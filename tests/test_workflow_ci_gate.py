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
- trigger ownership really moved: the six callees no longer carry
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
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI_GATE = WORKFLOWS / "ci-gate.yml"
COVERAGE_COMMENT = WORKFLOWS / "coverage-comment.yml"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"

# The six gate workflows ci-gate calls, plus the classifier job.
LEG_WORKFLOWS = (
    "tests.yml", "lint.yml", "types.yml", "audit.yml", "actionlint.yml",
    "codeql.yml",
)
LEG_IDS = tuple(Path(name).stem for name in LEG_WORKFLOWS)


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
    for leg in ("tests", "lint", "types", "audit", "actionlint"):
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
