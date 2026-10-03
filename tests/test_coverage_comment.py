"""The trusted commenter executes its contract, not its source text.

The `coverage comment` workflow is the one holder of `pull-requests: write`,
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
    env = {
        "PATH": f"{workdir / 'bin'}:{_system_path()}",
        "STUB_STATE": str(state),
        "STUB_CALLS": str(calls),
        "GITHUB_OUTPUT": str(workdir / "github-output"),
        "GH_TOKEN": "stub-token",
        "REPO": "Nitjsefnie/ai-researcher",
        "HEAD_SHA": "a" * 40,
        "PR_NUMBER": "7",
        "RUN_ID": "1234",
    }
    env.update(extra)
    return env


def _system_path():
    for entry in os.environ.get("PATH", "").split(":"):
        if (Path(entry) / "jq").exists():
            return entry
    raise AssertionError("jq must be on the ambient PATH")


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
