"""The trusted commenter executes its contract, not its source text.

The `coverage comment` workflow holds `pull-requests: write` — shared, since
issue #161, with the claim action's job, which also never checks out the tree —
so its steps run here against a stub `gh` — posting only where the event's
own pull request says to, updating one numbered comment in place, refusing
an artifact that names a different pull request, and publishing a check
that says plainly when coverage was not measured.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "coverage-comment.yml"
MARKER = "<!-- ai-researcher-diff-coverage -->"
BODY = "### Coverage of this change\n\n**100.0%** of added lines covered."


def _workdir(tmp_path):
    workdir = tmp_path / "run"
    bin_dir = workdir / "bin"
    workdir.mkdir(parents=True)
    state = workdir / "state.json"
    calls = workdir / "calls.jsonl"
    _workflowrun.write_gh_stub(bin_dir, state, calls)
    return workdir, state, calls


def _state(state_path, **values):
    current = json.loads(state_path.read_text(encoding="utf-8"))
    current.update(values)
    state_path.write_text(json.dumps(current), encoding="utf-8")
    return state_path


def _env(workdir, state, calls, **extra):
    # The stub directory PREPENDED to the ambient PATH, with the ambient
    # separator: every matrix OS resolves cat/wc/jq from its own PATH, and
    # the stub shadows a real gh by search order alone.
    env = {
        "PATH": os.pathsep.join([
            str(workdir / "bin"), os.environ.get("PATH", "")]),
        "STUB_STATE": str(state),
        "STUB_CALLS": str(calls),
        "GITHUB_OUTPUT": str(workdir / "github-output"),
        "GH_TOKEN": "stub-token",
        "REPO": "Nitjsefnie/ai-researcher",
        "HEAD_SHA": "a" * 40,
        "PR_NUMBER": "7",
        "RUN_ID": "1234",
        "HEAD_REPO": "Nitjsefnie/ai-researcher",
        "HEAD_BRANCH": "patch-coverage-126",
        "EVENT_NUMBERS": "[7]",
    }
    env.update(extra)
    return env


def _outputs(workdir):
    output = workdir / "github-output"
    if not output.exists():
        return {}
    text = output.read_text(encoding="utf-8")
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def _run(workdir, state, calls, name, env):
    step = _workflowrun.step_by_name(WORKFLOW, "comment", name)
    return _workflowrun.run_step(workdir, step, env)


def test_an_unexpired_artifact_is_found_and_an_expired_one_is_not(tmp_path):
    cases = (
        ("unexpired", [{"name": "diff-coverage-comment",
                        "expired": False}], "true"),
        ("expired", [{"name": "diff-coverage-comment",
                      "expired": True}], "false"),
        ("other-name", [{"name": "coverage-xml", "expired": False}], "false"),
        ("absent", [], "false"),
    )
    for label, artifacts, expected in cases:
        workdir, state, calls = _workdir(tmp_path / label)
        _state(state, artifacts=artifacts)
        done = _run(workdir, state, calls, "Check for the comment artifact",
                    _env(workdir, state, calls))
        assert done.returncode == 0, done.stderr
        # Absent is signaled by NO output, not by `present=false`: the
        # downstream conditions all read `!= 'true'`.
        assert _outputs(workdir).get("present") == (
            expected if expected == "true" else None), done.stderr


def test_a_post_happens_when_no_marker_comment_exists(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, comments=[])
    (workdir / "body.md").write_text(BODY, encoding="utf-8")
    (workdir / "pr-number.txt").write_text("7\n", encoding="utf-8")
    done = _run(workdir, state, calls,
                "Post or update the pull request comment",
                _env(workdir, state, calls))
    assert done.returncode == 0, (done.stdout, done.stderr)
    writes = _workflowrun.recorded_writes(calls)
    assert len(writes) == 1 and '"POST"' in writes[0], writes
    comments = json.loads(
        state.read_text(encoding="utf-8"))["comments"]
    assert comments[0]["body"].startswith(MARKER), comments[0]
    assert "a" * 40 in comments[0]["body"], comments[0]
    assert BODY in comments[0]["body"], comments[0]


def test_a_later_push_updates_one_comment_in_place(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, comments=[
        {"id": 11, "user": {"login": "github-actions[bot]"},
         "body": f"{MARKER}\n\nPatch coverage for commit {'b' * 40}."},
        {"id": 12, "user": {"login": "a-human"}, "body": "looks low"},
    ])
    (workdir / "body.md").write_text(BODY, encoding="utf-8")
    (workdir / "pr-number.txt").write_text("7\n", encoding="utf-8")
    done = _run(workdir, state, calls,
                "Post or update the pull request comment",
                _env(workdir, state, calls))
    assert done.returncode == 0, (done.stdout, done.stderr)
    writes = _workflowrun.recorded_writes(calls)
    # One PATCH to the marker comment's own id; the human's comment and the
    # comment count are untouched.
    assert len(writes) == 1 and '"PATCH"' in writes[0], writes
    assert "/issues/comments/11" in writes[0], writes
    state_now = json.loads(state.read_text(encoding="utf-8"))
    assert len(state_now["comments"]) == 2, state_now["comments"]
    assert state_now["comments"][0]["body"].startswith(MARKER)
    assert BODY in state_now["comments"][0]["body"], state_now


def test_an_artifact_naming_another_pull_request_is_refused(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, comments=[])
    (workdir / "body.md").write_text(BODY, encoding="utf-8")
    (workdir / "pr-number.txt").write_text("999\n", encoding="utf-8")
    done = _run(workdir, state, calls,
                "Post or update the pull request comment",
                _env(workdir, state, calls))
    assert done.returncode != 0, done.stdout
    assert "refusing to post" in done.stderr, done.stderr
    assert _workflowrun.recorded_writes(calls) == [], "a write escaped"


def test_an_oversized_body_is_refused_not_trimmed(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, comments=[])
    (workdir / "body.md").write_text("x" * 60001, encoding="utf-8")
    (workdir / "pr-number.txt").write_text("7\n", encoding="utf-8")
    done = _run(workdir, state, calls,
                "Post or update the pull request comment",
                _env(workdir, state, calls))
    assert done.returncode != 0, done.stdout
    assert "past the comment limit" in done.stderr, done.stderr
    assert _workflowrun.recorded_writes(calls) == [], "a write escaped"


def test_a_stale_run_posts_nothing(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="b" * 40, comments=[])
    (workdir / "body.md").write_text(BODY, encoding="utf-8")
    (workdir / "pr-number.txt").write_text("7\n", encoding="utf-8")
    done = _run(workdir, state, calls,
                "Post or update the pull request comment",
                _env(workdir, state, calls))
    assert done.returncode == 0, done.stderr
    assert "stale" in done.stdout, done.stdout
    assert _workflowrun.recorded_writes(calls) == [], "a write escaped"


def test_a_cancelled_run_marks_an_existing_comment_not_measured(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, comments=[
        {"id": 11, "user": {"login": "github-actions[bot]"},
         "body": f"{MARKER}\n\nPatch coverage for commit {'b' * 40}."},
    ])
    done = _run(workdir, state, calls, "Mark missing patch coverage",
                _env(workdir, state, calls, RUN_CONCLUSION="cancelled"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    outputs = _outputs(workdir)
    assert outputs["skipped"] == "true", outputs
    assert outputs["not_measured_reason"] == "a cancelled tests run", outputs
    # The verdict is EMPTIED, not absent: the default is `failure`, and a
    # cancelled run must not turn into a failed check.
    assert outputs.get("verdict", "missing") == "", outputs
    state_now = json.loads(state.read_text(encoding="utf-8"))
    assert "was not measured" in state_now["comments"][0]["body"], state_now
    assert f"{'a' * 40}" in state_now["comments"][0]["body"], state_now


def test_a_cancelled_run_with_no_prior_comment_writes_nothing(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, comments=[])
    done = _run(workdir, state, calls, "Mark missing patch coverage",
                _env(workdir, state, calls, RUN_CONCLUSION="cancelled"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert "no patch-coverage marker to update" in done.stdout, done.stdout
    assert _workflowrun.recorded_writes(calls) == [], "a write escaped"


DOCS_ONLY_JOBS = [
    {"name": "classify", "conclusion": "success"},
    {"name": "tests", "conclusion": "skipped"},
    {"name": "lint", "conclusion": "skipped"},
    {"name": "actionlint", "conclusion": "success"},
    {"name": "aggregate", "conclusion": "success"},
]
FULL_RUN_JOBS = [
    {"name": "classify", "conclusion": "success"},
    {"name": "tests", "conclusion": "success"},
    {"name": "aggregate", "conclusion": "success"},
]


def test_a_docs_only_run_marks_an_existing_comment_not_measured(tmp_path):
    # Since #133 the tests leg narrows under ci-gate's classification, so
    # a SUCCESSFUL run without the artifact is the narrowed shape when
    # its tests leg skipped: coverage was deliberately not measured, the
    # check goes neutral (never red), and the stale number is replaced.
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, jobs=DOCS_ONLY_JOBS, comments=[
        {"id": 11, "user": {"login": "github-actions[bot]"},
         "body": f"{MARKER}\n\nPatch coverage for commit {'b' * 40}."},
    ])
    done = _run(workdir, state, calls, "Mark missing patch coverage",
                _env(workdir, state, calls, RUN_CONCLUSION="success"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    outputs = _outputs(workdir)
    assert outputs["skipped"] == "true", outputs
    assert outputs["not_measured_reason"] == (
        "the tests leg was skipped by the ci-gate classification"), outputs
    # The verdict is EMPTIED, not absent: the default is `failure`, and a
    # narrowed docs-only run must not turn into a failed check.
    assert outputs.get("verdict", "missing") == "", outputs
    state_now = json.loads(state.read_text(encoding="utf-8"))
    assert "was not measured" in state_now["comments"][0]["body"], state_now
    assert f"{'a' * 40}" in state_now["comments"][0]["body"], state_now


def test_a_docs_only_run_with_no_prior_comment_writes_nothing(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, jobs=DOCS_ONLY_JOBS, comments=[])
    done = _run(workdir, state, calls, "Mark missing patch coverage",
                _env(workdir, state, calls, RUN_CONCLUSION="success"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert "no patch-coverage marker to update" in done.stdout, done.stdout
    assert _workflowrun.recorded_writes(calls) == [], "a write escaped"


def test_a_successful_run_whose_tests_leg_ran_keeps_the_failure_default(tmp_path):
    # A successful run whose tests leg RAN always carries the artifact
    # (diff-coverage uploads with if-no-files-found: error), so a missing
    # artifact beside a running tests leg is the true-failure shape and
    # the default verdict stands.
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, jobs=FULL_RUN_JOBS, comments=[
        {"id": 11, "user": {"login": "github-actions[bot]"},
         "body": f"{MARKER}\n\nPatch coverage for commit {'b' * 40}."},
    ])
    done = _run(workdir, state, calls, "Mark missing patch coverage",
                _env(workdir, state, calls, RUN_CONCLUSION="success"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    outputs = _outputs(workdir)
    assert "skipped" not in outputs, outputs
    assert outputs.get("verdict", "failure") == "failure", outputs


def test_a_successful_run_without_a_tests_leg_is_refused(tmp_path):
    # Fail closed: a jobs list the step cannot read the tests leg out of
    # is a shape this harness never modelled, not a narrowed run.
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, jobs=[
        {"name": "classify", "conclusion": "success"},
        {"name": "aggregate", "conclusion": "success"},
    ], comments=[])
    done = _run(workdir, state, calls, "Mark missing patch coverage",
                _env(workdir, state, calls, RUN_CONCLUSION="success"))
    assert done.returncode != 0, (done.stdout, done.stderr)
    assert "names no tests leg" in done.stderr, done.stderr


def test_the_check_publishes_on_the_pull_request_head(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, checks=[])
    done = _run(workdir, state, calls, "Publish coverage check",
                _env(workdir, state, calls, STATUS="success",
                     JOB_SKIPPED="", NOT_MEASURED_REASON="", VERDICT="",
                     RUN_URL="https://github.invalid/runs/1"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    writes = _workflowrun.recorded_writes(calls)
    assert len(writes) == 1 and '"POST"' in writes[0], writes
    state_now = json.loads(state.read_text(encoding="utf-8"))
    [check] = state_now["checks"]
    assert check["name"] == "coverage comment", check
    assert check["external_id"] == (
        f"ai-researcher-coverage-comment/v1/{'a' * 40}"), check
    assert check["head_sha"] == "a" * 40, check
    assert check["conclusion"] == "success", check


def test_a_skipped_measurement_publishes_a_neutral_check(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, checks=[])
    done = _run(workdir, state, calls, "Publish coverage check",
                _env(workdir, state, calls, STATUS="success",
                     JOB_SKIPPED="true",
                     NOT_MEASURED_REASON="a cancelled tests run",
                     VERDICT="",
                     RUN_URL="https://github.invalid/runs/1"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    state_now = json.loads(state.read_text(encoding="utf-8"))
    [check] = state_now["checks"]
    assert check["conclusion"] == "neutral", check
    assert "a cancelled tests run" in check["output[summary]"], check


def test_a_neutral_verdict_without_a_reason_is_refused(tmp_path):
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, checks=[])
    done = _run(workdir, state, calls, "Publish coverage check",
                _env(workdir, state, calls, STATUS="success",
                     JOB_SKIPPED="true", NOT_MEASURED_REASON="", VERDICT="",
                     RUN_URL="https://github.invalid/runs/1"))
    assert done.returncode != 0, done.stdout
    assert "not_measured_reason" in done.stderr, done.stderr


def test_the_resolver_takes_the_event_pull_request(tmp_path):
    """A non-fork run resolves its number from the event's own list."""
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40)
    done = _run(workdir, state, calls,
                "Resolve the target pull request from the event",
                _env(workdir, state, calls, EVENT_NUMBERS="[7]"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    outputs = _outputs(workdir)
    assert outputs["number"] == "7", outputs
    assert outputs["stale"] == "false", outputs


def test_the_resolver_falls_back_to_a_base_namespace_head_label(tmp_path):
    """A fork run resolves in the BASE repository's number namespace.

    The lookup is `repos/<base>/pulls?head=<owner>:<branch>` — never a
    commit association on the head repository, whose answer can be a
    fork-local pull request number (review finding F3, observed live).
    """
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, pulls=[
        {"number": 7, "head": {"sha": "a" * 40,
                               "repo": {"full_name": "forker/ai-researcher"},
                               "ref": "patch"},
         "base": {"repo": {"full_name": "Nitjsefnie/ai-researcher"}}},
        # A fork-local pull request with a colliding number cannot appear:
        # the query names the base repository.
    ])
    done = _run(workdir, state, calls,
                "Resolve the target pull request from the event",
                _env(workdir, state, calls, EVENT_NUMBERS="[]",
                     HEAD_REPO="forker/ai-researcher",
                     HEAD_BRANCH="patch"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert _outputs(workdir)["number"] == "7", done.stderr


def test_the_resolver_without_any_pull_request_posts_nothing(tmp_path):
    """No open pull request for the head is a real state, not an error."""
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, pulls=[])
    done = _run(workdir, state, calls,
                "Resolve the target pull request from the event",
                _env(workdir, state, calls, EVENT_NUMBERS="[]",
                     HEAD_REPO="forker/ai-researcher",
                     HEAD_BRANCH="patch"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert _outputs(workdir).get("present") == "false"


def test_the_resolver_refuses_an_ambiguous_head(tmp_path):
    """Two open pull requests on one fork branch cannot be told apart."""
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="a" * 40, pulls=[
        {"number": 7}, {"number": 8}])
    done = _run(workdir, state, calls,
                "Resolve the target pull request from the event",
                _env(workdir, state, calls, EVENT_NUMBERS="[]",
                     HEAD_REPO="forker/ai-researcher",
                     HEAD_BRANCH="patch"))
    assert done.returncode != 0, done.stdout
    assert "found 2" in done.stderr, done.stderr


def test_the_resolver_calls_a_moved_head_stale(tmp_path):
    """A run whose head no longer is the pull request's head is stale."""
    workdir, state, calls = _workdir(tmp_path)
    _state(state, head_sha="b" * 40)
    done = _run(workdir, state, calls,
                "Resolve the target pull request from the event",
                _env(workdir, state, calls, EVENT_NUMBERS="[7]"))
    assert done.returncode == 0, (done.stdout, done.stderr)
    outputs = _outputs(workdir)
    assert outputs["stale"] == "true", outputs
    assert "number" not in outputs, outputs
