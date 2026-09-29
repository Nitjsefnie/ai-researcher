"""Tests for the CI thresholds document loader.

The loader is the one place both ratchets read their numbers from, so a
document it accepts is a document CI acts on. The cases below pin the
document shape (schema_version, one-decimal coverage values, floor below
measured and exactly the calibration gap below it, unknown keys refused)
and the canonical byte layout that ``write()`` publishes.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

REPO_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = REPO_ROOT / ".github" / "ci-thresholds.json"


def _load(name):
    """Import a scripts/ci module by path.

    scripts/ci is not a package and deliberately has no __init__.py — it
    holds standalone CI entry points, not an importable library.
    """
    path = REPO_ROOT / "scripts" / "ci" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


thresholds = _load("thresholds")

GAP = Decimal("1.5")


def _document(measured="92.6", floor="91.1", javascript=("50.0", "48.5")):
    return {
        "schema_version": 1,
        "coverage": {
            "python": {
                "measured": Decimal(measured),
                "floor": Decimal(floor),
            },
            "javascript": {
                "measured": Decimal(javascript[0]),
                "floor": Decimal(javascript[1]),
            },
        },
    }


def _written_document(tmp_path, **kwargs):
    target = tmp_path / "ci-thresholds.json"
    payload = json.loads(json.dumps(_document(**kwargs), default=float))
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _git(repo, *args):
    """Git plumbing for the fixtures — NOT the script under test.

    The fixtures build real repositories; only the script's own code has
    to run in-process, so coverage.py can trace it (the script invocation
    is ``thresholds.main(...)``, never a subprocess).
    """
    return subprocess.run(("git", "-C", str(repo)) + args, check=True,
                          capture_output=True, text=True)


def _seed_repo(tmp_path):
    """A git repo whose HEAD commits the document at the canonical path."""
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    thresholds.write(repo / ".github" / "ci-thresholds.json", _document())
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "seed")
    return repo


def _ratchet():
    """Load scripts/ci/ratchet.py the same way, for the raise-path test."""
    return _load("ratchet")


def test_committed_document_loads():
    doc = thresholds.load(THRESHOLDS_PATH)
    assert doc["schema_version"] == 1
    for language in ("python", "javascript"):
        record = doc["coverage"][language]
        assert isinstance(record["measured"], Decimal)
        assert isinstance(record["floor"], Decimal)
        assert record["floor"] == record["measured"] - GAP


def test_javascript_coverage_language_accepted(tmp_path):
    # A javascript record carries the same shape and validation as a
    # python one: exactly one decimal place, floor exactly the gap below.
    target = tmp_path / "ci-thresholds.json"
    doc = _document()
    doc["coverage"]["javascript"] = {
        "measured": Decimal("71.3"),
        "floor": Decimal("69.8"),
    }
    thresholds.write(target, doc)
    loaded = thresholds.load(target)
    assert loaded["coverage"]["javascript"]["measured"] == Decimal("71.3")
    assert loaded["coverage"]["javascript"]["floor"] == Decimal("69.8")


def test_normalised_document_keeps_exact_values():
    doc = thresholds.normalise(_document(measured="92.6", floor="91.1"))
    record = doc["coverage"]["python"]
    assert record["measured"] == Decimal("92.6")
    assert record["floor"] == Decimal("91.1")


def test_write_publishes_canonical_bytes(tmp_path):
    target = tmp_path / "ci-thresholds.json"
    doc = _document()
    thresholds.write(target, doc)
    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text == json.dumps(
        json.loads(text), indent=2, sort_keys=True) + "\n"
    assert thresholds.load(target) == thresholds.normalise(doc)


def test_retired_baseline_section_is_now_an_unknown_field(tmp_path):
    # The maintainer ruling for this repo is coverage only: a document
    # carrying a sibling repo's module_size_baseline section is refused,
    # not silently ignored.
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["module_size_baseline"] = {}
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError,
                       match="unknown field: module_size_baseline"):
        thresholds.load(target)


def test_unknown_top_level_key_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["surprise"] = {}
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown field: surprise"):
        thresholds.load(target)


def test_unknown_coverage_language_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["coverage"]["ruby"] = {"measured": 50.0, "floor": 48.5}
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown coverage language"):
        thresholds.load(target)


def test_missing_javascript_coverage_language_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    del payload["coverage"]["javascript"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError,
                       match="missing coverage language: javascript"):
        thresholds.load(target)


def test_missing_field_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    del payload["coverage"]["python"]["floor"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        thresholds.load(target)


def test_floor_at_or_above_measured_refused(tmp_path):
    target = _written_document(tmp_path, measured="90.0", floor="90.0")
    with pytest.raises(ValueError, match="floor must be below measured"):
        thresholds.load(target)


def test_wrong_calibration_gap_refused(tmp_path):
    target = _written_document(tmp_path, measured="93.0", floor="90.0")
    with pytest.raises(ValueError, match="gap must be 1.5"):
        thresholds.load(target)


@pytest.mark.parametrize("value", ["92.55", "92.555"])
def test_more_than_one_decimal_place_refused(tmp_path, value):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["coverage"]["python"]["measured"] = json.loads(value)
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one decimal place"):
        thresholds.load(target)


def test_coverage_number_without_decimal_place_refused(tmp_path):
    # 92 is refused: the canonical spelling of a coverage number carries
    # exactly one decimal place (92.0) — what the ratchet writes and
    # what coverage --precision=1 measures.
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["coverage"]["python"]["measured"] = 92
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one decimal place"):
        thresholds.load(target)


def test_coverage_number_with_trailing_zero_place_accepted(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["coverage"]["python"]["measured"] = 92.0
    payload["coverage"]["python"]["floor"] = 90.5
    target.write_text(json.dumps(payload), encoding="utf-8")
    doc = thresholds.load(target)
    assert doc["coverage"]["python"]["measured"] == Decimal("92.0")


def test_non_finite_number_refused(tmp_path):
    target = tmp_path / "ci-thresholds.json"
    target.write_text(
        '{"schema_version": 1, "coverage": {"python": {"measured": NaN,'
        ' "floor": 91.1}, "javascript": {"measured": 50.0, "floor": 48.5}}}',
        encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        thresholds.load(target)


def test_duplicate_key_refused(tmp_path):
    target = tmp_path / "ci-thresholds.json"
    target.write_text(
        '{"schema_version": 1, "coverage": {"python": {"measured": 92.6,'
        ' "floor": 91.1}, "javascript": {"measured": 50.0, "floor": 48.5}},'
        ' "schema_version": 1}',
        encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        thresholds.load(target)


def test_wrong_schema_version_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema_version"):
        thresholds.load(target)


def test_coverage_value_bounds():
    assert thresholds.coverage_value(
        Decimal("100.0"), "m") == Decimal("100.0")
    assert thresholds.coverage_value(Decimal("0.0"), "m") == Decimal("0.0")
    with pytest.raises(ValueError, match="between 0.0 and 100.0"):
        thresholds.coverage_value(Decimal("100.1"), "m")
    with pytest.raises(ValueError, match="between 0.0 and 100.0"):
        thresholds.coverage_value(Decimal("-0.1"), "m")
    with pytest.raises(ValueError, match="exactly one decimal place"):
        thresholds.coverage_value(Decimal("92"), "m")


def test_committed_document_bytes_are_canonical(tmp_path):
    # The COMMITTED bytes must be byte-identical to what write()
    # publishes for the same document — no hand-edited formatting
    # drift. The bytes come from git, not the working-tree file: a
    # Windows autocrlf checkout delivers CRLF on disk, and the pin has
    # to hold on every platform's checkout.
    doc = thresholds.load(THRESHOLDS_PATH)
    target = tmp_path / "canonical.json"
    thresholds.write(target, doc)
    committed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "cat-file", "blob",
         f"HEAD:{THRESHOLDS_PATH.relative_to(REPO_ROOT).as_posix()}"],
        capture_output=True, check=True).stdout
    assert committed == target.read_bytes()


def test_coverage_floor_cli_prints_floor():
    # The printed floor is whatever the committed document records — the
    # seed moves; the CLI's contract does not.
    recorded = thresholds.load(THRESHOLDS_PATH)["coverage"]["python"]
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "thresholds.py"),
         "--coverage-floor", "python", "--thresholds", str(THRESHOLDS_PATH)],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == f'{recorded["floor"]:.1f}'


def test_coverage_measured_cli_prints_measured():
    recorded = thresholds.load(THRESHOLDS_PATH)["coverage"]["python"]
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "thresholds.py"),
         "--coverage-measured", "python", "--thresholds",
         str(THRESHOLDS_PATH)],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == f'{recorded["measured"]:.1f}'


def test_check_cli_accepts_committed_document():
    # No check=True: the return code is itself the assertion subject.
    result = subprocess.run(  # pylint: disable=subprocess-run-check
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "thresholds.py"),
         "--check", "--thresholds", str(THRESHOLDS_PATH)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "thresholds valid" in result.stdout


def test_check_cli_rejects_broken_document(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = 7
    target.write_text(json.dumps(payload), encoding="utf-8")
    # No check=True: a nonzero exit is the expected outcome here.
    result = subprocess.run(  # pylint: disable=subprocess-run-check
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "thresholds.py"),
         "--check", "--thresholds", str(target)],
        capture_output=True, text=True)
    assert result.returncode == 1
    assert "schema_version" in result.stderr


# --- the --check history component (issue #53) -------------------------------
#
# These run thresholds.main() IN-PROCESS, not through a subprocess: the
# coverage job traces the pytest process only, so a subprocess invocation
# would leave the history component uncounted and drag the ratchet total
# below its floor (PR #72's coverage-gate failure).


def test_check_rejects_working_tree_lowering(tmp_path, capsys):
    # Issue #53: a lowered document that keeps the 1.5 calibration gap is
    # self-consistent, so the structural check alone accepts it. --check
    # must also judge the working tree against the committed copy.
    repo = _seed_repo(tmp_path)
    target = repo / ".github" / "ci-thresholds.json"
    thresholds.write(
        target, _document(measured="90.0", floor="88.5"))
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 1
    captured = capsys.readouterr()
    assert "coverage.python.measured" in captured.err
    assert "lowered; it may only rise" in captured.err
    assert "coverage.python.floor" in captured.err


def test_check_accepts_working_tree_raise(tmp_path, capsys):
    # A raise lifts values only, so it is never a relaxation.
    repo = _seed_repo(tmp_path)
    target = repo / ".github" / "ci-thresholds.json"
    thresholds.write(
        target, _document(measured="94.2", floor="92.7"))
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 0
    assert "thresholds valid" in capsys.readouterr().out


def test_check_outside_any_repository_skips_history(tmp_path, capsys):
    # No repository around the file: there is no committed copy to be
    # lowered against, and the purely structural check decides.
    target = _written_document(tmp_path)
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 0
    assert "thresholds valid" in capsys.readouterr().out


def test_check_skips_history_when_git_is_missing(tmp_path, capsys,
                                                 monkeypatch):
    # git unavailable: the history component cannot run, and --check
    # stays a purely structural check rather than failing.
    def _raise(*_args, **_kwargs):
        raise OSError("no git binary")

    monkeypatch.setattr(thresholds.subprocess, "run", _raise)
    target = _written_document(tmp_path)
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 0
    assert "thresholds valid" in capsys.readouterr().out


def test_check_accepts_the_automated_raise_path(tmp_path, capsys):
    # The "Ratchet the thresholds" CI step raises the working-tree copy
    # with ratchet.py and then runs --check; that order must stay clean.
    repo = _seed_repo(tmp_path)
    target = repo / ".github" / "ci-thresholds.json"
    ratchet = _ratchet()
    assert ratchet.main(
        ["--measured", "94.2", "--thresholds", str(target)]) == 0
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 0
    assert "thresholds valid" in capsys.readouterr().out


def test_check_skips_history_when_head_is_unborn(tmp_path, capsys):
    # A repository with no commits has no copy at HEAD to be lowered
    # against: the first document cannot be lowered.
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    target = repo / ".github" / "ci-thresholds.json"
    thresholds.write(target, _document())
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 0
    assert "thresholds valid" in capsys.readouterr().out


def test_check_skips_history_when_absent_at_head(tmp_path, capsys):
    # A first document cannot be lowered: with no copy of the file at
    # HEAD (here it was never committed) the history component is skipped
    # and the structural check alone decides.
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "seed without the document")
    target = repo / ".github" / "ci-thresholds.json"
    thresholds.write(target, _document())
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 0
    assert "thresholds valid" in capsys.readouterr().out


def test_check_fails_closed_when_committed_copy_is_unreadable(tmp_path,
                                                              capsys):
    # A committed copy exists but cannot be parsed: never-lower cannot be
    # certified, so --check refuses instead of passing.
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    target = repo / ".github" / "ci-thresholds.json"
    target.write_text("{not json", encoding="utf-8")
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "commit a broken document")
    thresholds.write(target, _document())
    assert thresholds.main(["--check", "--thresholds", str(target)]) == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_invalid_json_text_refused(tmp_path):
    target = tmp_path / "ci-thresholds.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid thresholds JSON"):
        thresholds.load(target)


def test_non_object_document_refused(tmp_path):
    target = tmp_path / "ci-thresholds.json"
    target.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="thresholds must be an object"):
        thresholds.load(target)


def test_non_object_coverage_section_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["coverage"] = "nope"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage must be an object"):
        thresholds.load(target)


def test_non_number_schema_version_refused(tmp_path):
    target = _written_document(tmp_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["schema_version"] = "one"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON number"):
        thresholds.load(target)


def test_unknown_language_in_coverage_cli_lookup(tmp_path):
    target = _written_document(tmp_path)
    with pytest.raises(ValueError, match="unknown coverage language"):
        thresholds.coverage(thresholds.load(target), "ruby")


@pytest.mark.skipif(os.name == "nt", reason="Windows stat carries no POSIX "
                    "permission bits")
def test_write_preserves_the_target_mode(tmp_path):
    target = tmp_path / "ci-thresholds.json"
    target.write_bytes(b"{}\n")
    target.chmod(0o644)
    thresholds.write(target, _document())
    loaded = thresholds.load(target)
    assert loaded["coverage"]["python"]["measured"] == Decimal("92.6")
    assert target.stat().st_mode & 0o777 == 0o644


def test_floor_cli_prints_javascript_floor():
    recorded = thresholds.load(THRESHOLDS_PATH)["coverage"]["javascript"]
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "thresholds.py"),
         "--coverage-floor", "javascript", "--thresholds",
         str(THRESHOLDS_PATH)],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == f'{recorded["floor"]:.1f}'


def test_cli_with_missing_thresholds_file_fails(tmp_path):
    missing = tmp_path / "absent.json"
    result = subprocess.run(  # pylint: disable=subprocess-run-check
        [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "thresholds.py"),
         "--check", "--thresholds", str(missing)],
        capture_output=True, text=True)
    assert result.returncode == 1
    assert "cannot read thresholds" in result.stderr
