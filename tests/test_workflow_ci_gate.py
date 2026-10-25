"""Workflow shape: one aggregate gate owns the push/PR trigger surface.

ci-gate.yml folds every gate workflow's result into one verdict
(`ci gate / aggregate`, the name a future ruleset requires), and the
docs-only classifier narrows the expensive legs, the cheap legs still
run, and every required check still reports. The invariants pinned
here:

- every reusable call points at an existing workflow that declares
  `workflow_call`;
- the aggregate job runs with `if: always()` and needs every leg, so it
  reports even when legs fail, skip or never start;
- trigger ownership really moved: the seven callees no longer carry
  `push`/`pull_request`, and ci-gate's push and pull_request triggers
  are unfiltered by path — the classification, not a trigger filter,
  narrows;
- the aggregate's expected-leg list and the workflow's needs list cannot
  drift apart;
- the classifier's NON_LEG_JOBS and this file's LEG_IDS must together
  name every ci-gate job;
- every leg grants its callee read-only (`contents: read`): the callee
  runs no writer — the ratchet raise leaves tests.yml as an artifact for
  the top-level ratchet-push workflow — and the codeql leg forwards the
  `security-events: write` its callee needs;
- coverage-comment relays on the ci-gate run, the run that carries the
  diff-coverage-comment artifact once tests.yml is a workflow_call
  callee.
- the size-baseline leg (issue #333) is a workflow_call-only callee
  (mode: auto fails closed on a dispatch event) that stages its
  tightened records as an artifact on a main push only when the action
  changed them — the staging step is executed here, not only read,
  since a `run:` block is executable code.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest
import yaml

import _workflowrun

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI_GATE = WORKFLOWS / "ci-gate.yml"
COVERAGE_COMMENT = WORKFLOWS / "coverage-comment.yml"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"
SIZE_BASELINE = WORKFLOWS / "size-baseline.yml"
RATCHET_PUSH = WORKFLOWS / "ratchet-push.yml"

# The seven gate workflows ci-gate calls, plus the classifier job.
LEG_WORKFLOWS = ("tests.yml", "lint.yml", "types.yml", "audit.yml",
                 "actionlint.yml", "size-baseline.yml", "codeql.yml")
LEG_IDS = tuple(Path(name).stem for name in LEG_WORKFLOWS)

# A pushed SHA for the executed staging control: the step's git double
# answers only `git show <this>:<records path>`.
POSIX = pytest.mark.skipif(os.name == "nt", reason="Ubuntu workflow shell")
BASE_COMMIT = "a" * 40


def _load(path):
    # BaseLoader, not safe_load: YAML 1.1 parses the bare key `on` as the
    # boolean True, and these tests read the trigger map by name.
    return yaml.load(path.read_text(encoding="utf-8"),
                     Loader=yaml.BaseLoader) or {}


def _ci_gate():
    return _load(CI_GATE)


def _coverage_comment():
    return _load(COVERAGE_COMMENT)


def _aggregate_module():
    spec = importlib.util.spec_from_file_location(
        "aggregate_gate_shape",
        ROOT / "scripts" / "ci" / "aggregate_gate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["aggregate_gate_shape"] = module
    spec.loader.exec_module(module)
    return module


def test_every_reusable_call_points_at_an_existing_callable_workflow():
    doc = _ci_gate()
    for job_id, job in doc["jobs"].items():
        uses = (job or {}).get("uses") or ""
        if not uses.startswith("./.github/workflows/"):
            continue
        name = uses.removeprefix("./.github/workflows/")
        target = WORKFLOWS / name
        assert target.exists(), (job_id, uses)
        assert "workflow_call" in (_load(target).get("on") or {}), (
            job_id, uses)


def test_caller_and_every_callee_key_push_concurrency_by_sha():
    doc = _ci_gate()
    workflows = {CI_GATE: doc}
    for job in doc["jobs"].values():
        uses = (job or {}).get("uses") or ""
        if uses.startswith("./.github/workflows/"):
            target = WORKFLOWS / uses.removeprefix("./.github/workflows/")
            workflows[target] = _load(target)
    assert len(workflows) > 1
    for path, workflow in workflows.items():
        group = workflow["concurrency"]["group"]
        assert isinstance(group, str), path.name
        push_sha = re.search(
            r"\(\s*github\.event_name\s*==\s*'push'\s*&&\s*github\.sha\s*\)",
            group)
        assert push_sha, (path.name, group)
        ref_position = group.find("github.ref")
        assert ref_position == -1 or ref_position > push_sha.end(), (
            path.name, group)


def test_aggregate_always_runs_and_needs_every_leg():
    doc = _ci_gate()
    aggregate = doc["jobs"]["aggregate"]
    assert aggregate.get("if") == "${{ always() }}"
    needs = aggregate["needs"]
    for leg in ("classify", *LEG_IDS):
        assert leg in needs, leg


def test_aggregate_legs_match_the_modules_expected_legs():
    # Lockstep pin: the workflow's needs list and the aggregate module's
    # expected-leg tuple fail together, so adding or removing a leg in
    # one place without the other goes red here.
    module = _aggregate_module()
    assert module.EXPECTED_LEGS == ("classify", *LEG_IDS)


def test_ci_gate_jobs_are_exactly_the_non_leg_jobs_plus_the_legs():
    # Lockstep pin for the verified-base walk: the classifier's
    # NON_LEG_JOBS and this file's LEG_IDS must together name every
    # ci-gate job, so a leg added to the workflow moves all three lists
    # in one commit or this test goes red — a job the walk mistakes for
    # the classifier or the aggregate would otherwise read as "no leg
    # ran".
    spec = importlib.util.spec_from_file_location(
        "classify_changes_shape",
        ROOT / "scripts" / "ci" / "classify_changes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["classify_changes_shape"] = module
    spec.loader.exec_module(module)
    assert (set(_ci_gate()["jobs"])
            == set(module.NON_LEG_JOBS) | set(LEG_IDS))


def test_legs_are_conditioned_on_the_narrowing_outputs():
    # A bot-data-only change runs only the cheap legs; every other
    # conditioned leg needs BOTH narrowing outputs false. The cheap set
    # is pinned in lockstep with the aggregate module's CHEAP_LEGS, so a
    # leg cannot change class in one place.
    cheap = _aggregate_module().CHEAP_LEGS
    assert set(cheap) == {"lint", "actionlint"}
    doc = _ci_gate()
    for leg in LEG_IDS:
        gate = doc["jobs"][leg].get("if") or ""
        if leg == "actionlint":
            # The gate on the gates: no narrowing output may skip it.
            assert gate == "", leg
            only_needs = doc["jobs"][leg].get("needs")
            assert only_needs == "classify", leg
            continue
        if leg in cheap:
            assert gate == (
                "needs.classify.outputs.docs_only != 'true'"), leg
        else:
            assert gate == (
                "needs.classify.outputs.docs_only != 'true' "
                "&& needs.classify.outputs.data_only != 'true'"), leg


def test_aggregate_module_names_the_same_cheap_legs_the_workflow_runs():
    # The fold accepts a skipped leg under data_only only OUTSIDE the
    # cheap set, and the workflow runs the cheap set under data_only —
    # the same tuple, so the two files cannot disagree silently.
    module = _aggregate_module()
    assert module.CHEAP_LEGS == frozenset({"lint", "actionlint"})
    doc = _ci_gate()
    for leg in LEG_IDS:
        gate = doc["jobs"][leg].get("if") or ""
        runs_under_data_only = "data_only" not in gate
        assert runs_under_data_only == (leg in module.CHEAP_LEGS), leg


def test_ci_gate_push_and_pr_triggers_are_unfiltered_by_path():
    # The classification, not a trigger filter, narrows: ci-gate starts
    # on every push and pull request, so a docs-only change still gets
    # an aggregate verdict and the bot-data push still gets its cheap
    # class. (claudit's ci-gate keeps one trigger-level paths-ignore for
    # its ratchet bot's file; this repository has no bot whose commit
    # is silent by trigger — the refresh bot's data push is the
    # data_only class instead.)
    triggers = _ci_gate().get("on") or {}
    push = triggers.get("push") or {}
    assert push.get("branches") == ["main"]
    assert not push.get("paths-ignore")
    assert not push.get("paths")
    pull = triggers.get("pull_request") or {}
    assert not pull.get("paths-ignore")
    assert not pull.get("paths")


def test_classify_job_outputs_the_narrowing_outputs():
    outputs = _ci_gate()["jobs"]["classify"].get("outputs") or {}
    assert "docs_only" in outputs
    assert "data_only" in outputs
    assert "reason" in outputs


def test_classify_job_reads_actions_for_the_verified_base_walk():
    # On a push the classifier walks the ci-gate workflow runs and
    # run-jobs endpoints for the newest main commit whose legs executed.
    # Without `actions: read` every such read 403s and every push
    # over-runs to full legs, silently disabling docs-only narrowing on
    # main.
    permissions = _ci_gate()["jobs"]["classify"].get("permissions") or {}
    assert permissions.get("actions") == "read"


def test_every_leg_grants_read_only():
    # The callee runs no writer (issue #133 part 2b removed tests.yml's
    # ratchet-push job; the raise leaves as an artifact for the
    # top-level ratchet-push workflow), so every leg's grant stays at the
    # workflow floor. The codeql leg forwards the security-events write
    # its callee's job requests — the one non-contents elevation.
    doc = _ci_gate()
    for leg in ("tests", "lint", "types", "audit", "actionlint",
                "size-baseline"):
        assert (doc["jobs"][leg].get("permissions") or {}).get(
            "contents") == "read", leg
    codeql = doc["jobs"]["codeql"].get("permissions") or {}
    assert codeql.get("security-events") == "write"
    assert codeql.get("contents") == "read"
    assert codeql.get("actions") == "read"


def test_the_callees_no_longer_carry_push_or_pull_request_triggers():
    # Trigger ownership really moved.
    for name in LEG_WORKFLOWS:
        triggers = _load(WORKFLOWS / name).get("on") or {}
        assert "push" not in triggers, name
        assert "pull_request" not in triggers, name
        assert "workflow_call" in triggers, name


def test_coverage_comment_relays_on_the_ci_gate_run():
    # tests.yml is a workflow_call callee and produces no run of its own
    # on a pull request — the run carrying the diff-coverage-comment
    # artifact is ci-gate's, so the relay keys on that workflow's name.
    wr = (_coverage_comment().get("on") or {}).get("workflow_run") or {}
    assert wr.get("workflows") == ["ci gate"]
    assert wr.get("types") == ["completed"]


def test_the_diff_coverage_job_still_runs_on_pull_request_events():
    # The caller's event flows through the workflow_call: the callee's
    # diff-coverage job gates on `github.event_name == 'pull_request'`
    # and must keep doing so — it is what computes and uploads the
    # artifact the coverage-comment relay posts.
    jobs = _load(TESTS_WORKFLOW)["jobs"]
    condition = str(jobs["diff-coverage"].get("if") or "")
    assert "github.event_name == 'pull_request'" in condition


def test_the_size_baseline_callee_declares_workflow_call_alone():
    # issue #333: the size-ratchet action's mode: auto checks pull
    # requests and tightens main pushes; any other event —
    # workflow_dispatch among them — fails closed, so the callee declares
    # workflow_call and nothing else. ci-gate owns the trigger surface.
    triggers = _load(SIZE_BASELINE).get("on") or {}
    assert list(triggers) == ["workflow_call"]


def test_the_size_baseline_staging_is_push_only_and_uploads_only_when_changed():
    # The action writes the records file into the checkout when tighten
    # changed it; the staging step detects exactly that difference against
    # the pushed SHA and stages base.txt + the changed file. The staging
    # step sits after the size-ratchet step because the action's write is
    # what it stages — the locator reads the step's action name and pins
    # nothing about its pin or inputs (issue item 6).
    doc = _load(SIZE_BASELINE)
    steps = doc["jobs"]["size-baseline"]["steps"]
    stage = next(s for s in steps if s.get("id") == "stage")
    upload = next(s for s in steps
                  if s.get("uses", "").startswith("actions/upload-artifact@"))
    ratchet_at = next(i for i, s in enumerate(steps) if s.get(
        "uses", "").startswith("Nitjsefnie-Actions/size-ratchet@"))
    assert steps.index(stage) > ratchet_at
    assert stage["if"] == "github.event_name == 'push'"
    assert stage["env"]["AI_RESEARCHER_HEAD_SHA"] == "${{ github.sha }}"
    assert upload["if"] == (
        "github.event_name == 'push' "
        "&& steps.stage.outputs.changed == 'true'")


def test_the_size_baseline_artifact_name_is_the_staging_directory_name():
    # The artifact name is not pinned as a literal input: the upload's
    # name must be the staging directory the stage step itself populates,
    # AND the artifact ratchet-push downloads for the size document must
    # land in that same directory — one relational chain read from both
    # workflows, so no step can disagree about where the bytes come from
    # or where they go. (The name's exclusivity across the catalogue is
    # pinned by test_ratchet_push_workflow.py's producers map.)
    steps = _load(SIZE_BASELINE)["jobs"]["size-baseline"]["steps"]
    stage = next(s for s in steps if s.get("id") == "stage")
    upload = next(s for s in steps
                  if s.get("uses", "").startswith("actions/upload-artifact@"))
    directories = re.findall(r'data="\$\{RUNNER_TEMP\}/([a-z0-9-]+)"',
                             stage["run"])
    assert len(directories) == 1, stage["run"]
    directory = directories[0]
    assert upload["with"]["name"] == directory

    push_steps = _load(RATCHET_PUSH)["jobs"]["push"]["steps"]
    [size_download] = [
        s for s in push_steps
        if s.get("uses", "").startswith("actions/download-artifact@")
        and " ".join(s["with"]["path"].split())
        == "${{ runner.temp }}/" + directory]
    # The name is the list step's output for the same candidate the
    # staging step uploads; the executed selection tests pin that output's
    # value to the uploaded name, so the downloaded bytes are the staged
    # bytes.
    assert " ".join(size_download["with"]["name"].split()) == (
        "${{ steps.list.outputs.size_artifact }}")
    list_run = " ".join(next(
        s for s in push_steps if s.get("id") == "list")["run"].split())
    assert '"${tag}_artifact=$artifact"' in list_run


@POSIX
@pytest.mark.parametrize("changed", [False, True])
def test_size_baseline_staging_bytes_and_measured_base(tmp_path, changed):
    """The stage compares the pushed SHA's bytes and copies the tightened bytes.

    Executed control for the step above: the git double answers only
    `git show <pushed sha>:.github/size-baseline.json`, so the verdict
    comes from the step's own shell, not its text.
    """
    original = b'{"schema_version": 1, "baseline": {"build.py": 2900}}\n'
    current = (b'{"schema_version": 1, "baseline": {"build.py": 2890}}\n'
               if changed else original)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/size-baseline.json").write_bytes(current)
    (tmp_path / "original").write_bytes(original)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text('#!/bin/sh\nset -eu\n'
                   f'[ "$*" = "show {BASE_COMMIT}:.github/size-baseline.json" ]\n'
                   'cat "$ORIGINAL"\n', encoding="utf-8")
    git.chmod(0o755)
    runner = tmp_path / "runner"
    runner.mkdir()
    output = tmp_path / "output"
    stage = _workflowrun.step_by_name(
        SIZE_BASELINE, "size-baseline", "Stage tightened records")
    done = _workflowrun.run_step(tmp_path, stage, {
        **os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "AI_RESEARCHER_HEAD_SHA": BASE_COMMIT,
        "ORIGINAL": str(tmp_path / "original"),
        "RUNNER_TEMP": str(runner), "GITHUB_OUTPUT": str(output),
    })
    assert done.returncode == 0, done.stderr
    assert output.read_text(encoding="utf-8").strip() == (
        f"changed={str(changed).lower()}")
    data = runner / "size-baseline-data"
    if changed:
        assert sorted(p.name for p in data.iterdir()) == [
            "base.txt", "size-baseline.json"]
        assert (data / "base.txt").read_text(encoding="utf-8") == (
            BASE_COMMIT + "\n")
        assert (data / "size-baseline.json").read_bytes() == current
    else:
        assert not data.exists()
