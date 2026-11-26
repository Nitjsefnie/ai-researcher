"""The workflow sites of scripts/ci/download.py, executed.

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
import subprocess
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
    """A workspace holding the real helper, and a bin dir whose `python`,
    `python3` and `zizmor` run `boundary` (or `fallback` for any other script)."""
    workspace = tmp_path / "ws"
    for relative in ("scripts/ci/download.py", "scripts/fetch_http.py",
                     ".github/scripts/gitleaks_scan.sh", ".github/scripts/retry.sh"):
        (workspace / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / relative, workspace / relative)
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "boundary.py").write_text(boundary, encoding="utf-8")
    (stub / "fallback.py").write_text(fallback or boundary, encoding="utf-8")
    script = (f"#!/bin/sh\nif [ \"$1\" = scripts/ci/download.py ]; then\n"
              f"  exec '{sys.executable}' '{stub / 'boundary.py'}' \"$@\"\nfi\n"
              f"exec '{sys.executable}' '{stub / 'fallback.py'}' \"$@\"\n")
    for name in ("python", "python3", "zizmor"):
        (stub / name).write_text(script, encoding="utf-8")
        (stub / name).chmod(0o755)
    return workspace, stub


def run_site(tmp_path, workflow, job, step_name, tool, faults, run_edit=None, env_edit=None, token=""):
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
    env.update(env_edit(yaml.safe_load(path.read_text(encoding="utf-8")), digest) if env_edit else {})
    result = _workflowrun.run_step(workspace, step, env)
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, [json.loads(line) for line in lines], workspace


def gitleaks_digest(run, digest):
    edited, count = re.subn(r"\b[0-9a-f]{64}\b", digest, run)
    assert count == 1, run
    return edited


def actionlint_env(workflow, digest):
    return {**workflow["jobs"]["actionlint"]["env"], "AI_RESEARCHER_ACTIONLINT_SHA256": digest}


SITES = [
    ("secrets.yml", "gitleaks", "Download gitleaks and verify its digest",
     "gitleaks", {"run_edit": gitleaks_digest}),
    ("actionlint.yml", "actionlint", "Install actionlint", "actionlint",
     {"env_edit": actionlint_env}),
]
# The step after the download that executes the tool by its workspace path.
CONSUMERS = {"gitleaks": "Scan the tree and the history", "actionlint": "actionlint"}
LINUX = pytest.mark.skipif(sys.platform != "linux", reason="the workflow step runs on Ubuntu")
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
    # The scan reads the base branch's config from origin; the workspace serves as its own.
    for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "base"],
                 ["remote", "add", "origin", str(workspace)]):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                       cwd=workspace, check=True)
    consumed = _workflowrun.run_step(workspace, consumer, {**os.environ, "AI_RESEARCHER_BASE_REF": "main"})
    assert consumed.returncode == 0, consumed.stderr
    assert consumed.stdout.startswith(f"fake {tool} ")


@LINUX
@pytest.mark.parametrize("token", ["", TOKEN])
@pytest.mark.parametrize("workflow, job, name, tool, edits", SITES)
def test_a_site_fails_at_once_on_a_404(tmp_path, workflow, job, name, tool, edits, token):
    result, requests, _ = run_site(tmp_path, workflow, job, name, tool, [404], token=token, **edits)
    assert result.returncode != 0
    assert len(requests) == 1
    assert f"fake {tool}" not in result.stdout
    assert TOKEN not in result.stdout + result.stderr


@pytest.mark.parametrize("workflow, job, name, tool, edits", SITES)
def test_the_download_token_reaches_only_the_download_step(workflow, job, name, tool, edits):
    document = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    steps = document["jobs"][job]["steps"]
    assert [step["name"] for step in steps
            if "AI_RESEARCHER_DOWNLOAD_TOKEN" in (step.get("env") or {})] == [name]
    for scope in (document, document["jobs"][job]):
        assert "AI_RESEARCHER_DOWNLOAD_TOKEN" not in (scope.get("env") or {})
    assert document["permissions"] == {"contents": "read"}
    assert "permissions" not in document["jobs"][job]


# download.py --run, sleeps skipped and --timeout cut 30x; the pip or zizmor it reruns is FAKE_TOOL.
RUN_BOUNDARY = ("import runpy, subprocess, sys, time\ntime.sleep = lambda seconds: None\nrun = subprocess.run\n"
                "subprocess.run = lambda *a, timeout=None, **k: run(*a, timeout=timeout and timeout / 30, **k)\n"
                "sys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n")
# Records its arguments; exits each status in STUB_EXITS in turn ("hang": 99 after 60 s), then 0.
FAKE_TOOL = r'''
import json, os, sys, time
from pathlib import Path
log, exits = Path(os.environ["STUB_LOG"]), os.environ["STUB_EXITS"].split()
runs = len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\n")
runs < len(exits) and exits[runs] == "hang" and (time.sleep(60), sys.exit(99))
sys.exit(int(exits[runs]) if runs < len(exits) else 0)
'''
PIP_STEPS = [(path.name, job_id, step["name"])
             for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
             for job_id, job in (yaml.safe_load(path.read_text(encoding="utf-8"))
                                 .get("jobs") or {}).items()
             for step in job.get("steps", []) if "pip install" in step.get("run", "")]
SH = pytest.mark.skipif(not Path("/bin/sh").is_file(), reason="the stub interpreters are /bin/sh scripts")


def run_stubbed(tmp_path, workflow, job, name, exits, fault=None, **env):
    """Run one step whose tool is FAKE_TOOL (and git, given a fault, write_git_stub's); return (result, the tool's calls)."""
    workspace, stub = checkout_copy(tmp_path, RUN_BOUNDARY, FAKE_TOOL)
    if fault:
        _workflowrun.write_git_stub(stub, fault, tmp_path / "git.log")
    log = tmp_path / "calls.log"
    step = _workflowrun.step_by_name(REPO_ROOT / ".github" / "workflows" / workflow, job, name)
    result = _workflowrun.run_step(workspace, step, {
        **os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "GH_TOKEN": TOKEN, "STUB_LOG": str(log), "STUB_EXITS": exits, **env})
    return result, [json.loads(line) for line in (log.read_text(encoding="utf-8") if log.exists() else "").splitlines()]


def test_the_pip_install_sites_are_found():
    assert ("actionlint.yml", "actionlint", "Install zizmor") in PIP_STEPS


@SH
@pytest.mark.parametrize("workflow, job, name", PIP_STEPS)
def test_every_pip_install_is_rerun_after_a_failure(tmp_path, workflow, job, name):
    result, calls = run_stubbed(tmp_path, workflow, job, name, "1 0 1")
    assert result.returncode == 0, result.stderr  # types.yml then reruns pyright's first start too (issue #426)
    assert calls == [calls[0]] * 2 + [["-m", "pyright", "--version"]] * 2 * (workflow == "types.yml")
    assert calls[0][:3] == ["-m", "pip", "install"]
    assert "--upgrade" not in calls[0]
    if name == "Install zizmor":
        assert "--require-hashes" in calls[0]


# zizmor's error exit 1 (an online audit's network failure) and a hung run --timeout kills
# are rerun; findings (11-14) return at once, even after a rerun (issue #426).
@SH
@pytest.mark.parametrize("exits, status, runs", [
    ("1 1", 0, 3), ("13", 13, 1), ("1 14", 14, 2), ("11", 11, 1), ("hang", 0, 2)])
def test_the_zizmor_step_reruns_an_error_and_fails_a_finding_at_once(tmp_path, exits, status, runs):
    result, calls = run_stubbed(tmp_path, "actionlint.yml", "actionlint", "zizmor", exits)
    assert result.returncode == status, result.stderr
    assert calls == [["--no-progress", ".github/workflows/", ".github/actions/"]] * runs


# download.py's clock stands still; each sleep is one line in $PAUSES.
PAUSE_BOUNDARY = ("import importlib, os, sys, types; sys.path.insert(0, 'scripts/ci'); d = importlib.import_module('download')\n"
                  "log = open(os.environ['PAUSES'], 'a', encoding='utf-8')\n"
                  "d.time = types.SimpleNamespace(monotonic=lambda: 1000.0, sleep=lambda s: print(s, file=log)); sys.exit(d.main(sys.argv[2:]))\n")


def run_download_action(tmp_path, inputs, failures):
    """Run the download action's steps as the runner does: file order, each `if` under the implicit success(), a
    continue-on-error failure leaving it true. The wrapped download fails its first `failures` calls; the pauses run."""
    workspace, stub = checkout_copy(tmp_path, PAUSE_BOUNDARY)
    env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}", "GITHUB_WORKSPACE": str(workspace), "PAUSES": str(tmp_path / "pauses")}
    outcomes, calls, stderr, succeeded = {}, [], "", True
    for step in yaml.safe_load(_workflowrun.ARTIFACT_ACTION.read_text(encoding="utf-8"))["runs"]["steps"]:
        wanted = re.fullmatch(r"steps\.(\w+)\.outcome == 'failure'", step["if"]) if "if" in step else None
        assert wanted or "if" not in step, step
        if not succeeded or wanted and outcomes.get(wanted[1]) != "failure":
            continue
        given = {key: re.sub(r"\$\{\{ inputs\.(\w+) \}\}", lambda m: inputs[m[1]], value)
                 for key, value in step["with" if "uses" in step else "env"].items()}
        if "uses" in step:
            assert step["uses"].startswith("actions/download-artifact@"), step
            calls.append(given)
            failed = len(calls) <= failures
        else:
            assert step["shell"] == "bash", step
            done = _workflowrun.run_step(workspace, {**step, "shell": "bash --noprofile --norc -eo pipefail {0}"}, {**env, **given})
            failed, stderr = done.returncode != 0, stderr + done.stderr
        outcomes[step.get("id")] = "failure" if failed else "success"
        succeeded = not failed or step.get("continue-on-error") is True
    return succeeded, calls, stderr, [int(line) for line in (tmp_path / "pauses").read_text(encoding="utf-8").split()] if stderr else []


# An empty artifact list fails the wrapped action like any other error: each of five attempts gets the same inputs,
# 75 s of pauses lie between them, and a fifth failure is the step's.
@SH
@pytest.mark.parametrize("failures", range(6))
def test_the_download_action_retries_a_failed_download_and_fails_after_the_fifth(tmp_path, failures):
    inputs, pauses = {"name": "push  data", "path": "/runner/temp/push data"}, [5, 10, 20, 40][:failures]
    assert run_download_action(tmp_path, inputs, failures) == (failures < 5, [inputs] * min(failures + 1, 5), "".join(
        f"artifact push  data: attempt {n} failed (its error is above); retrying in {s}s\n" for n, s in enumerate(pauses, 1)), pauses)


# audit.yml's pip-audit: its first $FAILURES runs print $OUT and $ERR and exit 1, later runs are clean. Only
# download.py's own clock is faked, so every wait counts toward the window without being slept.
PIP_AUDIT = ('#!/bin/sh\nn=$(($(cat "$RUNS" 2>/dev/null || echo 0) + 1)); echo "$n" > "$RUNS"\n'
             '[ "$n" -gt "$FAILURES" ] && exit 0\nprintf "$OUT"; printf "$ERR" >&2; exit 1\n')
CLOCK_BOUNDARY = ("import importlib, sys, types; sys.path.insert(0, 'scripts/ci'); d = importlib.import_module('download')\n"
                  "w = []; d.time = types.SimpleNamespace(sleep=w.append, monotonic=lambda: sum(w)); sys.exit(d.main(sys.argv[2:]))\n")


# pip-audit reruns only on what the classifier calls transient, read over stdout and stderr both (issue #128);
# a finding, or a transient beside another 4xx, fails at once; five instant failures fill the 75 s window, 300 s eight.
@SH
@pytest.mark.parametrize("out, err, failures, runs, status", [
    ("requests 2.19.0 PYSEC-2018-28 2.20.0\\n", "Found 1 known vulnerability in 1 package\\n", 9, 1, 1),
    ("", "503 Server Error: Service Unavailable\\n", 1, 2, 0), ("503 Server Error\\n", "", 1, 2, 0),
    ("", "403 Client Error: Forbidden\\nConnection reset by peer\\n", 9, 1, 1), ("", "403 Client Error\\n429 Too Many Requests\\n", 1, 2, 0),
    ("", "Read timed out.\\n", 9, 5, 1), ("", "Could not connect to PyPI's vulnerability feed\\n", 1, 2, 0),
    ("", "ssl.SSLError: bad handshake\\n", 1, 2, 0), ("", "pip_audit._service.interface.ServiceError: boom\\n", 1, 2, 0),
    ("", "Temporary failure in name resolution\\n", 1, 2, 0)])
def test_the_pip_audit_step_reruns_only_a_transient_failure(tmp_path, out, err, failures, runs, status):
    workspace, stub = checkout_copy(tmp_path, CLOCK_BOUNDARY)
    (workspace / "requirements-x.txt").write_text("x==1\n", encoding="utf-8")
    (stub / "pip-audit").write_text(PIP_AUDIT, encoding="utf-8")
    (stub / "pip-audit").chmod(0o755)
    step = _workflowrun.step_by_name(REPO_ROOT / ".github" / "workflows" / "audit.yml", "pip-audit", "Audit dependencies")
    result = _workflowrun.run_step(workspace, step, {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
                                   "RUNS": str(tmp_path / "runs"), "FAILURES": str(failures), "OUT": out, "ERR": err})
    assert (result.returncode, int((tmp_path / "runs").read_text(encoding="utf-8"))) == (status, runs), result.stderr


# The ratchet guard's history fetch on a real shallow clone, per event route: the first fetch unshallows it, then
# reports the fault. Exit 128 reruns it without --unshallow, which would now exit 128 for good; 1 fails at once.
# check_ratchets.py runs once on a complete history, and its own exit 1 is the step's, never rerun.
@SH
@pytest.mark.parametrize("event, fault, verdict, fetches, status", [
    ("pull_request", 128, "", ["--unshallow origin", "origin"], 0), ("pull_request", 1, "", ["--unshallow origin"], 1),
    ("push", 128, "", ["--unshallow origin main", "origin main"], 0), ("pull_request", 128, "1", ["--unshallow origin", "origin"], 1)])
def test_the_ratchet_guard_reruns_its_history_fetch_on_exit_128_alone(tmp_path, event, fault, verdict, fetches, status):
    origin, git = tmp_path / "origin", ["git", "-C", str(tmp_path / "origin")]
    for command in (["git", "init", "-q", "-b", "main", str(origin)], [*git, "config", "user.name", "fixture"],
                    [*git, "config", "user.email", "fixture@example.com"], [*git, "config", "commit.gpgsign", "false"],
                    [*git, "commit", "-q", "--allow-empty", "-m", "base"],
                    ["git", "clone", "-q", "--depth", "1", origin.as_uri(), str(tmp_path / "ws")]):
        subprocess.run(command, check=True, capture_output=True)
    sha = subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    result, calls = run_stubbed(tmp_path, "tests.yml", "budgets", "Ratchet documents", verdict, fault, GITHUB_EVENT_NAME=event,
                                AI_RESEARCHER_CI_SHA=sha, AI_RESEARCHER_BEFORE=sha)
    assert result.returncode == status, result.stderr
    assert (tmp_path / "git.log").read_text(encoding="utf-8").splitlines() == [f"fetch {f} {sha}" for f in fetches]
    assert [call[0] for call in calls] == ["scripts/ci/check_ratchets.py"] * (fault == 128)
