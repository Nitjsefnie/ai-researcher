"""Tests for the coverage ratchet and the ratchet-document guard.

The ratchet moves the recorded calibration in one direction only: a run
whose measured coverage sits at most the hysteresis above the recorded
measured justifies no raise, and a measurement below the recorded value
never lowers anything. The guard refuses a head document that removes a
key, lowers a value, changes schema_version, or rewrites a measurement
without the floor it implies. The cases pin both tools' behaviour, and
the guard also gets end-to-end git cases in temporary repositories.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _thresholds():
    return _load("thresholds")


def _ratchet():
    return _load("ratchet")


def _guard():
    return _load("check_ratchets")


def _document(measured="92.6", floor="91.1", javascript=("50.0", "48.5"),
              schema=1):
    return {
        "schema_version": schema,
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


def _written(tmp_path):
    thresholds = _thresholds()
    target = tmp_path / "ci-thresholds.json"
    thresholds.write(target, _document())
    return target


# --- the ratchet ----------------------------------------------------------


def test_no_raise_within_hysteresis():
    ratchet = _ratchet()
    measured = Decimal("94.1")  # recorded 92.6 + hysteresis 1.5, not over
    assert ratchet.update(_document(), measured) is None


def test_raise_beyond_hysteresis():
    ratchet = _ratchet()
    updated = ratchet.update(_document(), Decimal("94.2"))
    assert updated is not None
    record = updated["coverage"]["python"]
    assert record["measured"] == Decimal("94.2")
    assert record["floor"] == Decimal("92.7")
    assert updated["schema_version"] == 1
    assert updated["coverage"]["javascript"] == {
        "measured": Decimal("50.0"),
        "floor": Decimal("48.5"),
    }


def test_raise_beyond_hysteresis_javascript():
    ratchet = _ratchet()
    updated = ratchet.update(_document(), Decimal("52.0"),
                             language="javascript")
    assert updated is not None
    record = updated["coverage"]["javascript"]
    assert record["measured"] == Decimal("52.0")
    assert record["floor"] == Decimal("50.5")
    assert updated["coverage"]["python"] == {
        "measured": Decimal("92.6"),
        "floor": Decimal("91.1"),
    }


def test_no_raise_within_hysteresis_javascript():
    ratchet = _ratchet()
    measured = Decimal("51.5")  # recorded 50.0 + hysteresis 1.5, not over
    assert ratchet.update(
        _document(), measured, language="javascript") is None


def test_measured_below_recorded_never_lowers():
    ratchet = _ratchet()
    for language in ("python", "javascript"):
        assert ratchet.update(
            _document(), Decimal("0.0"), language) is None


def test_measurement_at_the_recorded_value_never_raises():
    ratchet = _ratchet()
    for measured in (Decimal("91.1"), Decimal("92.6"), Decimal("94.1")):
        assert ratchet.update(_document(), measured) is None


def test_measured_with_two_decimals_rejected():
    ratchet = _ratchet()
    with pytest.raises(ValueError, match="exactly one decimal place"):
        ratchet.update(_document(), Decimal("94.25"))


def test_floor_for_is_measured_minus_gap():
    ratchet = _ratchet()
    assert ratchet.floor_for(Decimal("92.6")) == Decimal("91.1")


def test_main_no_raise_leaves_file_untouched(tmp_path, capsys):
    ratchet = _ratchet()
    target = _written(tmp_path)
    before = target.read_text(encoding="utf-8")
    assert ratchet.main(
        ["--measured", "94.1", "--thresholds", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == before
    assert "justifies no raise" in capsys.readouterr().out


def test_main_raise_rewrites_the_file(tmp_path, capsys):
    thresholds = _thresholds()
    ratchet = _ratchet()
    target = _written(tmp_path)
    assert ratchet.main(
        ["--measured", "95.0", "--thresholds", str(target)]) == 0
    doc = thresholds.load(target)
    assert doc["coverage"]["python"]["measured"] == Decimal("95.0")
    assert doc["coverage"]["python"]["floor"] == Decimal("93.5")
    out = capsys.readouterr().out
    assert "raised" in out
    assert "91.1 -> 93.5" in out


def test_main_raise_javascript_rewrites_the_file(tmp_path, capsys):
    thresholds = _thresholds()
    ratchet = _ratchet()
    target = _written(tmp_path)
    assert ratchet.main(
        ["--language", "javascript", "--measured", "52.0",
         "--thresholds", str(target)]) == 0
    doc = thresholds.load(target)
    assert doc["coverage"]["javascript"]["measured"] == Decimal("52.0")
    assert doc["coverage"]["javascript"]["floor"] == Decimal("50.5")
    assert doc["coverage"]["python"]["measured"] == Decimal("92.6")
    out = capsys.readouterr().out
    assert "raised" in out
    assert "48.5 -> 50.5" in out


def test_main_invalid_measurement_fails(tmp_path, capsys):
    ratchet = _ratchet()
    target = _written(tmp_path)
    assert ratchet.main(
        ["--measured", "abc", "--thresholds", str(target)]) == 1
    assert capsys.readouterr().err


def test_main_unreadable_thresholds_fails(tmp_path):
    ratchet = _ratchet()
    missing = tmp_path / "absent.json"
    assert ratchet.main(
        ["--measured", "92.6", "--thresholds", str(missing)]) == 1


# --- the guard: direct function cases --------------------------------------


def _base_head():
    base = _document()
    head = _document()
    return base, head


def test_guard_identical_documents_are_clean():
    guard = _guard()
    base = _document()
    # round-trip the way the guard itself reads a document: JSON text
    # parsed back with numbers as Decimals
    round_trip = json.loads(
        json.dumps(base, default=float), parse_float=Decimal,
        parse_int=Decimal)
    assert guard.coverage_relaxations(base, round_trip) == []


def test_guard_deleted_document_is_a_finding():
    guard = _guard()
    findings = guard.coverage_relaxations({"schema_version": 1}, None)
    assert findings == [
        '.github/ci-thresholds.json: (document): merge base "present", '
        'head absent — the document was deleted'
    ]


def test_guard_key_removed_is_a_finding():
    guard = _guard()
    base, head = _base_head()
    del head["coverage"]["javascript"]
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 2  # the language's measured and floor leaves
    assert all("key removed" in line for line in findings)
    assert all("coverage.javascript" in line for line in findings)


def test_guard_key_added_is_a_finding():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["ruby"] = {}
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "key added" in findings[0]


def test_guard_schema_version_change_is_a_finding():
    guard = _guard()
    base, head = _base_head()
    head["schema_version"] = 2
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "schema_version changed" in findings[0]


def test_guard_lowered_values_are_findings():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["python"]["measured"] = Decimal("90.0")
    head["coverage"]["python"]["floor"] = Decimal("88.5")
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 2
    assert "lowered; it may only rise" in findings[0]
    assert "lowered; it may only rise" in findings[1]


def test_guard_lowered_floor_alone_is_a_finding():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["python"]["floor"] = Decimal("89.0")
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "lowered; it may only rise" in findings[0]


def test_guard_raise_carrying_the_implied_floor_is_clean():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["python"]["measured"] = Decimal("94.2")
    head["coverage"]["python"]["floor"] = Decimal("92.7")
    assert guard.coverage_relaxations(base, head) == []


def test_guard_changed_measurement_without_implied_floor_is_a_finding():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["python"]["measured"] = Decimal("94.2")
    # the floor stays at the old implied value: not a document the ratchet
    # would have written
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "must carry floor = measured - 1.5" in findings[0]


def test_guard_string_value_is_not_a_finite_number():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["python"]["measured"] = "94.2"
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "not a finite number" in findings[0]


def test_guard_boolean_value_is_not_a_finite_number():
    guard = _guard()
    base, head = _base_head()
    head["coverage"]["python"]["measured"] = True
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "not a finite number" in findings[0]


def test_guard_absent_at_merge_base_is_clean():
    guard = _guard()
    assert guard.coverage_relaxations(None, {"schema_version": 1}) == []


# --- the guard: end-to-end git cases ----------------------------------------


def _git(repo, *args):
    return subprocess.run(("git", "-C", str(repo)) + args, check=True,
                          capture_output=True, text=True)


def _seed_repo(tmp_path, document):
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    _thresholds().write(repo / ".github" / "ci-thresholds.json", document)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "base")
    return repo


def _commit_here(repo, document, message):
    """Commit the document on whatever branch is checked out."""
    (repo / ".github").mkdir(exist_ok=True)
    _thresholds().write(repo / ".github" / "ci-thresholds.json", document)
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _commit_on_branch(repo, document, message):
    """Commit on a `pr` branch forked from main, as a pull request does.

    Both revisions must have history behind them: with the change on main
    itself, the merge base of main and the tip IS the tip, and the check
    would compare the document with itself.
    """
    _git(repo, "checkout", "-q", "-b", "pr")
    return _commit_here(repo, document, message)


def test_end_to_end_clean_raise_is_ok(tmp_path, monkeypatch):
    repo = _seed_repo(tmp_path, _document())
    head = _commit_on_branch(repo, _document(measured="94.2", floor="92.7"),
                             "raise")
    guard = _guard()
    fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []
    assert fork == _git(repo, "rev-parse", "main").stdout.strip()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 0


def test_end_to_end_relaxed_head_fails_with_findings(tmp_path, capsys,
                                                     monkeypatch):
    repo = _seed_repo(tmp_path, _document())
    head = _commit_on_branch(repo, _document(measured="90.0", floor="88.5"),
                             "lower the calibration by hand")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 2
    assert all("lowered" in line for line in findings)
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 1
    assert "relaxation(s)" in capsys.readouterr().out


def test_end_to_end_main_advancing_after_the_fork_is_not_a_relaxation(
        tmp_path, monkeypatch):
    """The merge base, not main's tip, is the reference.

    Main records a higher measured after the branch forked — a raise the
    stale branch must not be penalised for missing. Comparing against
    main's tip instead of the merge base would read the branch's older
    values as a lowering; the guard compares against the fork, so the
    stale branch is clean.
    """
    repo = _seed_repo(tmp_path, _document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _git(repo, "checkout", "-q", "main")
    tip = _commit_here(repo, _document(measured="94.2", floor="92.7"),
                       "raise on main after the branch forked")
    guard = _guard()
    fork, findings = guard.check_ratchets(repo, "main", "pr")
    assert findings == []
    assert fork == _git(repo, "rev-parse", "pr").stdout.strip()
    assert fork != tip
    monkeypatch.chdir(repo)
    assert guard.main(["main", "pr"]) == 0


def test_end_to_end_branch_lowering_while_main_advanced_is_flagged(tmp_path):
    """Main's raise does not make the branch's own lowering acceptable."""
    repo = _seed_repo(tmp_path, _document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _git(repo, "checkout", "-q", "main")
    _commit_here(repo, _document(measured="94.2", floor="92.7"),
                 "raise on main after the branch forked")
    _git(repo, "checkout", "-q", "pr")
    head = _commit_here(repo, _document(measured="90.0", floor="88.5"),
                        "lower the calibration on the branch")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 2
    assert all("lowered" in line for line in findings)


def test_end_to_end_shallow_repository_is_refused(tmp_path):
    repo = _seed_repo(tmp_path, _document())
    clone = Path(tmp_path) / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(clone)],
        check=True, capture_output=True)
    guard = _guard()
    with pytest.raises(ValueError, match="shallow"):
        guard.check_ratchets(clone, "main", "main")


def test_end_to_end_document_absent_at_merge_base_is_clean(tmp_path):
    repo = _seed_repo(tmp_path, _document())
    _git(repo, "rm", "-q", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "remove the document")
    # the branch reintroduces the document against a merge base that
    # lacks it — nothing there to relax
    head = _commit_on_branch(repo, _document(), "reintroduce the document")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []


def test_end_to_end_symlink_head_entry_is_a_finding(tmp_path, monkeypatch):
    repo = _seed_repo(tmp_path, _document())
    _git(repo, "checkout", "-q", "-b", "pr")
    target = repo / ".github" / "ci-thresholds.json"
    target.unlink()
    target.symlink_to("elsewhere.json")
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "swap the document for a symlink")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", "pr")
    assert findings == [
        '.github/ci-thresholds.json: (document): merge base "100644 blob", '
        'head "120000 blob" — not a regular file'
    ]
    monkeypatch.chdir(repo)
    assert guard.main(["main", "pr"]) == 1


def test_end_to_end_invalid_json_at_head_is_a_git_error(tmp_path):
    repo = _seed_repo(tmp_path, _document())
    _git(repo, "checkout", "-q", "-b", "pr")
    (repo / ".github" / "ci-thresholds.json").write_text(
        "{not json", encoding="utf-8")
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "break the document")
    guard = _guard()
    with pytest.raises(ValueError, match="not valid JSON"):
        guard.check_ratchets(repo, "main", "pr")


def test_end_to_end_unknown_revision_is_exit_2(tmp_path):
    _seed_repo(tmp_path, _document())
    guard = _guard()
    assert guard.main(["main", "no-such-revision"]) == 2


def test_end_to_end_push_lowering_on_main_is_flagged(tmp_path):
    """The push path's shape: BEFORE..HEAD, both tips of main.

    The workflow's push branch invokes the guard as
    ``check_ratchets.py "${BEFORE}" HEAD`` with the previous main tip and
    the new one; a direct-push lowering must be flagged exactly as a
    branch's lowering is.
    """
    repo = _seed_repo(tmp_path, _document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_here(repo, _document(measured="90.0", floor="88.5"),
                        "lower the calibration by direct push")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, before, head)
    assert len(findings) == 2
    assert all("lowered" in line for line in findings)


def test_end_to_end_push_raise_on_main_is_clean(tmp_path):
    """The automated raise's own push run must stay green.

    The raise commit only lifts values, so against its parent it relaxes
    nothing — the push branch of the guard step cannot break the very
    commits the ratchet itself produces.
    """
    repo = _seed_repo(tmp_path, _document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_here(repo, _document(measured="94.2", floor="92.7"),
                        "raise (automated)")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, before, head)
    assert findings == []
