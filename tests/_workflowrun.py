"""Execute decoded workflow shell steps in contract tests.

Adapted from Nitjsefnie-Harness-Commons/daedalus `tests/_workflowrun.py` at
0d4f2a03765b345cab8105c07991f2dbfdc98f3a: a workflow `run:` block is
executable code, so the contract tests run it rather than read it, with a
stub `gh` serving the GitHub API surface the step touches and recording
every call it makes. The stub enforces the run's own identity — a route for
another repository, pull request or head SHA is unmodeled and fails loudly
— because a double that answers any destination cannot prove the
destination.
"""
import shlex
import shutil
import subprocess
from pathlib import Path

import yaml

# The comment workflow declares no `shell:`, so this is the runner default.
_DEFAULT_SHELL = "bash -e {0}"


def step_by_name(workflow_path, job_id, name):
    """Return one job's named step, decoded, from a workflow file."""
    workflow = yaml.safe_load(
        Path(workflow_path).read_text(encoding="utf-8"))
    [job] = [job for job_id_, job in workflow["jobs"].items()
             if job_id_ == job_id]
    [step] = [step for step in job["steps"] if step.get("name") == name]
    return step


def run_step(workdir, step, env):
    """Run one decoded workflow step, with `env` winning over its own.

    The workflow substitutes `${{ ... }}` before a script ever runs, so a
    test must resolve every expression in the step's `env:` itself; an
    unresolved one reaching the child is a broken test, not a broken step.
    The child's PATH is the stub directory PREPENDED to the ambient PATH —
    on every matrix OS the step's own tools (`cat`, `wc`, `jq`) resolve
    ambiently, and the stub `gh` shadows any real one by search order.
    """
    script = step.get("run")
    assert isinstance(script, str), f"step has no run script: {step!r}"
    script_path = Path(workdir) / "workflow-step.sh"
    script_path.write_text(script, encoding="utf-8")
    shell = step.get("shell", _DEFAULT_SHELL)
    assert shell.count("{0}") == 1, shell
    command = [part.replace("{0}", str(script_path))
               for part in shlex.split(shell)]
    command[0] = shutil.which(command[0]) or command[0]
    child_env = dict(env)
    for name, value in (step.get("env") or {}).items():
        assert "${{" not in value or name in env, (
            f"unresolved workflow expression in {name}: {value!r}")
        child_env.setdefault(name, value)
    return subprocess.run(
        command, cwd=workdir, env=child_env, check=False,
        capture_output=True, text=True, timeout=120)


def write_gh_stub(bin_dir, state_path, calls_path):
    """Install the `gh` double: a trampoline and its Python payload.

    The trampoline is a POSIX `sh` script rather than a Python-shebang
    file: on the Windows cells the suite runs under git-bash, where an
    `env python3` shebang resolves to the WindowsApps stub and a bare
    `python` may not exist on PATH. `sh` exists in every cell's ambient
    PATH, and the payload is found beside the trampoline.
    """
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "gh").write_text(
        "#!/bin/sh\n"
        '# The test double for the gh CLI; payload sits beside this file.\n'
        'exec "$(command -v python || command -v python3)" '
        '"$(dirname "$0")/gh_payload.py" "$@"\n',
        encoding="utf-8")
    (bin_dir / "gh_payload.py").write_text(STUB_GH, encoding="utf-8")
    trampoline = bin_dir / "gh"
    trampoline.chmod(0o755)
    state_path.write_text("{}", encoding="utf-8")
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    return trampoline


STUB_GH = r'''#!/usr/bin/env python3
"""A `gh` double: canned JSON per route, every call recorded."""
import json
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
state_path = Path(os.environ["STUB_STATE"])
calls_path = Path(os.environ["STUB_CALLS"])
state = json.loads(state_path.read_text(encoding="utf-8"))
with calls_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + chr(10))

def endpoint():
    for value in args:
        if value.startswith("repos/"):
            return value
    return ""

def method():
    for flag in ("-X", "--method"):
        if flag in args:
            return args[args.index(flag) + 1]
    return "GET"

def fields():
    """Field flags, with `@file` expansion on -F/--field only.

    Real gh: -f/--raw-field carries a static literal string, -F/--field
    interprets a leading @ as a filename to read.
    """
    result = {}
    for index, value in enumerate(args[:-1]):
        raw = value in ("-f", "--raw-field")
        typed = value in ("-F", "--field")
        if not (raw or typed):
            continue
        key, separator, field = args[index + 1].partition("=")
        if separator and typed and field.startswith("@"):
            field = Path(field[1:]).read_text(encoding="utf-8")
        if separator:
            result[key] = field
    return result

def emit(document):
    """Serve one API page: jq applies when the call asked, raw otherwise."""
    if "--jq" not in args:
        sys.stdout.write(document + chr(10))
        return
    expression = args[args.index("--jq") + 1]
    done = subprocess.run(
        ["jq", expression], input=document,
        capture_output=True, text=True)
    out = done.stdout
    sys.stderr.write(done.stderr)
    if done.returncode:
        raise SystemExit(done.returncode)
    # gh prints a top-level string result UNQUOTED — every workflow here
    # compares `--jq '.head.sha'` output with a bare SHA.
    stripped = out.strip()
    if (stripped.count(chr(10)) == 0
            and stripped.startswith('"') and stripped.endswith('"')):
        out = json.loads(stripped) + chr(10)
    sys.stdout.write(out)

def refuse(reason):
    print(f"gh stub: {reason}: {args}", file=sys.stderr)
    raise SystemExit(64)

target = endpoint()
verb = method()
REPO = os.environ.get("REPO", "")
PR_NUMBER = os.environ.get("PR_NUMBER", "")
HEAD_SHA = os.environ.get("HEAD_SHA", "")

# Identity first: the double answers only the run's own repository, and
# the destination routes only the run's own pull request and head SHA. A
# step that writes anywhere else is unmodeled, never served.
if not target.startswith(f"repos/{REPO}/"):
    refuse(f"route outside {REPO}")
if "/issues/" in target and "/comments" in target and verb == "POST":
    if target != f"repos/{REPO}/issues/{PR_NUMBER}/comments":
        refuse(f"destination is not pull request {PR_NUMBER}")
    comments = state.setdefault("comments", [])
    comments.append({"id": len(comments) + 1,
                     "user": {"login": "github-actions[bot]"},
                     "body": fields().get("body", "")})
elif "/issues/comments/" in target and verb == "PATCH":
    # The route is repo-level on the real API; the id is the identity, so
    # a PATCH to an id the PR's comment list never named is refused.
    comment_id = target.rsplit("/", 1)[1]
    known = {str(comment["id"]) for comment in state.get("comments", [])}
    if comment_id not in known:
        refuse(f"PATCH to unknown comment id {comment_id}")
    for comment in state.get("comments", []):
        if str(comment["id"]) == comment_id:
            comment["body"] = fields().get("body", "")
elif "/issues/" in target and target.endswith("/comments") and verb == "GET":
    emit(json.dumps(state.get("comments", [])))
elif "/pulls?" in target and verb == "GET":
    emit(json.dumps(state.get("pulls", [])))
elif "/pulls/" in target and verb == "GET":
    if not target.rstrip("/").endswith(f"/pulls/{PR_NUMBER}"):
        refuse(f"pull route is not pull request {PR_NUMBER}")
    emit(json.dumps({"head": {"sha": state.get("head_sha", "")}}))
elif target.endswith("/artifacts") and verb == "GET":
    emit(json.dumps({"total_count": len(state.get("artifacts", [])),
                     "artifacts": state.get("artifacts", [])}))
elif target.endswith("/jobs") and verb == "GET":
    emit(json.dumps({"total_count": len(state.get("jobs", [])),
                     "jobs": state.get("jobs", [])}))
elif target.endswith("/check-runs") and verb == "GET":
    if f"/commits/{HEAD_SHA}/" not in target:
        refuse(f"check route is not head {HEAD_SHA}")
    checks = state.get("checks", [])
    if fields().get("filter") != "all":
        checks = checks[-1:]
    emit(json.dumps({"total_count": len(checks), "check_runs": checks}))
elif target.endswith("/check-runs") and verb == "POST":
    checks = state.setdefault("checks", [])
    checks.append({"id": len(checks) + 1, **fields(),
                   "app": {"slug": "github-actions"}})
elif "/check-runs/" in target and verb == "PATCH":
    check_id = target.rsplit("/", 1)[1]
    for check in state.get("checks", []):
        if str(check["id"]) == check_id:
            check.update(fields())
else:
    refuse("unmodeled call")

state_path.write_text(json.dumps(state), encoding="utf-8")
'''


def recorded_writes(calls_path):
    """Return recorded POST and PATCH calls from the stub log."""
    calls_path = Path(calls_path)
    if not calls_path.exists():
        return []
    calls = calls_path.read_text(encoding="utf-8").splitlines()
    return [call for call in calls
            if '"-X"' in call and ('"POST"' in call or '"PATCH"' in call)]
