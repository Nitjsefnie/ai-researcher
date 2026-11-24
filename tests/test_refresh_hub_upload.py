"""Both hub jobs upload through scripts/publish_docs.py and its retry (issue #402).

Each job's real `Publish to docs-hub` step runs against a local origin, a
stale live page, and the real download.py and publish_docs.py with only
urlopen and the backoff clock faked (tests/_hubfake.py).
"""
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "scripts"), str(ROOT / "scripts/ci")]

import _hubfake  # noqa: E402  # pylint: disable=wrong-import-position
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position
import download  # noqa: E402  # pylint: disable=wrong-import-position
import publish_docs  # noqa: E402  # pylint: disable=wrong-import-position

WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/refresh.yml").read_text(encoding="utf-8"))
JOBS = {
    "hub": ("frontier-models", "publish-payload/tree/out", {
        "slug": "ai-researcher/frontier-models",
        "title": "Frontier models — intelligence vs cost per task",
        "tags": "benchmarks,comparison,interactive,ai"}),
    "rankings-hub": ("trending-rankings", "rankings-page", {
        "slug": "ai-researcher/trending-rankings",
        "title": "Trending rankings — Hugging Face, OpenRouter & GitHub top 10 over time",
        "tags": "trending,rankings,ai"}),
}


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True, timeout=60).stdout.strip()


def _publish(tmp_path, job, code, fault=128):
    """Run the job's publish step once, its first ref fetch reporting `fault`; return (result, uploads)."""
    page_name, artifact, _ = JOBS[job]
    page = f"<html>{page_name}</html>\n"
    origin = tmp_path / "origin"
    (origin / "out").mkdir(parents=True)
    (origin / f"out/{page_name}.html").write_text(page, encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main", str(origin))
    for setting in (("user.name", "fixture"), ("user.email", "fixture@example.com"),
                    ("commit.gpgsign", "false")):
        _git(origin, "config", *setting)
    _git(origin, "add", "out")
    _git(origin, "commit", "-qm", "page")
    config = tmp_path / "gitconfig"
    _git(origin, "config", "--file", str(config),
         f"url.{origin.as_uri()}.insteadOf", "https://github.com/fixture/hub")
    runner = tmp_path / "runner"
    (runner / artifact).mkdir(parents=True)
    (runner / artifact / f"{page_name}.html").write_text(page, encoding="utf-8")
    (runner / "push-data").mkdir()
    (runner / "push-data/tip.txt").write_text(_git(origin, "rev-parse", "HEAD"), encoding="utf-8")
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "live.html").write_text("previous page", encoding="utf-8")
    record = _hubfake.install(stub)
    _workflowrun.write_git_stub(stub, fault, tmp_path / "git.log")
    env = {**os.environ, "PATH": str(stub) + os.pathsep + os.environ["PATH"],
           "RUNNER_TEMP": str(runner), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
           "GITHUB_REPOSITORY": "fixture/hub", "GIT_CONFIG_GLOBAL": str(config),
           "GITHUB_WORKSPACE": str(ROOT), "DOCS_HUB_API_KEY": "fixture", "AI_RESEARCHER_LIVE_PAGE": str(stub / "live.html"),
           "AI_RESEARCHER_UPLOAD_CODE": code, "AI_RESEARCHER_UPLOAD_BODY": '{"error":"refused"}' if code == "400" else "{}"}
    entry = [s for s in WORKFLOW["jobs"][job]["steps"] if s.get("name") == "Publish to docs-hub"]
    assert len(entry) == 1
    return _workflowrun.run_step(tmp_path, entry[0], env), _hubfake.uploads(record)


@pytest.mark.skipif(os.name == "nt", reason="workflow shell runs on Ubuntu")
@pytest.mark.parametrize("job", sorted(JOBS))
def test_a_transient_5xx_is_retried_and_the_page_uploaded(tmp_path, job):
    done, uploads = _publish(tmp_path, job, "503,200")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "retrying in 5s" in done.stderr
    assert len((tmp_path / "git.log").read_text(encoding="utf-8").splitlines()) == 2  # exit 128 reran the fetch
    page_name, _, fields = JOBS[job]
    assert len(uploads) == 2
    for upload in uploads:
        assert upload == {
            "key": "fixture", "timeout": publish_docs.UPLOAD_TIMEOUT,
            "fields": {**fields, "project": "ai-researcher", "from": "ai-researcher"},
            "filename": f"{page_name}.html", "type": "text/html",
            "page": f"<html>{page_name}</html>\n"}


@pytest.mark.skipif(os.name == "nt", reason="workflow shell runs on Ubuntu")
@pytest.mark.parametrize("job", sorted(JOBS))
def test_a_refusal_fails_the_step_at_once_with_the_hubs_body(tmp_path, job):
    done, uploads = _publish(tmp_path, job, "400")
    assert done.returncode == 1, done.stdout + done.stderr
    assert len(uploads) == 1
    assert "publish failed: HTTP 400" in done.stderr
    assert '{"error":"refused"}' in done.stderr


@pytest.mark.skipif(os.name == "nt", reason="workflow shell runs on Ubuntu")
@pytest.mark.parametrize("job", sorted(JOBS))
def test_a_hub_that_never_answers_fails_after_the_window(tmp_path, job):
    done, uploads = _publish(tmp_path, job, "transport")
    assert done.returncode == 1, done.stdout + done.stderr
    assert len(uploads) == 8
    assert "publish failed after 8 attempts in 255s: cannot reach" in done.stderr


@pytest.mark.skipif(os.name == "nt", reason="workflow shell runs on Ubuntu")
@pytest.mark.parametrize("job", sorted(JOBS))
def test_a_ref_fetch_failing_otherwise_is_not_rerun(tmp_path, job):
    done, uploads = _publish(tmp_path, job, "200", fault=1)  # rankings-hub concedes, hub fails red
    fetches = (tmp_path / "git.log").read_text(encoding="utf-8").splitlines()
    assert (done.returncode, uploads, len(fetches)) == ({"hub": 1, "rankings-hub": 0}[job], [], 1)


@pytest.mark.parametrize("job", sorted(JOBS))
def test_each_hub_checks_out_the_client_and_outlasts_its_retry(job):
    steps = WORKFLOW["jobs"][job]["steps"]
    names = [s.get("name") for s in steps]
    checkouts = [i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 1 and checkouts[0] < names.index("Publish to docs-hub")
    # Each artifact's 75 s of pauses, then the ref fetch's window, the live page's and the upload's, whose last
    # attempt may wait its whole timeout.
    artifacts = sum(s.get("uses") == _workflowrun.DOWNLOAD_ARTIFACT for s in steps)
    assert artifacts and WORKFLOW["jobs"][job]["timeout-minutes"] * 60 > (
        75 * artifacts + 3 * download.WINDOW_SECONDS + publish_docs.UPLOAD_TIMEOUT)
