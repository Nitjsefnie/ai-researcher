"""Structural pins on .github/workflows/ratchet-push.yml (issue #133 part 2b).

The ratchet raise's push is the workflow's one privileged delivery, and
its trust shape is the reason it exists as a top-level workflow: a
workflow_call callee cannot read an environment secret (claudit's #479),
and the workflow_run trigger's hazard — another run's data reaching a
privileged job — is gated shut four ways (event, branch, conclusion,
head repository) before the artifact is even downloaded. The artifact is
data and nothing else: validated inline, executed never.

The ci gate arm carries TWO candidates — the coverage thresholds, then
the size records (issue #333). Documents staged by one run land one per
main-tip generation: the first landing moves main, so the second drops
green and re-stages on the next main push's gate run.
"""
import contextlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

import pytest
import yaml

import _workflowrun

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ratchet-push.yml"


def load():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"),
                     Loader=yaml.BaseLoader)


def step(wf, name):
    matches = [s for s in wf["jobs"]["push"]["steps"]
               if s.get("name") == name]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one step named {name!r}, found {len(matches)}")
    return matches[0]


def flattened(text):
    return " ".join(text.split())


def commands(text):
    return flattened("\n".join(line for line in text.splitlines()
                               if not line.lstrip().startswith("#")))


class TriggerGateTests(unittest.TestCase):
    """The workflow_run hazard is gated shut before anything runs."""

    def setUp(self):
        self.wf = load()
        self.push = self.wf["jobs"]["push"]

    def test_the_trigger_names_both_ratchet_producers(self):
        wr = (self.wf.get("on") or self.wf.get(True) or {})["workflow_run"]
        assert wr["workflows"] == ["ci gate", "comment share"], wr
        assert wr["types"] == ["completed"], wr

    def test_the_job_admits_only_this_repos_main_push_success(self):
        condition = " ".join(self.push["if"].split())
        assert condition == " && ".join((
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.head_repository.full_name =="
            " github.repository",
        ))

    def test_the_environment_and_its_exclusivity(self):
        # The deploy key is reachable only through the main-push
        # environment, and only this workflow's push job declares it.
        assert self.push.get("environment") == "main-push"
        tests = yaml.load(
            (ROOT / ".github" / "workflows" / "tests.yml").read_text(
                encoding="utf-8"),
            Loader=yaml.BaseLoader)
        for name, job in tests["jobs"].items():
            assert "environment" not in job, (name, job.get("environment"))

    def test_the_job_holds_no_checkout_and_no_contents_write(self):
        assert self.push["permissions"] == {"actions": "read"}, (
            "the push authenticates with the deploy key; the job token "
            "stays at actions: read")
        assert not [s for s in self.push["steps"]
                    if s.get("uses", "").startswith("actions/checkout@")], (
            "the push job runs no repository code: no checkout step")

    def test_the_workflow_floor_is_empty(self):
        assert self.wf.get("permissions") == {}, (
            "the workflow floor is empty: every job declares its own block")


class ArtifactDataTests(unittest.TestCase):
    """The artifact is data and nothing else: validated inline, executed
    never, downloaded only from the triggering run."""

    def setUp(self):
        self.wf = load()

    def test_the_download_is_cross_run_and_gated(self):
        # One download step per candidate, each gated on that candidate's
        # own staged output and served by the list step's emission of the
        # same outputs (issue #333). The cross-run run-id expression is
        # enumerated over every workflow_run workflow by test_ci_workflows;
        # the token's cap is the job's actions: read pin.
        list_step = step(self.wf, "List the triggering run's artifacts")
        assert list_step["env"]["AI_RESEARCHER_WORKFLOW_NAME"] == (
            "${{ github.event.workflow_run.name }}")
        downloads = [entry for entry in self.wf["jobs"]["push"]["steps"]
                     if entry.get("uses", "").startswith(
                         "actions/download-artifact@")]
        assert len(downloads) == 3, downloads
        run_text = flattened(list_step["run"])
        for download in downloads:
            gate = re.fullmatch(
                r"steps\.list\.outputs\.(\w+)_staged == 'true'",
                " ".join(download["if"].split()))
            assert gate, download["if"]
            tag = gate.group(1)
            with_ = download["with"]
            reference = re.fullmatch(
                r"\$\{\{\s*steps\s*\.\s*list\s*\.\s*outputs\s*\.\s*"
                rf"{tag}_artifact\s*" + r"\}\}",
                " ".join(with_["name"].split()))
            assert reference is not None, with_["name"]
            for emitted in ("artifact", "document", "staged=true",
                            "staged=false"):
                assert f'"${{tag}}_{emitted}=$' in run_text or (
                    f'"${{tag}}_{emitted}"' in run_text), (tag, emitted)

    def test_the_loops_walk_exactly_the_downloaded_candidates(self):
        # The fixed candidate order the validate and push loops walk
        # must cover exactly the artifacts a download step can land:
        # nothing validated is not downloaded, nothing downloaded is
        # never validated (issue #333).
        loop_text = " ".join(
            step(self.wf, name)["run"]
            for name in ("Validate the staged data", "Push the ratchet commit"))
        walked = set(re.findall(
            r"'([a-z0-9-]+) ([a-z0-9.-]+\.json)'", loop_text))
        assert walked == {
            ("ratchet-data", "ci-thresholds.json"),
            ("size-baseline-data", "size-baseline.json"),
            ("comment-share-data", "comment-share.json"),
        }

    def test_the_validation_step_runs_before_the_push_step(self):
        names = [s.get("name") for s in self.wf["jobs"]["push"]["steps"]]
        assert names == [
            "List the triggering run's artifacts",
            "Download the ratchet data",
            "Download the size records",
            "Download the comment records",
            "Validate the staged data",
            "Push the ratchet commit",
        ], names

    def test_the_validation_gates_the_push_step(self):
        # A validation failure must hold the push step back entirely:
        # both steps share the staged gate, run in order, and a
        # validation failure fails the job under bash -e before the push
        # step starts.
        validate = step(self.wf, "Validate the staged data")
        push_step = step(self.wf, "Push the ratchet commit")
        assert validate["if"] == "steps.list.outputs.staged == 'true'"
        assert push_step["if"] == "steps.list.outputs.staged == 'true'"


class DeployKeyTests(unittest.TestCase):
    """The key contract, copied verbatim from the refresh push job."""

    def setUp(self):
        self.wf = load()

    def test_the_deploy_key_fails_closed(self):
        run = flattened(step(self.wf, "Push the ratchet commit")["run"])
        assert (
            "AI_RESEARCHER_MASTER_PUSH_DEPLOY_KEY is empty: the main-push environment is "
            "missing its secret" in run)
        assert "github.token" not in run

    def test_the_agent_never_outlives_the_step(self):
        run = flattened(step(self.wf, "Push the ratchet commit")["run"])
        assert 'trap \'kill "$SSH_AGENT_PID" 2>/dev/null || true\' EXIT' in run
        assert "ssh-add <(printf '%s\\n' \"$AI_RESEARCHER_MASTER_PUSH_DEPLOY_KEY\")" in run

    def test_the_base_check_drops_green_and_the_race_is_classified(self):
        run = flattened(step(self.wf, "Push the ratchet commit")["run"])
        assert "Main moved while this run measured" in run
        assert "the ratchet push was rejected while main stood still" in run
        assert "set -o pipefail" in run


class ExecutedValidationTests(unittest.TestCase):
    """The validate step EXECUTED against forged artifacts, not read.

    Text pins survive shapes the executed step would reject: the round-1
    review drove wrong-leaf keys, a garbage-suffixed base and a float
    schema_version through the flattened text and all three passed. Each
    case below runs the step's own run block under bash -e against a
    staged artifact and pins the verdict the push depends on.
    """
    VALID = {
        "coverage": {
            "javascript": {"floor": 95.3, "measured": 96.8},
            "python": {"floor": 92.8, "measured": 94.3},
        },
        "schema_version": 1,
    }
    SIZE_VALID = {
        "schema_version": 1,
        "baseline": {"build.py": 2890,
                     "tests/test_ratchet_push_workflow.py": 549},
    }
    BASE_COMMIT = "a" * 40

    @classmethod
    def setUpClass(cls):
        if os.name == "nt":
            # The validate step is a POSIX bash script exercising POSIX
            # tooling (ls/sort/tr/xargs), the same shape test_ci_gate_
            # output_wiring skips for its POSIX stub: on the Windows cells
            # the git-bash resolution differs in line endings only, and
            # the step runs on ubuntu in CI.
            raise unittest.SkipTest(
                "the validate step is a POSIX script; the Windows cells "
                "skip its execution")

    def _validate(self, tmp_path, document, payload_bytes, base_bytes,
                  directory=None):
        """Stage one candidate in its staging directory and run the
        validate step's script over RUNNER_TEMP; `directory` overrides
        the candidate's own staging directory (the wrong-arm cases)."""
        step_ = step(load(), "Validate the staged data")
        data = tmp_path / (directory or DIRECTORIES[document])
        data.mkdir(parents=True)
        (data / document).write_bytes(payload_bytes)
        (data / "base.txt").write_bytes(base_bytes)
        return _workflowrun.run_step(tmp_path, step_,
                                     {"RUNNER_TEMP": str(tmp_path),
                                      **staged_flags(data.name, "true")})

    def _run_with(self, tmp_path, document, base):
        payloads = {"ci-thresholds.json": self.VALID,
                    "size-baseline.json": self.SIZE_VALID,
                    "comment-share.json": {}}
        return self._validate(
            tmp_path, document,
            json.dumps(payloads[document]).encode("utf-8"),
            base.encode("utf-8"))

    def test_the_real_shape_passes(self):
        for document in ("ci-thresholds.json",):
            done = self._run_with(self.enterContext(_dir()), document,
                                  self.BASE_COMMIT)
            assert done.returncode == 0, (done.stdout, done.stderr)

    def test_wrong_leaf_keys_are_refused(self):
        document = {"coverage": {"javascript": {"a": 1, "b": 2},
                                 "python": {"floor": 1, "measured": 2}},
                    "schema_version": 1}
        done = self._validate(
            self.enterContext(_dir()), "ci-thresholds.json",
            json.dumps(document).encode("utf-8"),
            self.BASE_COMMIT.encode("utf-8"))
        assert done.returncode != 0, done.stdout

    def test_a_garbage_suffixed_base_is_refused(self):
        for document in ("ci-thresholds.json", "size-baseline.json"):
            done = self._run_with(self.enterContext(_dir()), document,
                                  self.BASE_COMMIT + "\nrm -rf /\n")
            assert done.returncode != 0, (document, done.stdout)

    def test_a_string_typed_leaf_is_refused(self):
        document = {"coverage": {"javascript": {"floor": "95", "measured": 1},
                                 "python": {"floor": 1, "measured": 2}},
                    "schema_version": 1}
        done = self._validate(
            self.enterContext(_dir()), "ci-thresholds.json",
            json.dumps(document).encode("utf-8"),
            self.BASE_COMMIT.encode("utf-8"))
        assert done.returncode != 0, done.stdout

    def test_a_string_schema_version_is_refused(self):
        document = dict(self.VALID, schema_version="1")
        done = self._validate(
            self.enterContext(_dir()), "ci-thresholds.json",
            json.dumps(document).encode("utf-8"),
            self.BASE_COMMIT.encode("utf-8"))
        assert done.returncode != 0, done.stdout

    def test_a_size_records_value_that_is_not_an_admissible_integer_is_refused(self):
        for value in (-1, 1.5, "1", True, None):
            payload = {"schema_version": 1, "baseline": {"a.py": value}}
            done = self._validate(
                self.enterContext(_dir()), "size-baseline.json",
                json.dumps(payload).encode("utf-8"),
                self.BASE_COMMIT.encode("utf-8"))
            assert done.returncode != 0, (value, done.stdout, done.stderr)

    def test_a_size_records_shape_outside_the_schema_is_refused(self):
        for payload in ({"schema_version": 1},
                        {"baseline": {}},
                        {"schema_version": 1, "baseline": {}, "extra": 1},
                        {"schema_version": 2, "baseline": {}},
                        {"schema_version": 1, "baseline": []},
                        {"schema_version": 1, "baseline": None}):
            done = self._validate(
                self.enterContext(_dir()), "size-baseline.json",
                json.dumps(payload).encode("utf-8"),
                self.BASE_COMMIT.encode("utf-8"))
            assert done.returncode != 0, (payload, done.stdout, done.stderr)

    def test_a_sibling_document_in_the_wrong_staging_directory_is_refused(self):
        # The staging directory selects the schema: a sibling document in
        # another arm's directory is an unexpected file there, and a
        # wrong-arm download must not pass as the right arm's document
        # (issue #333).
        for sibling in ("size-baseline.json", "comment-share.json"):
            done = self._validate(
                self.enterContext(_dir()), sibling,
                json.dumps({}).encode("utf-8"),
                self.BASE_COMMIT.encode("utf-8"),
                directory="ratchet-data")
            assert done.returncode != 0, (sibling, done.stdout, done.stderr)


@contextlib.contextmanager
def _dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield pathlib.Path(tmp)


POSIX = pytest.mark.skipif(os.name == "nt", reason="Ubuntu workflow shell")
BASE_COMMIT = "a" * 40
COMMENT_WORKFLOW = ROOT / ".github/workflows/comment-share.yml"
# Each candidate's staging directory, as the validate and push loops walk it.
DIRECTORIES = {
    "ci-thresholds.json": "ratchet-data",
    "size-baseline.json": "size-baseline-data",
    "comment-share.json": "comment-share-data",
}
MESSAGES = {
    "ci-thresholds.json":
        "Ratchet ci-thresholds: raise the coverage floor (automated)",
    "size-baseline.json":
        "Ratchet size-baseline: tighten the records (automated)",
    "comment-share.json":
        "Ratchet comment-share: tighten the records (automated)",
}
# Each staging directory's list-step tag, as the steps' env reads it.
TAGS = {"ratchet-data": "ratchet", "size-baseline-data": "size",
        "comment-share-data": "comment"}


def staged_flags(directory=None, truth="true"):
    """The list step's staged outputs, as the validate and push steps
    read them from their env."""
    flags = {tag: "false" for tag in TAGS.values()}
    if directory:
        flags[TAGS[directory]] = truth
    return {f"AI_RESEARCHER_{tag.upper()}_STAGED": value
            for tag, value in flags.items()}


# The outputs the list step emits per triggering workflow, executed below.
EXPECTED_OUTPUTS = {
    "ci gate": lambda staged: {
        "ratchet_artifact": "ratchet-data",
        "ratchet_document": "ci-thresholds.json",
        "size_artifact": "size-baseline-data",
        "size_document": "size-baseline.json",
        "ratchet_staged": str("ratchet-data" in staged).lower(),
        "size_staged": str("size-baseline-data" in staged).lower(),
        "staged": str(bool(staged)).lower(),
    },
    "comment share": lambda staged: {
        "comment_artifact": "comment-share-data",
        "comment_document": "comment-share.json",
        "comment_staged": str(bool(staged)).lower(),
        "staged": str(bool(staged)).lower(),
    },
}


@POSIX
@pytest.mark.parametrize("workflow,staged", [
    ("ci gate", []),
    ("ci gate", ["ratchet-data"]),
    ("ci gate", ["size-baseline-data"]),
    ("ci gate", ["ratchet-data", "size-baseline-data"]),
    ("comment share", []),
    ("comment share", ["comment-share-data"]),
])
def test_artifact_selection_and_absent_noop(tmp_path, workflow, staged):
    """A producer can only consume its own unexpired artifacts (issues
    #281 and #333): the arm's candidates are selected by the triggering
    workflow's name, each staged independently."""
    state, calls = tmp_path / "state.json", tmp_path / "calls.jsonl"
    bin_dir = tmp_path / "bin"
    _workflowrun.write_gh_stub(bin_dir, state, calls)
    sibling = ("comment-share-data" if workflow == "ci gate"
               else "ratchet-data")
    artifacts = [{"name": "unrelated", "expired": False},
                 {"name": sibling, "expired": False}]
    for name in staged:
        artifacts.append({"name": name, "expired": True})
        artifacts.append({"name": name, "expired": False})
    state.write_text(json.dumps({"artifacts": artifacts}), encoding="utf-8")
    output = tmp_path / "output"
    done = _workflowrun.run_step(tmp_path, step(load(), "List the triggering run's artifacts"), {
        **os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "STUB_STATE": str(state), "STUB_CALLS": str(calls),
        "GITHUB_OUTPUT": str(output), "AI_RESEARCHER_WORKFLOW_NAME": workflow,
        "GH_TOKEN": "test", "AI_RESEARCHER_REPO": "Nitjsefnie/ai-researcher", "AI_RESEARCHER_RUN_ID": "281",
    })
    assert done.returncode == 0, done.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert outputs == EXPECTED_OUTPUTS[workflow](staged)
    [call] = [json.loads(line) for line in calls.read_text().splitlines()]
    assert "repos/Nitjsefnie/ai-researcher/actions/runs/281/artifacts" in call


def test_ratchet_artifact_names_have_exclusive_producers():
    """A same-name upload anywhere else could substitute another data path."""
    producers = {"ratchet-data": [], "comment-share-data": [],
                 "size-baseline-data": []}
    for path in (ROOT / ".github/workflows").glob("*.y*ml"):
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in wf["jobs"].values():
            for candidate in job.get("steps", []):
                if candidate.get("uses", "").startswith("actions/upload-artifact@"):
                    name = candidate["with"]["name"]
                    assert "${{" not in name, "dynamic names cannot prove isolation"
                    if name in producers:
                        producers[name].append(path.name)
    assert producers == {"ratchet-data": ["tests.yml"],
                         "comment-share-data": ["comment-share.yml"],
                         "size-baseline-data": ["size-baseline.yml"]}


def test_comment_staging_is_push_only_and_uploads_only_when_changed():
    wf = yaml.load(COMMENT_WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    steps = wf["jobs"]["comment-share"]["steps"]
    stage = next(s for s in steps if s.get("id") == "stage")
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert steps.index(stage) > next(
        i for i, s in enumerate(steps)
        if s.get("uses", "").startswith("Nitjsefnie-Actions/comment-ratchet@"))
    assert stage["if"] == "github.event_name == 'push'"
    assert stage["env"]["AI_RESEARCHER_HEAD_SHA"] == "${{ github.sha }}"
    assert upload["if"] == "github.event_name == 'push' && steps.stage.outputs.changed == 'true'"
    assert wf["permissions"] == {"contents": "read"}


@POSIX
@pytest.mark.parametrize("changed", [False, True])
def test_comment_staging_bytes_and_measured_base(tmp_path, changed):
    """The stage compares the pushed SHA's bytes and copies the tightened bytes."""
    original = b'{"module.py": [10, 100]}\n'
    current = b'{"module.py": [9, 100]}\n' if changed else original
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/comment-share.json").write_bytes(current)
    (tmp_path / "original").write_bytes(original)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text('#!/bin/sh\nset -eu\n'
                   f'[ "$*" = "show {BASE_COMMIT}:.github/comment-share.json" ]\n'
                   'cat "$ORIGINAL"\n', encoding="utf-8")
    git.chmod(0o755)
    runner = tmp_path / "runner"
    runner.mkdir()
    output = tmp_path / "output"
    stage = _workflowrun.step_by_name(COMMENT_WORKFLOW, "comment-share", "Stage tightened records")
    done = _workflowrun.run_step(tmp_path, stage, {
        **os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "AI_RESEARCHER_HEAD_SHA": BASE_COMMIT, "ORIGINAL": str(tmp_path / "original"),
        "RUNNER_TEMP": str(runner), "GITHUB_OUTPUT": str(output),
    })
    assert done.returncode == 0, done.stderr
    assert output.read_text().strip() == f"changed={str(changed).lower()}"
    data = runner / "comment-share-data"
    if changed:
        assert sorted(p.name for p in data.iterdir()) == ["base.txt", "comment-share.json"]
        assert (data / "base.txt").read_text() == BASE_COMMIT + "\n"
        assert (data / "comment-share.json").read_bytes() == current
    else:
        assert not data.exists()


@POSIX
@pytest.mark.parametrize("payload,valid", [
    ('[]', False), ('null', False), ('{"x": [1.5, 2]}', False),
    ('{"x": [-1, 2]}', False), ('{"x": [1, -2]}', False),
    ('{"x": [1, 2.5]}', False), ('{"x": [1]}', False),
    ('{"x": [1, 2, 3]}', False), ('{"x": []}', False),
    ('{"x": {"a": 1, "b": 2}}', False), ('{"x": [true, 2]}', False),
    ('{"x": ["1", 2]}', False), ('{"x": [null, 2]}', False),
    ('{"x": [NaN, 2]}', False), ('{"x": [1, NaN]}', False),
    ('{"x": [Infinity, 2]}', False), ('{"x": [1, Infinity]}', False),
    ('{"x": [1e999, 2]}', False), ('{"x": [1, -Infinity]}', False),
    ('[] {}', False), ('{} {}', False), ('', False),
])
def test_comment_schema_executed(tmp_path, payload, valid):
    data = tmp_path / "comment-share-data"
    data.mkdir()
    (data / "base.txt").write_text(BASE_COMMIT, encoding="utf-8")
    (data / "comment-share.json").write_text(payload, encoding="utf-8")
    done = _workflowrun.run_step(tmp_path, step(load(), "Validate the staged data"), {
        **os.environ, "RUNNER_TEMP": str(tmp_path),
        **staged_flags("comment-share-data", "true"),
    })
    assert (done.returncode == 0) == valid, (payload, done.stdout, done.stderr)


@POSIX
@pytest.mark.parametrize("payload,valid", [
    ('{"baseline": {}}', False),
    ('{"schema_version": 1}', False),
    ('{"schema_version": 1, "baseline": {}, "x": 1}', False),
    ('{"schema_version": 2, "baseline": {}}', False),
    ('{"schema_version": "1", "baseline": {}}', False),
    ('{"schema_version": true, "baseline": {}}', False),
    ('{"schema_version": 1, "baseline": []}', False),
    ('{"schema_version": 1, "baseline": null}', False),
    ('{"schema_version": 1, "baseline": {"a.py": -1}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": 1.5}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": "1"}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": true}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": null}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": NaN}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": Infinity}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": 1e999}}', False),
    ('{"schema_version": 1, "baseline": {"a.py": -Infinity}}', False),
    ('{"schema_version": 1, "baseline": {}} {}', False),
    ('{"schema_version": 1, "baseline": {}} {"schema_version": 1, "baseline": {}}',
     False),
    ('', False),
])
def test_size_schema_executed(tmp_path, payload, valid):
    """The size records schema, executed: exact top-level keys,
    schema_version exactly 1, and a baseline of finite non-negative
    integers — one JSON document, no stream (issue #333)."""
    data = tmp_path / "size-baseline-data"
    data.mkdir()
    (data / "base.txt").write_text(BASE_COMMIT, encoding="utf-8")
    (data / "size-baseline.json").write_text(payload, encoding="utf-8")
    done = _workflowrun.run_step(tmp_path, step(load(), "Validate the staged data"), {
        **os.environ, "RUNNER_TEMP": str(tmp_path),
        **staged_flags("size-baseline-data", "true"),
    })
    assert (done.returncode == 0) == valid, (payload, done.stdout, done.stderr)


@POSIX
@pytest.mark.parametrize("directory,document,payload,sibling", [
    ("ratchet-data", "ci-thresholds.json",
     json.dumps(ExecutedValidationTests.VALID), "size-baseline.json"),
    ("size-baseline-data", "size-baseline.json",
     '{"schema_version": 1, "baseline": {}}', "ci-thresholds.json"),
    ("comment-share-data", "comment-share.json", "{}", "size-baseline.json"),
])
@pytest.mark.parametrize("base,extra", [
    ("a" * 39, None), ("g" * 40, None), (BASE_COMMIT + "\nextra", None),
    (BASE_COMMIT, "extra.sh"), (BASE_COMMIT, ".hidden"),
    (BASE_COMMIT, "SIBLING"), (BASE_COMMIT, " "),
])
def test_artifact_shape_executed(tmp_path, directory, document, payload,
                                 sibling, base, extra):
    """Every arm's two-file shape: base.txt plus only that arm's
    document; the sibling document planted in the directory is refused
    in every arm (issue #333)."""
    data = tmp_path / directory
    data.mkdir()
    (data / "base.txt").write_text(base, encoding="utf-8")
    (data / document).write_text(payload, encoding="utf-8")
    if extra:
        (data / (sibling if extra == "SIBLING" else extra)).write_text(
            "exit 99", encoding="utf-8")
    done = _workflowrun.run_step(tmp_path, step(load(), "Validate the staged data"), {
        **os.environ, "RUNNER_TEMP": str(tmp_path),
        **staged_flags(directory, "true"),
    })
    assert done.returncode != 0, (done.stdout, done.stderr)


def _git(workdir, *args):
    done = subprocess.run(["git", *args], cwd=workdir, check=True,
                          capture_output=True, text=True)
    return done.stdout.strip()


def _push_fixture(tmp_path, outcome, staged):
    """Build the isolated push fixture: a source repo whose tip is the
    measured base, a bare remote pinned at it, the push step's stub bin
    dir, and one staging directory per requested candidate. Returns the
    step env and the base and moved SHAs."""
    source = tmp_path / "source"
    _git(tmp_path, "init", "-q", "-b", "main", str(source))
    _git(source, "config", "user.name", "fixture")
    _git(source, "config", "user.email", "fixture@example.com")
    _git(source, "config", "commit.gpgsign", "false")
    (source / ".github").mkdir()
    (source / ".github/.gitkeep").write_text("", encoding="utf-8")
    _git(source, "add", ".github/.gitkeep")
    _git(source, "commit", "-m", "base")
    base = _git(source, "rev-parse", "HEAD")
    _git(source, "commit", "--allow-empty", "-m", "moved")
    moved = _git(source, "rev-parse", "HEAD")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    # Share only the fixture's complete history, independent of checkout depth.
    objects = _git(source, "rev-parse", "--path-format=absolute", "--git-path", "objects")
    (remote / "objects/info/alternates").write_text(objects + "\n", encoding="utf-8")
    _git(tmp_path, "--git-dir", str(remote), "update-ref", "refs/heads/main", base)
    payloads = {
        "comment-share.json": b'{}\n',
        "ci-thresholds.json": json.dumps(
            ExecutedValidationTests.VALID).encode("utf-8") + b"\n",
        "size-baseline.json": json.dumps(
            ExecutedValidationTests.SIZE_VALID).encode("utf-8") + b"\n",
    }
    for document in staged:
        data = tmp_path / DIRECTORIES[document]
        data.mkdir()
        (data / "base.txt").write_text(
            BASE_COMMIT if outcome == "stale" else base, encoding="utf-8")
        (data / document).write_bytes(payloads[document])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {
        "ssh-agent": "printf 'SSH_AGENT_PID=; export SSH_AGENT_PID;\\n'",
        "ssh-add": "exit 0",
        "git": 'exec "$TEST_PYTHON" "$TEST_GIT_STUB" "$@"',
    }.items():
        path = bin_dir / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)
    stub = bin_dir / "git_stub.py"
    stub.write_text(PUSH_GIT_STUB, encoding="utf-8")
    # Isolate SSH's known_hosts writes from the user's home directory.
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "HOME": str(home), "RUNNER_TEMP": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "AI_RESEARCHER_REPO": "Nitjsefnie/ai-researcher",
        "AI_RESEARCHER_MASTER_PUSH_DEPLOY_KEY": "" if outcome == "no-key" else "test input",
        "PUSH_REMOTE": str(remote), "REAL_GIT": shutil.which("git") or "git",
        "TEST_PYTHON": shutil.which("python3") or "python3", "TEST_GIT_STUB": str(stub),
        "TEST_CALLS": str(tmp_path / "calls.jsonl"), "TEST_OUTCOME": outcome,
        "TEST_MOVED": moved,
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": objects,
        **staged_flags(),
    }
    for document in staged:
        env.update(staged_flags(DIRECTORIES[document], "true"))
    return env, base, moved, remote


@POSIX
@pytest.mark.parametrize("document", ["comment-share.json", "ci-thresholds.json",
                                      "size-baseline.json"])
@pytest.mark.parametrize("outcome", [
    "landed", "stale", "moved-before-fetch", "rejected", "moved", "no-key", "transport",
])
def test_records_only_push_and_race_classification(tmp_path, document, outcome):
    """Run the real push script with isolated SSH and controlled remote movement."""
    env, base, moved, remote = _push_fixture(tmp_path, outcome, [document])
    done = _workflowrun.run_step(tmp_path, step(load(), "Push the ratchet commit"), env)
    assert (done.returncode != 0) == (outcome in {"no-key", "transport", "rejected"}), (
        done.stdout, done.stderr)
    tip = _git(tmp_path, "--git-dir", str(remote), "rev-parse", "refs/heads/main")
    recorded = [json.loads(line) for line in
                (tmp_path / "calls.jsonl").read_text().splitlines()] if (
        tmp_path / "calls.jsonl").exists() else []
    if outcome == "landed":
        payload = (b'{}\n' if document == "comment-share.json" else
                   json.dumps(ExecutedValidationTests.SIZE_VALID
                              if document == "size-baseline.json"
                              else ExecutedValidationTests.VALID).encode("utf-8") + b"\n")
        assert _git(tmp_path, "--git-dir", str(remote), "rev-parse", tip + "^") == base
        assert _git(tmp_path, "--git-dir", str(remote), "diff-tree", "--no-commit-id",
                    "--name-only", "-r", tip) == f".github/{document}"
        assert _git(tmp_path, "--git-dir", str(remote), "show", f"{tip}:.github/{document}") == payload.decode().strip()
        assert _git(tmp_path, "--git-dir", str(remote), "show", "-s", "--format=%s", tip) == MESSAGES[document]
        assert not (tmp_path / "summary").exists()
    else:
        assert tip == (moved if outcome in {"moved", "moved-before-fetch"} else base)
    if outcome in {"stale", "moved-before-fetch", "moved"}:
        assert "main moved while this run measured" in (tmp_path / "summary").read_text().lower()
    if outcome == "moved-before-fetch":
        assert "### Dropped: main moved while this run measured" in (tmp_path / "summary").read_text()
        assert f"({moved})" in (tmp_path / "summary").read_text()
        commands_ = [args[2:] if args[0] == "-C" else args for args in recorded]
        assert any(args[0] == "fetch" for args in commands_)
        assert not any(args[0] in {"checkout", "add", "commit", "push"} for args in commands_)
        assert not (tmp_path / "ratchet-repo/.github" / document).exists()
    if outcome in {"rejected", "moved"}:
        assert _git(tmp_path / "ratchet-repo", "rev-parse", "HEAD^") == base
    if outcome in {"stale", "transport", "no-key"}:
        assert not (tmp_path / "ratchet-repo").exists()
    if outcome == "no-key":
        assert not recorded
        assert "AI_RESEARCHER_MASTER_PUSH_DEPLOY_KEY is empty" in done.stderr
    if outcome == "rejected":
        assert "the ratchet push was rejected while main stood still" in done.stderr


@POSIX
def test_two_staged_documents_land_one_per_tip_generation(tmp_path):
    """One document lands per main-tip generation, executed: with both
    ci gate candidates staged at one base, thresholds lands first (the
    determinism order) and the size records drop green (main moved),
    re-staging on the next main push's gate run (issue #333)."""
    env, base, _moved, remote = _push_fixture(
        tmp_path, "landed", ["ci-thresholds.json", "size-baseline.json"])
    done = _workflowrun.run_step(tmp_path, step(load(), "Push the ratchet commit"), env)
    assert done.returncode == 0, (done.stdout, done.stderr)
    tip = _git(tmp_path, "--git-dir", str(remote), "rev-parse", "refs/heads/main")
    assert _git(tmp_path, "--git-dir", str(remote), "rev-parse", tip + "^") == base
    assert _git(tmp_path, "--git-dir", str(remote), "show", "-s", "--format=%s",
                tip) == MESSAGES["ci-thresholds.json"]
    # Exactly one landing: the thresholds document's commit is the only
    # one past the measured base.
    assert _git(tmp_path, "--git-dir", str(remote), "log", "--format=%s",
                f"{base}..{tip}").splitlines() == [MESSAGES["ci-thresholds.json"]]
    summary = (tmp_path / "summary").read_text(encoding="utf-8")
    assert "main moved while this run measured" in summary.lower()


@POSIX
@pytest.mark.parametrize("document", ["ci-thresholds.json", "size-baseline.json",
                                      "comment-share.json"])
def test_a_staged_artifact_without_its_directory_is_a_loud_failure(
        tmp_path, document):
    """A staged artifact with no staging directory is a loud failure,
    never a green no-op (issue #333)."""
    done = _workflowrun.run_step(tmp_path, step(load(), "Validate the staged data"), {
        **os.environ, "RUNNER_TEMP": str(tmp_path),
        **staged_flags(DIRECTORIES[document], "true"),
    })
    assert done.returncode != 0, (document, done.stdout, done.stderr)
    assert document in done.stderr


@POSIX
@pytest.mark.parametrize("directory", ["ratchet-data", "size-baseline-data",
                                       "comment-share-data"])
def test_an_unstaged_candidate_without_a_directory_stays_a_no_op(
        tmp_path, directory):
    """With the staged output false, an absent directory stays a
    green no-op (issue #333)."""
    done = _workflowrun.run_step(tmp_path, step(load(), "Validate the staged data"), {
        **os.environ, "RUNNER_TEMP": str(tmp_path),
        **staged_flags(directory, "false"),
    })
    assert done.returncode == 0, (directory, done.stdout, done.stderr)


@POSIX
def test_push_staged_artifact_without_its_directory_is_a_loud_failure(tmp_path):
    """A staged artifact with no staging directory fails the push
    step loudly, never a silent no-op (issue #333)."""
    env, _base, _moved, _remote = _push_fixture(tmp_path, "landed", [])
    env.update(staged_flags("ratchet-data", "true"))
    done = _workflowrun.run_step(tmp_path, step(load(), "Push the ratchet commit"), env)
    assert done.returncode != 0, (done.stdout, done.stderr)
    assert "ci-thresholds.json" in done.stderr


@POSIX
def test_push_unstaged_candidates_without_directories_stay_a_no_op(tmp_path):
    """With every staged output false and no directories, the push
    step completes without touching the remote (issue #333)."""
    env, base, _moved, remote = _push_fixture(tmp_path, "landed", [])
    done = _workflowrun.run_step(tmp_path, step(load(), "Push the ratchet commit"), env)
    assert done.returncode == 0, (done.stdout, done.stderr)
    tip = _git(tmp_path, "--git-dir", str(remote), "rev-parse", "refs/heads/main")
    assert tip == base


PUSH_GIT_STUB = '''import json
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
with Path(os.environ["TEST_CALLS"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
command = args[2:] if args[0] == "-C" else args
outcome = os.environ["TEST_OUTCOME"]
real = os.environ["REAL_GIT"]
if command[0] == "ls-remote" and outcome == "transport":
    sys.exit(128)
if command[0] == "fetch" and outcome == "moved-before-fetch":
    subprocess.run([real, "--git-dir", os.environ["PUSH_REMOTE"], "update-ref",
                    "refs/heads/main", os.environ["TEST_MOVED"]], check=True)
if command[0] == "push":
    assert command == ["push", "origin", "HEAD:main"], command
    if outcome == "moved":
        subprocess.run([real, "--git-dir", os.environ["PUSH_REMOTE"], "update-ref",
                        "refs/heads/main", os.environ["TEST_MOVED"]], check=True)
    if outcome == "rejected":
        sys.exit(1)
os.execv(real, [real, *args])
'''
