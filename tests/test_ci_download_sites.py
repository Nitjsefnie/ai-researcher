"""The workflow sites of scripts/ci/download.py, executed (issue #395).

Each case runs a real `run:` block in a workspace holding copies of the real
helper; only the network boundary (urlopen) or the pip child is faked.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

import _workflowrun

REPO_ROOT = Path(__file__).resolve().parents[1]


# The `python3` a step runs: the real interpreter, with urlopen answering
# the scripted faults, then a release listing for a tag lookup and the fake
# archive for anything else; every request is recorded with where it carries
# an Authorization header.
BOUNDARY = r'''
import io, json, os, runpy, sys, time, urllib.error, urllib.request
from pathlib import Path
log = Path(os.environ["DOWNLOAD_STUB_LOG"])
faults = [int(code) for code in os.environ["DOWNLOAD_STUB_FAULTS"].split()]
asset = sys.argv[2].rsplit("/", 1)[1]
def urlopen(request, timeout):
    url = getattr(request, "full_url", request)
    held = (getattr(request, "unredirected_hdrs", {}), getattr(request, "headers", {}))
    auth = ["none", "unredirected", "redirected"][next(
        (i for i, hdrs in enumerate(held, 1) if "Authorization" in hdrs), 0)]
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps([url, auth]) + "\n")
    hit = len(log.read_text(encoding="utf-8").splitlines())
    if hit <= len(faults):
        raise urllib.error.HTTPError(url, faults[hit - 1], "fault", None, None)
    if "/releases/tags/" in url:
        return io.BytesIO(json.dumps({"assets": [{"name": asset, "id": 42}]}).encode())
    return io.BytesIO(Path(os.environ["DOWNLOAD_STUB_BODY"]).read_bytes())
urllib.request.urlopen = urlopen
time.sleep = lambda seconds: None
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
'''


def fake_tool_archive(path: Path, tool: str) -> str:
    """A tarball holding an executable `tool` that echoes its arguments."""
    script = f'#!/bin/sh\necho "fake {tool} $*"\n'.encode("utf-8")
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(tool)
        member.size, member.mode = len(script), 0o755
        archive.addfile(member, io.BytesIO(script))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkout_copy(tmp_path, boundary, fallback=None):
    """A workspace holding the real helper, and a bin dir whose `python` and
    `python3` run `boundary` (or `fallback` for any other script)."""
    workspace = tmp_path / "ws"
    for relative in ("scripts/ci/download.py", "scripts/fetch_http.py"):
        (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, workspace / relative)
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "boundary.py").write_text(boundary, encoding="utf-8")
    (stub / "fallback.py").write_text(fallback or boundary, encoding="utf-8")
    script = (f"#!/bin/sh\nif [ \"$1\" = scripts/ci/download.py ]; then\n"
              f"  exec '{sys.executable}' '{stub / 'boundary.py'}' \"$@\"\nfi\n"
              f"exec '{sys.executable}' '{stub / 'fallback.py'}' \"$@\"\n")
    for name in ("python", "python3"):
        (stub / name).write_text(script, encoding="utf-8")
        (stub / name).chmod(0o755)
    return workspace, stub


def run_site(tmp_path, workflow, job, step_name, tool, faults, run_edit=None,
             env_edit=None, token=""):
    """Run one download step in a checkout copy; return (result, requests, ws)."""
    workspace, stub = checkout_copy(tmp_path, BOUNDARY)
    body = tmp_path / "fake.tar.gz"
    digest = fake_tool_archive(body, tool)
    path = REPO_ROOT / ".github" / "workflows" / workflow
    step = dict(_workflowrun.step_by_name(path, job, step_name))
    if run_edit:
        step["run"] = run_edit(step["run"], digest)
    log = tmp_path / "urls.log"
    env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
           "DOWNLOAD_STUB_LOG": str(log), "DOWNLOAD_STUB_BODY": str(body),
           "DOWNLOAD_STUB_FAULTS": " ".join(map(str, faults)),
           "AI_RESEARCHER_DOWNLOAD_TOKEN": token}
    env.update(env_edit(yaml.safe_load(path.read_text(encoding="utf-8")),
                        digest) if env_edit else {})
    result = _workflowrun.run_step(workspace, step, env)
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, [json.loads(line) for line in lines], workspace


def gitleaks_digest(run, digest):
    edited, count = re.subn(r"\b[0-9a-f]{64}\b", digest, run)
    assert count == 1, run
    return edited


def actionlint_env(workflow, digest):
    return {**workflow["jobs"]["actionlint"]["env"],
            "AI_RESEARCHER_ACTIONLINT_SHA256": digest}


SITES = [
    ("secrets.yml", "gitleaks", "Download gitleaks and verify its digest",
     "gitleaks", {"run_edit": gitleaks_digest}),
    ("actionlint.yml", "actionlint", "Install actionlint", "actionlint",
     {"env_edit": actionlint_env}),
]
# The step after the download that executes the tool by its workspace path.
CONSUMERS = {"gitleaks": "Scan the tree and the history",
             "actionlint": "actionlint"}
LINUX = pytest.mark.skipif(sys.platform != "linux",
                           reason="the workflow step runs on Ubuntu")
TOKEN = "token-value-for-tests"


def expected_requests(requests, token):
    """Without a token: the release URL twice. With one: the tag lookup twice,
    then the asset, all on the API with the token unredirected."""
    if not token:
        url = requests[0][0]
        assert url.startswith("https://github.com/") and "/releases/download/" in url
        return [[url, "none"]] * 2
    tags = requests[0][0]
    assert tags.startswith("https://api.github.com/repos/") and "/releases/tags/" in tags
    assets = tags.split("/releases/tags/")[0] + "/releases/assets/42"
    return [[tags, "unredirected"]] * 2 + [[assets, "unredirected"]]


@LINUX
@pytest.mark.parametrize("token", ["", TOKEN])
@pytest.mark.parametrize("workflow, job, name, tool, edits", SITES)
def test_a_site_retries_a_gateway_error_then_its_consumer_runs_the_tool(
        tmp_path, workflow, job, name, tool, edits, token):
    result, requests, workspace = run_site(tmp_path, workflow, job, name, tool,
                                           [504], token=token, **edits)
    assert result.returncode == 0, result.stderr
    assert requests == expected_requests(requests, token)
    assert TOKEN not in result.stdout + result.stderr
    assert f"fake {tool} " in result.stdout
    consumer = _workflowrun.step_by_name(
        REPO_ROOT / ".github" / "workflows" / workflow, job, CONSUMERS[tool])
    consumed = _workflowrun.run_step(workspace, consumer, dict(os.environ))
    assert consumed.returncode == 0, consumed.stderr
    assert consumed.stdout.startswith(f"fake {tool} ")


@LINUX
@pytest.mark.parametrize("token", ["", TOKEN])
@pytest.mark.parametrize("workflow, job, name, tool, edits", SITES)
def test_a_site_fails_at_once_on_a_404(tmp_path, workflow, job, name, tool,
                                       edits, token):
    result, requests, _ = run_site(tmp_path, workflow, job, name, tool, [404],
                                   token=token, **edits)
    assert result.returncode != 0
    assert len(requests) == 1
    assert f"fake {tool}" not in result.stdout
    assert TOKEN not in result.stdout + result.stderr


@pytest.mark.parametrize("workflow, job, name, tool, edits", SITES)
def test_the_download_token_reaches_only_the_download_step(workflow, job, name,
                                                           tool, edits):
    document = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    steps = document["jobs"][job]["steps"]
    assert [step["name"] for step in steps
            if "AI_RESEARCHER_DOWNLOAD_TOKEN" in (step.get("env") or {})] == [name]
    for scope in (document, document["jobs"][job]):
        assert "AI_RESEARCHER_DOWNLOAD_TOKEN" not in (scope.get("env") or {})
    assert document["permissions"] == {"contents": "read"}
    assert "permissions" not in document["jobs"][job]


# download.py --run with its sleeps skipped; the pip it reruns is FAKE_PIP.
RUN_BOUNDARY = ("import runpy, sys, time\ntime.sleep = lambda seconds: None\n"
                "sys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n")
# Records its arguments; fails its first run, succeeds after.
FAKE_PIP = r'''
import json, os, sys
from pathlib import Path
log = Path(os.environ["PIP_STUB_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\n")
sys.exit(1 if len(log.read_text(encoding="utf-8").splitlines()) == 1 else 0)
'''
PIP_STEPS = [(path.name, job_id, step["name"])
             for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
             for job_id, job in (yaml.safe_load(path.read_text(encoding="utf-8"))
                                 .get("jobs") or {}).items()
             for step in job.get("steps", []) if "pip install" in step.get("run", "")]


def test_the_pip_install_sites_are_found():
    assert ("actionlint.yml", "actionlint", "Install zizmor") in PIP_STEPS


@pytest.mark.skipif(not Path("/bin/sh").is_file(),
                    reason="the stub interpreters are /bin/sh scripts")
@pytest.mark.parametrize("workflow, job, name", PIP_STEPS)
def test_every_pip_install_is_rerun_after_a_failure(tmp_path, workflow, job,
                                                    name):
    workspace, stub = checkout_copy(tmp_path, RUN_BOUNDARY, FAKE_PIP)
    log = tmp_path / "pip.log"
    step = _workflowrun.step_by_name(
        REPO_ROOT / ".github" / "workflows" / workflow, job, name)
    result = _workflowrun.run_step(workspace, step, {
        **os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "PIP_STUB_LOG": str(log)})
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line)
             for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(calls) == 2 and calls[0] == calls[1]
    assert calls[0][:3] == ["-m", "pip", "install"]
    assert "--upgrade" not in calls[0]
    if name == "Install zizmor":
        assert "--require-hashes" in calls[0]
