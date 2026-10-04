"""Structural pins on .github/workflows/ratchet-push.yml (issue #133 part 2b).

The ratchet raise's push is the workflow's one privileged delivery, and
its trust shape is the reason it exists as a top-level workflow: a
workflow_call callee cannot read an environment secret (claudit's #479),
and the workflow_run trigger's hazard — another run's data reaching a
privileged job — is gated shut four ways (event, branch, conclusion,
head repository) before the artifact is even downloaded. The artifact is
data and nothing else: validated inline, executed never.
"""
import contextlib
import json
import os
import pathlib
import tempfile
import unittest

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

    def test_the_trigger_names_ci_gate_completions_only(self):
        wr = (self.wf.get("on") or self.wf.get(True) or {})["workflow_run"]
        assert wr["workflows"] == ["ci gate"], wr
        assert wr["types"] == ["completed"], wr

    def test_the_job_admits_only_this_repos_main_push_success(self):
        condition = " ".join(self.push["if"].split())
        for conjunct in (
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.head_repository.full_name =="
            " github.repository",
        ):
            assert conjunct in condition, conjunct

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
        down = step(self.wf, "Download the ratchet data")
        assert down["if"] == "steps.list.outputs.staged == 'true'"
        with_ = down["with"]
        assert with_["name"] == "ratchet-data"
        assert with_["run-id"] == "${{ github.event.workflow_run.id }}"
        assert with_["github-token"] == "${{ secrets.GITHUB_TOKEN }}"

    def test_the_validation_step_runs_before_the_push_step(self):
        names = [s.get("name") for s in self.wf["jobs"]["push"]["steps"]]
        assert names == [
            "List the triggering run's artifacts",
            "Download the ratchet data",
            "Validate the staged data",
            "Push the ratchet commit",
        ], names

    def test_the_validation_is_inline_and_complete(self):
        # No repository code: the schema check is inline jq, and it pins
        # the exact two-file shape, the 40-hex base, the exact key set and
        # finite numeric leaves.
        run = flattened(step(self.wf, "Validate the staged data")["run"])
        assert 'ls -A "${data}"' in run
        # The base check is whole-file: one read, a 40-char length gate
        # and a full-content hex match, so a garbage-suffixed line dies.
        assert 'base="$(cat "${data}/base.txt")"' in run
        assert '[ "${#base}" -eq 40 ]' in run
        assert 'grep -qE "^[0-9a-f]{40}$" <<< "${base}"' in run
        assert "ci-thresholds.json does not match the ratchet schema" in run
        assert "the ratchet artifact carries unexpected files" in run
        # Nothing from the artifact is executed: the only python-shaped
        # word in the block is the thresholds schema's own
        # `coverage.python` key inside the jq expression, no interpreter
        # is invoked, and nothing sourced or executed names the staged
        # data directory.
        assert "python3" not in run
        assert "source " not in run and ". \"${data}" not in run

    def test_no_staged_file_reaches_git_anywhere_but_the_copy(self):
        # The push step may name the staged document exactly once: the cp
        # into the scratch tree. Nothing else from the artifact is read.
        run = flattened(step(self.wf, "Push the ratchet commit")["run"])
        assert 'cp "${RUNNER_TEMP}/ratchet-data/ci-thresholds.json"' in run
        # The staged base is read as a VALUE (the staleness check), never
        # as a command.
        assert 'base="$(cat "${RUNNER_TEMP}/ratchet-data/base.txt")"' in run
        assert "eval" not in run.replace(
            'eval "$(ssh-agent -s)"', ""), (
            "the only eval is the ssh-agent bootstrap")

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
            "MASTER_PUSH_DEPLOY_KEY is empty: the main-push environment is "
            "missing its secret" in run)
        assert "github.token" not in run

    def test_the_agent_never_outlives_the_step(self):
        run = flattened(step(self.wf, "Push the ratchet commit")["run"])
        assert 'trap \'kill "$SSH_AGENT_PID" 2>/dev/null || true\' EXIT' in run
        assert "ssh-add <(printf '%s\\n' \"$MASTER_PUSH_DEPLOY_KEY\")" in run

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
    BASE = "a" * 40

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

    def _validate(self, tmp_path, threshold_bytes, base_bytes):
        step_ = step(load(), "Validate the staged data")
        data = tmp_path / "ratchet-data"
        data.mkdir()
        (data / "ci-thresholds.json").write_bytes(threshold_bytes)
        (data / "base.txt").write_bytes(base_bytes)
        return _workflowrun.run_step(tmp_path, step_,
                                     {"RUNNER_TEMP": str(tmp_path)})

    def _run_with(self, tmp_path, document, base):
        return self._validate(
            tmp_path,
            json.dumps(document).encode("utf-8"),
            base.encode("utf-8"))

    def test_the_real_shape_passes(self):
        done = self._run_with(self.enterContext(_dir()), self.VALID,
                              self.BASE)
        assert done.returncode == 0, (done.stdout, done.stderr)

    def test_wrong_leaf_keys_are_refused(self):
        document = {"coverage": {"javascript": {"a": 1, "b": 2},
                                 "python": {"floor": 1, "measured": 2}},
                    "schema_version": 1}
        done = self._run_with(self.enterContext(_dir()), document, self.BASE)
        assert done.returncode != 0, done.stdout

    def test_a_garbage_suffixed_base_is_refused(self):
        done = self._run_with(self.enterContext(_dir()), self.VALID,
                              self.BASE + "\nrm -rf /\n")
        assert done.returncode != 0, done.stdout

    def test_a_string_typed_leaf_is_refused(self):
        document = {"coverage": {"javascript": {"floor": "95", "measured": 1},
                                 "python": {"floor": 1, "measured": 2}},
                    "schema_version": 1}
        done = self._run_with(self.enterContext(_dir()), document, self.BASE)
        assert done.returncode != 0, done.stdout

    def test_a_string_schema_version_is_refused(self):
        document = dict(self.VALID, schema_version="1")
        done = self._run_with(self.enterContext(_dir()), document, self.BASE)
        assert done.returncode != 0, done.stdout

    def test_an_extra_staged_file_is_refused(self):
        tmp = self.enterContext(_dir())
        data = tmp / "ratchet-data"
        data.mkdir()
        (data / "ci-thresholds.json").write_bytes(
            b'{"coverage": {}, "schema_version": 1}')
        (data / "base.txt").write_bytes(self.BASE.encode("utf-8"))
        (data / "extra.sh").write_bytes(b"echo nope\n")
        step_ = step(load(), "Validate the staged data")
        done = _workflowrun.run_step(tmp, step_, {"RUNNER_TEMP": str(tmp)})
        assert done.returncode != 0, done.stdout


@contextlib.contextmanager
def _dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield pathlib.Path(tmp)
