"""The validate step's downward-only records gate, EXECUTED (issue #340).

A staged record raising a value recorded at its base dies here, before
the deploy key; lowerings, removals and first entries land. The cases
run the step's own run block with the seam at a local fixture repo.
Helpers are copied, not imported: a sibling test module import
re-collects its TestCase here and runs every case twice.
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
    "size-baseline.json": "size-baseline-data",
    "comment-share.json": "comment-share-data",
}
TAGS = {"ratchet-data": "ratchet", "size-baseline-data": "size",
        "comment-share-data": "comment"}


def staged_flags(directory, truth):
    flags = {tag: "false" for tag in TAGS.values()}
    flags[TAGS[directory]] = truth
    return {f"AI_RESEARCHER_{tag.upper()}_STAGED": value
            for tag, value in flags.items()}


SIZE = "size-baseline.json"
COMMENT = "comment-share.json"
THRESHOLDS = "ci-thresholds.json"
SIZE_BASE = {"schema_version": 1, "baseline": {"a.py": 100, "b.py": 50}}
COMMENT_BASE = {"x.yml": [10, 100]}
THRESHOLDS_BASE = {
    "coverage": {"javascript": {"floor": 95.3, "measured": 96.8},
                 "python": {"floor": 92.8, "measured": 94.3}},
    "schema_version": 1,
}


def _records_repo(tmp_path, documents):
    """The fetch seam: each record committed at a known SHA on main."""
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


def _validate(tmp_path, document, payload, base, remote):
    """Stage one candidate; run the validate step with the seam at
    remote."""
    data = tmp_path / DIRECTORIES[document]
    data.mkdir(parents=True)
    (data / document).write_bytes(payload)
    (data / "base.txt").write_text(base, encoding="utf-8")
    return _workflowrun.run_step(
        tmp_path, step(load(), "Validate the staged data"),
        {"RUNNER_TEMP": str(tmp_path),
         "AI_RESEARCHER_BASE_FETCH_REMOTE": remote,
         **staged_flags(DIRECTORIES[document], "true")})


def _direction_case(tmp_path, document, staged, base_payload):
    """Build a base repo holding `base_payload` for `document` and run
    the step against a staged `staged` payload of the same document."""
    payload = json.dumps(base_payload).encode("utf-8")
    remote, tip = _records_repo(tmp_path, {document: payload})
    return _validate(tmp_path, document,
                     json.dumps(staged).encode("utf-8"), tip, remote)


@POSIX
def test_a_raised_size_record_is_refused(tmp_path):
    done = _direction_case(
        tmp_path, SIZE, {"schema_version": 1, "baseline": {"a.py": 101}},
        SIZE_BASE)
    assert done.returncode != 0, done.stdout
    # The refusal is the direction gate's, not the schema check's.
    assert "raises a value recorded at its base commit" in done.stderr


@POSIX
def test_a_lowered_size_record_lands(tmp_path):
    done = _direction_case(
        tmp_path, SIZE, {"schema_version": 1, "baseline": {"a.py": 99}},
        SIZE_BASE)
    assert done.returncode == 0, done.stderr


@POSIX
def test_an_unchanged_size_record_lands(tmp_path):
    done = _direction_case(
        tmp_path, SIZE, {"schema_version": 1, "baseline": {"a.py": 100}},
        SIZE_BASE)
    assert done.returncode == 0, done.stderr


@POSIX
def test_a_first_size_entry_lands(tmp_path):
    done = _direction_case(
        tmp_path, SIZE,
        {"schema_version": 1, "baseline": {"a.py": 100, "c.py": 7}},
        SIZE_BASE)
    assert done.returncode == 0, done.stderr


@POSIX
def test_a_removed_size_entry_lands(tmp_path):
    done = _direction_case(
        tmp_path, SIZE, {"schema_version": 1, "baseline": {"a.py": 100}},
        {"schema_version": 1, "baseline": {"a.py": 100, "b.py": 50}})
    assert done.returncode == 0, done.stderr


@POSIX
def test_a_raised_comment_share_is_refused(tmp_path):
    done = _direction_case(
        tmp_path, COMMENT, {"x.yml": [11, 100]}, COMMENT_BASE)
    assert done.returncode != 0, done.stdout
    assert "raises a share recorded at its base commit" in done.stderr


@POSIX
def test_a_byte_rise_with_a_share_rise_is_refused(tmp_path):
    done = _direction_case(
        tmp_path, COMMENT, {"x.yml": [20, 150]}, COMMENT_BASE)
    assert done.returncode != 0, done.stdout
    assert "raises a share" in done.stderr


@POSIX
def test_the_comment_ratchets_real_tightening_lands(tmp_path):
    # comment-ratchet's tighten raises both leaves as the share falls
    # ([4623, 10811] -> [5536, 14438] on this very workflow): a per-leaf
    # compare would refuse exactly this shape.
    done = _direction_case(
        tmp_path, COMMENT, {"x.yml": [5536, 14438]}, {"x.yml": [4623, 10811]})
    assert done.returncode == 0, done.stderr


@POSIX
def test_an_unchanged_comment_share_lands(tmp_path):
    done = _direction_case(
        tmp_path, COMMENT, {"x.yml": [20, 200]}, COMMENT_BASE)
    assert done.returncode == 0, done.stderr


@POSIX
def test_a_first_comment_entry_lands(tmp_path):
    done = _direction_case(
        tmp_path, COMMENT, {"x.yml": [1, 5], "y.yml": [2, 10]}, {})
    assert done.returncode == 0, done.stderr


@POSIX
def test_a_removed_comment_entry_lands(tmp_path):
    done = _direction_case(
        tmp_path, COMMENT, {"x.yml": [10, 100]},
        {"x.yml": [10, 100], "y.yml": [5, 50]})
    assert done.returncode == 0, done.stderr


@POSIX
@pytest.mark.parametrize("document,payload", [
    (SIZE, {"schema_version": 1, "baseline": {"huge.py": 999999}}),
    (COMMENT, {"x.yml": [9999, 10000]}),
    # The sibling suite's schema-lands rows, moved here.
    (COMMENT, {}),
    (COMMENT, {"x.py": [0, 10], "y.py": [12, 100]}),
    (SIZE, {"schema_version": 1, "baseline": {}}),
    (SIZE, {"schema_version": 1, "baseline": {"build.py": 2890}}),
    (SIZE, {"schema_version": 1, "baseline": {"a b/c.py": 0}}),
])
def test_a_record_absent_at_its_base_lands(tmp_path, document, payload):
    # Absent at the base commit: a first landing — everything lands.
    remote, tip = _records_repo(tmp_path, {})
    done = _validate(tmp_path, document, json.dumps(payload).encode("utf-8"),
                     tip, remote)
    assert done.returncode == 0, done.stderr


@POSIX
def test_a_base_commit_outside_main_fails_loudly(tmp_path):
    # An orphan commit off main is a loud error, never "absent at base".
    remote, _tip = _records_repo(tmp_path, {})
    repo = tmp_path / "base-records"
    _git(repo, "checkout", "-q", "--orphan", "island")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "island")
    island = _git(repo, "rev-parse", "HEAD")
    done = _validate(tmp_path, COMMENT, b'{"x.yml": [1, 2]}\n', island,
                     remote)
    assert done.returncode != 0, done.stdout
    assert "not reachable from main" in done.stderr


@POSIX
def test_a_failed_base_fetch_fails_loudly(tmp_path):
    _remote, tip = _records_repo(tmp_path, {COMMENT: b'{"x.yml": [1, 2]}\n'})
    done = _validate(tmp_path, COMMENT, b'{"x.yml": [2, 2]}\n', tip,
                     str(tmp_path / "not-a-repo"))
    assert done.returncode != 0, done.stdout


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
