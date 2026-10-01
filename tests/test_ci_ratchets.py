"""Tests for the coverage ratchet and the ratchet-document guard.

The ratchet moves the recorded calibration in one direction only: a run
whose measured coverage sits at most the hysteresis above the recorded
measured justifies no raise, and a measurement below the recorded value
never lowers anything. The guard refuses a head document that removes a
key, lowers a value, changes schema_version, or rewrites a measurement
without the floor it implies. The perf-budgets document
(.github/perf-budgets.json, issue #109) gets the same guard with the
opposite value direction: every budget is an integer maximum, so the
relaxation is the RAISE, schema_version is fixed, and key add/remove are
findings there too. The instruction-budgets document
(.github/instruction-budgets.json, issue #110) — integer maxima of the
pipeline targets' startup-subtracted callgrind totals — shares the
budgets' direction rules verbatim. The cases pin both tools' behaviour,
and the guard also gets end-to-end git cases in temporary repositories.
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


def _seed_repo(tmp_path, document, budgets=None, instruction_budgets=None):
    """Seed a repo with the thresholds document and, optionally, the
    committed budgets and instruction-budgets documents."""
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    _thresholds().write(repo / ".github" / "ci-thresholds.json", document)
    if budgets is not None:
        _budgets_written(repo, budgets)
    if instruction_budgets is not None:
        _instruction_budgets_written(repo, instruction_budgets)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    _git(repo, "add", ".github/ci-thresholds.json")
    if budgets is not None:
        _git(repo, "add", ".github/perf-budgets.json")
    if instruction_budgets is not None:
        _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", "base")
    return repo


def _instruction_budgets_written(repo, document):
    """Write the instruction budgets document into a repo's .github/."""
    target = Path(repo) / ".github" / "instruction-budgets.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def _budgets_written(repo, document):
    """Write the budgets document into a repo's .github/."""
    target = Path(repo) / ".github" / "perf-budgets.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def _commit_budgets_on_branch(repo, document, message):
    """Commit the budgets document on a `pr` branch forked from main, as
    a pull request does."""
    _git(repo, "checkout", "-q", "-b", "pr")
    _budgets_written(repo, document)
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


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


def test_end_to_end_push_lowering_on_main_is_flagged(tmp_path, capsys,
                                                     monkeypatch):
    """The push path's shape: BEFORE..HEAD, both tips of main.

    The workflow's push branch invokes the guard as
    ``check_ratchets.py "${BEFORE}" HEAD`` with the previous main tip and
    the new one; a direct-push lowering must be flagged exactly as a
    branch's lowering is. main() runs in-process so coverage.py can trace
    the guard's lines.
    """
    repo = _seed_repo(tmp_path, _document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_here(repo, _document(measured="90.0", floor="88.5"),
                        "lower the calibration by direct push")
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head]) == 1
    assert "relaxation(s)" in capsys.readouterr().out


def test_end_to_end_push_raise_on_main_is_clean(tmp_path, capsys,
                                                monkeypatch):
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
    monkeypatch.chdir(repo)
    assert guard.main([before, head]) == 0
    assert "not relaxed" in capsys.readouterr().out


# --- the guard: the budgets document (issue #109) ----------------------------


def _budgets_document(schema=1):
    """The committed budgets document's shape, as test values.

    Option A's shape (issue #112): one code-only byte budget, absolute
    long-task maxima, and hover DOM -- the load/filter/sort DOM counts
    have no leaves because they are never gated.
    """
    return {
        "schema_version": schema,
        "bytes": {"code_bytes": 71627},
        "journeys": {
            "load": {"long_task_count": 2},
            "filter": {"long_task_count": 2},
            "sort": {"long_task_count": 2},
            "hover": {"dom_nodes_mutated": 33, "long_task_count": 1},
        },
    }


def test_budgets_guard_identical_documents_are_clean():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    # round-trip the way the guard itself reads a document: JSON text
    # parsed back with numbers as Decimals
    round_trip = json.loads(json.dumps(head), parse_float=Decimal,
                            parse_int=Decimal)
    assert guard.budgets_relaxations(base, round_trip) == []


def test_budgets_guard_raised_budget_is_a_finding():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    head["bytes"]["code_bytes"] = 71628
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "raised; it may only fall" in findings[0]
    assert "bytes.code_bytes" in findings[0]
    assert ".github/perf-budgets.json" in findings[0]


def test_budgets_guard_lowered_budget_is_clean():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    head["journeys"]["filter"]["long_task_count"] = 0
    head["bytes"]["code_bytes"] = 71000
    assert guard.budgets_relaxations(base, head) == []


def test_budgets_guard_every_budget_may_only_fall():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    # every budget raised by one: six findings, one per raised leaf
    head["bytes"]["code_bytes"] += 1
    for journey in head["journeys"].values():
        for metric in journey:
            journey[metric] += 1
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 6
    assert all("raised; it may only fall" in line for line in findings)


def test_budgets_guard_schema_version_is_fixed():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document(schema=2)
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "schema_version changed" in findings[0]


def test_budgets_guard_key_removed_is_a_finding():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    del head["journeys"]["hover"]
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 2  # the journey's two budget leaves
    assert all("key removed" in line for line in findings)
    assert all("journeys.hover" in line for line in findings)


def test_budgets_guard_key_added_is_a_finding():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    # a PR adding a journey budget is a change -- it must not be able to
    # mask a raise elsewhere, so additions are refused, matching the
    # coverage document's shape
    head["journeys"]["scroll"] = {"dom_nodes_mutated": 1,
                                  "long_task_count": 0}
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 2
    assert all("key added" in line for line in findings)
    assert all("journeys.scroll" in line for line in findings)


def test_budgets_guard_string_value_is_not_a_finite_number():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    head["bytes"]["code_bytes"] = "71627"
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "not a finite number" in findings[0]


def test_budgets_guard_boolean_value_is_not_a_finite_number():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    head["journeys"]["load"]["long_task_count"] = True
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "not a finite number" in findings[0]


def test_budgets_guard_deleted_document_is_a_finding():
    guard = _guard()
    findings = guard.budgets_relaxations(_budgets_document(), None)
    assert findings == [
        '.github/perf-budgets.json: (document): merge base "present", '
        'head absent — the document was deleted'
    ]


def test_budgets_guard_absent_at_merge_base_is_clean():
    guard = _guard()
    assert guard.budgets_relaxations(None, _budgets_document()) == []


# --- the budgets guard: end-to-end git cases ---------------------------------


def test_end_to_end_budgets_raise_is_flagged(tmp_path, capsys, monkeypatch):
    """Raising a perf budget relaxes the ratchet: one finding, exit 1."""
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 71628
    head = _commit_budgets_on_branch(repo, raised, "raise a budget")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 1
    assert "raised; it may only fall" in findings[0]
    assert ".github/perf-budgets.json" in findings[0]
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 1
    assert "relaxation(s)" in capsys.readouterr().out


def test_end_to_end_budgets_tighten_is_clean(tmp_path, capsys, monkeypatch):
    """Lowering budgets tightens: clean, and ALL THREE documents report ok
    in one run — the guard checks all three in the same pass."""
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    tightened = _budgets_document()
    tightened["journeys"]["load"]["long_task_count"] = 1
    tightened["bytes"]["code_bytes"] = 71000
    head = _commit_budgets_on_branch(repo, tightened, "tighten the budgets")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 0
    out = capsys.readouterr().out
    assert out.count("not relaxed") == 3


def test_end_to_end_budgets_schema_version_is_fixed(tmp_path):
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    head = _commit_budgets_on_branch(
        repo, _budgets_document(schema=2), "bump the schema version")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 1
    assert "schema_version changed" in findings[0]


def test_end_to_end_budgets_key_add_and_remove_are_findings(tmp_path):
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    reshaped = _budgets_document()
    del reshaped["journeys"]["hover"]
    reshaped["journeys"]["scroll"] = {"dom_nodes_mutated": 1,
                                      "long_task_count": 0}
    head = _commit_budgets_on_branch(repo, reshaped, "swap a journey")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 4
    assert all("journeys.hover" in f for f in findings[:2])
    assert all("key removed" in f for f in findings[:2])
    assert all("journeys.scroll" in f for f in findings[2:])
    assert all("key added" in f for f in findings[2:])


def test_end_to_end_both_documents_are_guarded_in_one_run(tmp_path):
    """One branch lowers the calibration AND raises a budget: the guard
    reports both documents' findings in the same pass."""
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _thresholds().write(repo / ".github" / "ci-thresholds.json",
                        _document(measured="90.0", floor="88.5"))
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "lower the calibration")
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] += 100
    _budgets_written(repo, raised)
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "raise a budget")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert any(".github/ci-thresholds.json" in f and "lowered" in f
               for f in findings)
    assert any(".github/perf-budgets.json" in f and "raised; it may only "
               "fall" in f for f in findings)


def test_end_to_end_budgets_absent_from_history_is_clean(tmp_path):
    """A repo (or an old tag) predating the budgets document: absent on
    both sides relaxes nothing."""
    repo = _seed_repo(tmp_path, _document())
    head = _commit_budgets_on_branch(repo, _budgets_document(),
                                     "introduce the budgets document")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []


# --- the guard: the instruction budgets document (issue #110) -----------------


def _instruction_budgets_document(schema=1):
    """The committed instruction budgets document's shape, as test values.

    Three integer maxima, one per pipeline target; these are the values
    this branch committed -- the measured medians plus 3%, rounded up to
    the next million (the basis lives in
    tests/test_ci_instruction_budgets.py and CONTRIBUTING.md)."""
    return {
        "schema_version": schema,
        "scripts": {
            "build": 161000000,
            "capture_gate": 248000000,
            "diff_aa": 208000000,
        },
    }


def test_instruction_budgets_guard_identical_documents_are_clean():
    guard = _guard()
    base = _instruction_budgets_document()
    # round-trip the way the guard itself reads a document: JSON text
    # parsed back with numbers as Decimals
    round_trip = json.loads(json.dumps(base), parse_float=Decimal,
                            parse_int=Decimal)
    assert guard.instruction_budgets_relaxations(base, round_trip) == []


def test_instruction_budgets_guard_raised_budget_is_a_finding():
    guard = _guard()
    base, head = _instruction_budgets_document(), _instruction_budgets_document()
    head["scripts"]["build"] += 1
    findings = guard.instruction_budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "raised; it may only fall" in findings[0]
    assert "scripts.build" in findings[0]
    assert ".github/instruction-budgets.json" in findings[0]


def test_instruction_budgets_guard_lowered_budget_is_clean():
    """A lowered budget is the ratchet tightening itself: clean."""
    guard = _guard()
    base, head = _instruction_budgets_document(), _instruction_budgets_document()
    head["scripts"]["diff_aa"] -= 1
    head["scripts"]["build"] -= 1000
    assert guard.instruction_budgets_relaxations(base, head) == []


def test_instruction_budgets_guard_every_budget_may_only_fall():
    guard = _guard()
    base, head = _instruction_budgets_document(), _instruction_budgets_document()
    # every budget raised by one: three findings, one per raised leaf
    for name in head["scripts"]:
        head["scripts"][name] += 1
    findings = guard.instruction_budgets_relaxations(base, head)
    assert len(findings) == 3
    assert all("raised; it may only fall" in line for line in findings)


def test_instruction_budgets_guard_schema_version_is_fixed():
    guard = _guard()
    base, head = _instruction_budgets_document(), _instruction_budgets_document(
        schema=2)
    findings = guard.instruction_budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "schema_version changed" in findings[0]


def test_instruction_budgets_guard_key_removed_and_added_are_findings():
    """A PR must not be able to mask a raise behind a reshuffle: removing
    a target's budget and adding another one are each findings."""
    guard = _guard()
    base, head = _instruction_budgets_document(), _instruction_budgets_document()
    del head["scripts"]["capture_gate"]
    head["scripts"]["fetch_aa"] = 1
    findings = guard.instruction_budgets_relaxations(base, head)
    assert len(findings) == 2
    assert all("scripts.capture_gate" in f for f in findings[:1])
    assert all("key removed" in f for f in findings[:1])
    assert all("scripts.fetch_aa" in f for f in findings[1:])
    assert all("key added" in f for f in findings[1:])


def test_instruction_budgets_guard_absent_at_merge_base_is_clean():
    guard = _guard()
    assert guard.instruction_budgets_relaxations(
        None, _instruction_budgets_document()) == []


def test_instruction_budgets_guard_non_finite_leaf_fails_closed():
    """A NaN/Infinity literal leaf is a finding, never a crash, a silent
    pass or a misjudged raise -- the same fail-closed walk the other two
    documents get."""
    guard = _guard()
    for poison in (float("nan"), float("inf"), float("-inf")):
        base, head = _instruction_budgets_document(), _instruction_budgets_document()
        head["scripts"]["build"] = poison
        findings = guard.instruction_budgets_relaxations(base, head)
        assert len(findings) == 1, (poison, findings)
        assert "scripts.build" in findings[0]
        assert "not a finite number" in findings[0]


# --- the instruction budgets guard: end-to-end git cases ----------------------


def test_end_to_end_instruction_budgets_raise_is_flagged(tmp_path, capsys,
                                                         monkeypatch):
    """Raising an instruction budget relaxes the ratchet: one finding,
    exit 1, named against the third document."""
    repo = _seed_repo(tmp_path, _document(),
                      instruction_budgets=_instruction_budgets_document())
    raised = _instruction_budgets_document()
    raised["scripts"]["build"] += 100
    _git(repo, "checkout", "-q", "-b", "pr")
    _instruction_budgets_written(repo, raised)
    _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", "raise an instruction budget")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 1
    assert ".github/instruction-budgets.json" in findings[0]
    assert "raised; it may only fall" in findings[0]
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 1
    assert "relaxation(s)" in capsys.readouterr().out


def test_end_to_end_instruction_budgets_tighten_is_clean(tmp_path, capsys,
                                                         monkeypatch):
    """Lowering an instruction budget tightens: clean, and the guard's
    clean run reports all three documents ok in one pass."""
    repo = _seed_repo(tmp_path, _document(),
                      instruction_budgets=_instruction_budgets_document())
    tightened = _instruction_budgets_document()
    tightened["scripts"]["build"] -= 1_000_000
    _git(repo, "checkout", "-q", "-b", "pr")
    _instruction_budgets_written(repo, tightened)
    _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", "tighten an instruction budget")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 0
    assert capsys.readouterr().out.count("not relaxed") == 3


def test_end_to_end_instruction_budgets_absent_from_history_is_clean(tmp_path):
    """A repo predating the third document: absent at the merge base,
    the branch's new document relaxes nothing."""
    repo = _seed_repo(tmp_path, _document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _instruction_budgets_written(repo, _instruction_budgets_document())
    _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", "introduce the instruction budgets")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []


def test_end_to_end_all_three_documents_guarded_in_one_run(tmp_path):
    """One branch lowers the calibration, raises a perf budget AND raises
    an instruction budget: the guard reports all three documents'
    findings in the same pass."""
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document(),
                      instruction_budgets=_instruction_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _thresholds().write(repo / ".github" / "ci-thresholds.json",
                        _document(measured="90.0", floor="88.5"))
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "lower the calibration")
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] += 100
    _budgets_written(repo, raised)
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "raise a perf budget")
    raised_instructions = _instruction_budgets_document()
    raised_instructions["scripts"]["capture_gate"] += 1_000_000
    _instruction_budgets_written(repo, raised_instructions)
    _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", "raise an instruction budget")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert any(".github/ci-thresholds.json" in f and "lowered" in f
               for f in findings)
    assert any(".github/perf-budgets.json" in f and "raised; it may only "
               "fall" in f for f in findings)
    assert any(".github/instruction-budgets.json" in f and "raised; it may "
               "only fall" in f for f in findings)


# --- the guard: non-finite float leaves fail closed --------------------------


def test_guard_nan_and_infinity_leaves_fail_closed_in_both_walks():
    """A NaN/Infinity literal leaf is a finding, never a crash, a silent
    pass or a misjudged raise — in both documents' walks.

    json's reader hands NaN/Infinity literals back as FLOATS, past the
    parse_float hook that would have made them Decimals, so _is_number's
    float arm must finite-check them. Before that check a poisoned
    budget compared as a number and passed the down-only walk clean
    (NaN, -Infinity never compare greater) or read as a genuine raise
    (+Infinity).
    """
    guard = _guard()

    def poison_javascript_measured(doc, value):
        doc["coverage"]["javascript"]["measured"] = value

    def poison_bytes_raw(doc, value):
        doc["bytes"]["code_bytes"] = value

    cases = (
        (guard.coverage_relaxations, _document,
         poison_javascript_measured, "coverage.javascript.measured"),
        (guard.budgets_relaxations, _budgets_document,
         poison_bytes_raw, "bytes.code_bytes"),
    )
    for relaxations, build_doc, poison_leaf, path in cases:
        for poison in (float("nan"), float("inf"), float("-inf")):
            base, head = build_doc(), build_doc()
            poison_leaf(head, poison)
            findings = relaxations(base, head)
            assert len(findings) == 1, (path, poison, findings)
            assert path in findings[0], findings[0]
            assert "not a finite number" in findings[0]


def test_end_to_end_non_finite_budget_head_fails_closed(tmp_path, capsys,
                                                        monkeypatch):
    """A head budgets document carrying a NaN literal: exit 1 through the
    normal findings path — never a crash, never a silent pass."""
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    poisoned = _budgets_document()
    poisoned["bytes"]["code_bytes"] = float("nan")
    # json.dumps writes the NaN literal here, and the guard's reader
    # parses it back to a non-finite float — the exact shape a poisoned
    # commit would carry.
    (repo / ".github" / "perf-budgets.json").write_text(
        json.dumps(poisoned), encoding="utf-8")
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "poison a budget with NaN")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head]) == 1
    out = capsys.readouterr().out
    assert "bytes.code_bytes" in out
    assert "not a finite number" in out
    assert "relaxation(s)" in out


def test_guard_finite_unchanged_leaves_stay_clean():
    """The poison tests' control: finite unchanged inputs produce zero
    findings in both walks."""
    guard = _guard()
    for relaxations, build_doc in ((guard.coverage_relaxations, _document),
                                   (guard.budgets_relaxations,
                                    _budgets_document)):
        base, head = build_doc(), build_doc()
        assert relaxations(base, head) == []


# --- the guard's git and rendering helpers, pinned directly ------------------


def test_guard_unit_helpers_pin_their_contract():
    # white-box: these rendering helpers are the contract under test
    # pylint: disable=protected-access
    guard = _guard()
    assert guard._decimal(94.2) == Decimal("94.2")
    # an unserializable value falls back to its repr, never a crash
    assert guard._show(object()).startswith("<")
    assert guard._key_path([]) == "(document)"
    # a key part that is not a plain identifier renders as JSON text
    assert guard._key_path(["a b"]) == '["a b"]'


def test_guard_changed_leaf_without_a_direction_is_a_finding():
    # a coverage leaf outside the direction map must not slip through
    # unjudged when it changes: no direction means any change is a
    # finding
    guard = _guard()
    base, head = _document(), _document()
    base["coverage"]["ruby"] = {"measured": Decimal("1.0")}
    head["coverage"]["ruby"] = {"measured": Decimal("2.0")}
    findings = guard.coverage_relaxations(base, head)
    assert len(findings) == 1
    assert "changed, and has no tightening direction" in findings[0]


def test_guard_merge_base_non_number_is_a_finding():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    base["bytes"]["code_bytes"] = "corrupt"
    head["bytes"]["code_bytes"] = 5
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "merge-base value is not a finite number" in findings[0]


def test_guard_git_failure_outside_a_repository_is_refused(tmp_path):
    guard = _guard()
    with pytest.raises(ValueError, match="cannot tell whether"):
        guard.require_full_history(tmp_path)


def test_end_to_end_unrelated_histories_are_refused(tmp_path):
    """Orphan histories share no merge base: the guard refuses rather
    than guessing a comparison."""
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    _git(repo, "checkout", "-q", "--orphan", "isolated")
    (repo / ".github" / "ci-thresholds.json").write_text(
        json.dumps({"schema_version": 1}), encoding="utf-8")
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "an unrelated history")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    with pytest.raises(ValueError, match="no merge base"):
        guard.check_ratchets(repo, "main", head)


def test_entry_kind_refuses_an_unreadable_object(tmp_path):
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    guard = _guard()
    with pytest.raises(ValueError, match="cannot list"):
        guard.entry_kind(repo, "f" * 40, ".github/ci-thresholds.json")


def test_read_document_refuses_a_non_regular_entry(tmp_path):
    repo = _seed_repo(tmp_path, _document(), budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    target = repo / ".github" / "ci-thresholds.json"
    target.unlink()
    target.symlink_to("elsewhere.json")
    _git(repo, "add", ".github/ci-thresholds.json")
    _git(repo, "commit", "-qm", "swap the document for a symlink")
    guard = _guard()
    with pytest.raises(ValueError, match="not a regular file"):
        guard.read_document(repo, "HEAD", ".github/ci-thresholds.json")
