"""Exercise the coverage validate step's direction boundary (issue #340).

Helpers are copied: importing the sibling module collects its TestCase twice.
"""
import json
import os
import pathlib
import subprocess

import pytest
import yaml

import _workflowrun

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ratchet-push.yml"
POSIX = pytest.mark.skipif(os.name == "nt", reason="Ubuntu workflow shell")


def load():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"),
                     Loader=yaml.BaseLoader)


def step(wf, name):
    matches = [s for s in wf["jobs"]["push"]["steps"]
               if s.get("name") == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def _git(workdir, *args):
    done = subprocess.run(["git", *args], cwd=workdir, check=True,
                          capture_output=True, text=True)
    return done.stdout.strip()


# The staging directories and list-step tags, copied from the sibling
# suite.
DIRECTORIES = {
    "ci-thresholds.json": "ratchet-data",
}
TAGS = {"ratchet-data": "ratchet"}


def staged_flags(directory, truth):
    flags = {tag: "false" for tag in TAGS.values()}
    flags[TAGS[directory]] = truth
    return {f"AI_RESEARCHER_{tag.upper()}_STAGED": value
            for tag, value in flags.items()}


THRESHOLDS = "ci-thresholds.json"
THRESHOLDS_BASE = {
    "coverage": {"javascript": {"floor": 95.3, "measured": 96.8},
                 "python": {"floor": 92.8, "measured": 94.3}},
    "schema_version": 1,
}


def _records_repo(tmp_path, documents):
    repo = tmp_path / "base-records"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "user.email", "fixture@example.com")
    (repo / ".github").mkdir()
    (repo / ".github/.gitkeep").write_text("", encoding="utf-8")
    _git(repo, "add", ".github/.gitkeep")
    _git(repo, "commit", "-q", "-m", "records root")
    for name, payload in documents.items():
        (repo / ".github" / name).write_bytes(payload)
        _git(repo, "add", f".github/{name}")
        _git(repo, "commit", "-q", "-m", f"records {name}")
    return str(repo), _git(repo, "rev-parse", "HEAD")


def _validate(tmp_path, document, payload, base, remote, **extra):
    """Stage one candidate; run the validate step with the seam at
    remote (None omits it) and any extra env."""
    data = tmp_path / DIRECTORIES[document]
    data.mkdir(parents=True)
    (data / document).write_bytes(payload)
    (data / "base.txt").write_text(base, encoding="utf-8")
    env = {"RUNNER_TEMP": str(tmp_path),
           **staged_flags(DIRECTORIES[document], "true"), **extra}
    if remote is not None:
        env["AI_RESEARCHER_BASE_FETCH_REMOTE"] = remote
    return _workflowrun.run_step(
        tmp_path, step(load(), "Validate the staged data"), env)


@POSIX
def test_the_thresholds_document_is_not_direction_checked_here(tmp_path):
    # Scope pin: a raising-but-schema-valid thresholds document passes
    # THIS step with no base fetch; its direction check is tests.yml's.
    floor_high = json.loads(json.dumps(THRESHOLDS_BASE))
    floor_high["coverage"]["python"]["floor"] = 99.9
    remote, tip = _records_repo(
        tmp_path, {THRESHOLDS:
                   json.dumps(THRESHOLDS_BASE).encode("utf-8") + b"\n"})
    done = _validate(tmp_path, THRESHOLDS,
                     json.dumps(floor_high).encode("utf-8") + b"\n",
                     tip, remote)
    assert done.returncode == 0, done.stderr
    assert not (tmp_path / "base-docs").exists()
    assert not (tmp_path / f"base-{THRESHOLDS}").exists()
