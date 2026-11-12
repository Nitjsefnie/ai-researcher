"""Both hub jobs upload through scripts/publish_docs.py and its retry (issue #402).

Each job's real `Publish to docs-hub` step runs against a local origin, a
stub curl serving a stale live page, and the real publish_docs.py with only
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
LIVE_CURL = """import pathlib, sys
args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith('https://'))
if url != 'https://docs.nitjsefni.eu/d/ai-researcher/' + pathlib.Path(sys.argv[0]).stem[5:]:
    raise SystemExit('unexpected curl endpoint: ' + url)
open(args[args.index('-o') + 1], 'w', encoding='utf-8').write('previous page')
"""


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True, timeout=60).stdout.strip()


def _publish(tmp_path, job, code):
    """Run the job's publish step once; return (result, uploads)."""
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
    (stub / f"curl.{page_name}.py").write_text(LIVE_CURL, encoding="utf-8")
    (stub / "curl").write_text(f"#!/bin/sh\nexec '{sys.executable}' "
                               f"'{stub / f'curl.{page_name}.py'}' \"$@\"\n", encoding="utf-8")
    (stub / "curl").chmod(0o755)
    record = _hubfake.install(stub)
    env = {**os.environ, "PATH": str(stub) + os.pathsep + os.environ["PATH"],
           "RUNNER_TEMP": str(runner), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
           "GITHUB_REPOSITORY": "fixture/hub", "GIT_CONFIG_GLOBAL": str(config),
           "GITHUB_WORKSPACE": str(ROOT), "DOCS_HUB_API_KEY": "fixture",
           "UPLOAD_CODE": code, "UPLOAD_BODY": '{"error":"refused"}' if code == "400" else "{}"}
    entry = [s for s in WORKFLOW["jobs"][job]["steps"] if s.get("name") == "Publish to docs-hub"]
    assert len(entry) == 1
    return _workflowrun.run_step(tmp_path, entry[0], env), _hubfake.uploads(record)


@pytest.mark.skipif(os.name == "nt", reason="workflow shell runs on Ubuntu")
@pytest.mark.parametrize("job", sorted(JOBS))
def test_a_transient_5xx_is_retried_and_the_page_uploaded(tmp_path, job):
    done, uploads = _publish(tmp_path, job, "503,200")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "retrying in 5s" in done.stderr
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


@pytest.mark.parametrize("job", sorted(JOBS))
def test_each_hub_checks_out_the_client_and_outlasts_its_retry(job):
    steps = WORKFLOW["jobs"][job]["steps"]
    names = [s.get("name") for s in steps]
    checkouts = [i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 1 and checkouts[0] < names.index("Publish to docs-hub")
    # The last attempt starts inside the window and may wait its whole timeout.
    assert WORKFLOW["jobs"][job]["timeout-minutes"] * 60 > (
        download.WINDOW_SECONDS + publish_docs.UPLOAD_TIMEOUT)
