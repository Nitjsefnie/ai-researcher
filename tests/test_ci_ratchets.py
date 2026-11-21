"""Tests for the ratchet-document guard.

The perf-budgets document (.github/perf-budgets.json) holds integer
maxima, so the guard's relaxation is the RAISE: schema_version is fixed,
and key add/remove are findings. The instruction-budgets document
(.github/instruction-budgets.json) — integer maxima of the pipeline
targets' startup-subtracted callgrind totals — shares the budgets'
direction rules verbatim. The guard also gets end-to-end git cases in
temporary repositories.
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


def _guard():
    return _load("check_ratchets")


# --- the guard: end-to-end git cases ----------------------------------------


def _git(repo, *args):
    return subprocess.run(("git", "-C", str(repo)) + args, check=True,
                          capture_output=True, text=True)


def _seed_repo(tmp_path, budgets=None, instruction_budgets=None):
    """Seed a repo with the committed budgets and/or instruction-budgets
    documents."""
    repo = Path(tmp_path) / "repo"
    (repo / ".github").mkdir(parents=True)
    if budgets is not None:
        _budgets_written(repo, budgets)
    if instruction_budgets is not None:
        _instruction_budgets_written(repo, instruction_budgets)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
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


def _commit_budgets_on_branch(repo, document, message, extra_path=None,
                              extra_content=None):
    """Commit the budgets document on a `pr` branch forked from main, as
    a pull request does. `extra_path`/`extra_content` ride the SAME
    commit — the per-commit purity rule's impure shape."""
    _git(repo, "checkout", "-q", "-b", "pr")
    _budgets_written(repo, document)
    if extra_path is not None:
        target = repo / extra_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(extra_content, encoding="utf-8")
        _git(repo, "add", extra_path)
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_end_to_end_main_advancing_after_the_fork_is_not_a_relaxation(
        tmp_path, monkeypatch, capsys):
    """On the PR route the merge base, not main's tip, is the reference.

    Main tightens a budget after the branch forked — a tightening the
    stale branch must not be penalised for missing. Comparing against
    main's tip instead of the merge base would read the branch's older
    value as a raise; the guard compares against the fork, so the stale
    branch is clean.
    """
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _git(repo, "checkout", "-q", "main")
    tightened = _budgets_document()
    tightened["bytes"]["code_bytes"] = 71000
    tip = _commit_budgets_here(repo, tightened,
                               "tighten on main after the branch forked")
    guard = _guard()
    fork, findings = guard.check_ratchets(repo, "main", "pr", route="pr")
    assert findings == []
    assert fork == _git(repo, "rev-parse", "pr").stdout.strip()
    assert fork != tip
    monkeypatch.chdir(repo)
    assert guard.main(["--route", "pr", "main", "pr"]) == 0
    assert capsys.readouterr().out.count(f"against merge base {fork} — ok") == 2


def test_end_to_end_branch_raise_while_main_advanced_is_flagged(tmp_path):
    """Main's tightening does not make the branch's own raise acceptable."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _git(repo, "checkout", "-q", "main")
    tightened = _budgets_document()
    tightened["bytes"]["code_bytes"] = 71000
    _commit_budgets_here(repo, tightened,
                         "tighten on main after the branch forked")
    _git(repo, "checkout", "-q", "pr")
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 72000
    head = _commit_budgets_here(repo, raised, "raise on the branch")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head, route="pr")
    assert len(findings) == 1
    assert "raised; it may only fall" in findings[0]


def test_end_to_end_shallow_repository_is_refused(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    clone = Path(tmp_path) / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(clone)],
        check=True, capture_output=True)
    guard = _guard()
    with pytest.raises(ValueError, match="shallow"):
        guard.check_ratchets(clone, "main", "main")


def test_end_to_end_document_absent_at_merge_base_is_clean(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "rm", "-q", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "remove the document")
    # the branch reintroduces the document against a merge base that
    # lacks it — nothing there to relax
    head = _commit_budgets_on_branch(repo, _budgets_document(),
                                     "reintroduce the document")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []


def test_end_to_end_symlink_head_entry_is_a_finding(tmp_path, monkeypatch):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    target = repo / ".github" / "perf-budgets.json"
    target.unlink()
    target.symlink_to("elsewhere.json")
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "swap the document for a symlink")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", "pr")
    assert findings == [
        '.github/perf-budgets.json: (document): reference "100644 blob", '
        'head "120000 blob" — not a regular file'
    ]
    monkeypatch.chdir(repo)
    assert guard.main(["main", "pr"]) == 1


def test_end_to_end_invalid_json_at_head_is_a_git_error(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    (repo / ".github" / "perf-budgets.json").write_text(
        "{not json", encoding="utf-8")
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "break the document")
    guard = _guard()
    with pytest.raises(ValueError, match="not valid JSON"):
        guard.check_ratchets(repo, "main", "pr")


def test_end_to_end_unknown_revision_is_exit_2(tmp_path):
    _seed_repo(tmp_path, budgets=_budgets_document())
    guard = _guard()
    assert guard.main(["main", "no-such-revision"]) == 2


def test_end_to_end_push_raise_on_main_is_flagged(tmp_path, capsys,
                                                  monkeypatch):
    """The push path's shape: AI_RESEARCHER_BEFORE..HEAD, both tips of main.

    The workflow passes main's previous and new tips to the guard; a
    direct-push raise must be flagged like a branch's raise.
    main() runs in-process so coverage.py can trace the guard's lines.
    """
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 72000
    head = _commit_budgets_here(repo, raised, "raise a budget by direct push")
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head]) == 1
    assert "relaxation(s)" in capsys.readouterr().out


def test_end_to_end_push_tighten_on_main_is_clean(tmp_path, capsys,
                                                  monkeypatch):
    """A tightening push only lowers values, so against its parent it
    relaxes nothing."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    tightened = _budgets_document()
    tightened["bytes"]["code_bytes"] = 71000
    head = _commit_budgets_here(repo, tightened, "tighten a budget")
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head]) == 0
    assert "not relaxed" in capsys.readouterr().out


# --- the guard: the budgets document -----------------------------------------


def _budgets_document(schema=1):
    """The committed budgets document's shape, as test values.

    One code-only byte budget, absolute long-task maxima, and hover DOM --
    the load/filter/sort DOM counts have no leaves because they are never
    gated.
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
    # mask a raise elsewhere, so additions are refused
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
        '.github/perf-budgets.json: (document): reference "present", '
        'head absent — the document was deleted'
    ]


def test_budgets_guard_absent_at_merge_base_is_clean():
    guard = _guard()
    assert guard.budgets_relaxations(None, _budgets_document()) == []


# --- the budgets guard: end-to-end git cases ---------------------------------


def test_end_to_end_budgets_raise_is_flagged(tmp_path, capsys, monkeypatch):
    """Raising a perf budget relaxes the ratchet: one finding, exit 1."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
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
    """Lowering budgets tightens: clean, and BOTH documents report ok in
    one run — the guard checks both in the same pass."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
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
    assert out.count("not relaxed") == 2


def test_end_to_end_budgets_schema_version_is_fixed(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    head = _commit_budgets_on_branch(
        repo, _budgets_document(schema=2), "bump the schema version")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert len(findings) == 1
    assert "schema_version changed" in findings[0]


def test_end_to_end_budgets_key_add_and_remove_are_findings(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
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


def test_end_to_end_budgets_absent_from_history_is_clean(tmp_path):
    """A repo (or an old tag) predating the budgets document: absent on
    both sides relaxes nothing."""
    repo = _seed_repo(tmp_path,
                      instruction_budgets=_instruction_budgets_document())
    head = _commit_budgets_on_branch(repo, _budgets_document(),
                                     "introduce the budgets document")
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []


# --- the guard: the instruction budgets document ------------------------------


def _instruction_budgets_document(schema=1):
    """The committed instruction budgets document's shape, as test values.

    Three integer maxima, one per pipeline target; these are the values
    this branch committed -- the CI coverage cell's first measured counts
    plus 3%, rounded up to the next million (the basis lives in
    CONTRIBUTING.md)."""
    return {
        "schema_version": schema,
        "scripts": {
            "build": 177000000,
            "capture_gate": 276000000,
            "diff_aa": 230000000,
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
    exit 1, named against the second document."""
    repo = _seed_repo(tmp_path,
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
    clean run reports both documents ok in one pass."""
    repo = _seed_repo(tmp_path,
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
    assert capsys.readouterr().out.count("not relaxed") == 2


def test_end_to_end_instruction_budgets_absent_from_history_is_clean(tmp_path):
    """A repo predating the second document: absent at the merge base,
    the branch's new document relaxes nothing."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    _instruction_budgets_written(repo, _instruction_budgets_document())
    _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", "introduce the instruction budgets")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    _fork, findings = guard.check_ratchets(repo, "main", head)
    assert findings == []


def test_end_to_end_both_documents_guarded_in_one_run(tmp_path):
    """One branch raises a perf budget AND an instruction budget: the
    guard reports both documents' findings in the same pass."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document(),
                      instruction_budgets=_instruction_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
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
    float arm must finite-check them. Unchecked, a poisoned budget would
    compare as a number: NaN and -Infinity never compare greater, so they
    would pass the down-only walk clean, and +Infinity would read as a
    genuine raise.
    """
    guard = _guard()

    def poison_build_instructions(doc, value):
        doc["scripts"]["build"] = value

    def poison_bytes_raw(doc, value):
        doc["bytes"]["code_bytes"] = value

    cases = (
        (guard.instruction_budgets_relaxations, _instruction_budgets_document,
         poison_build_instructions, "scripts.build"),
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
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
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
    for relaxations, build_doc in ((guard.instruction_budgets_relaxations,
                                    _instruction_budgets_document),
                                   (guard.budgets_relaxations,
                                    _budgets_document)):
        base, head = build_doc(), build_doc()
        assert relaxations(base, head) == []


# --- the guard's git and rendering helpers, pinned directly ------------------


def test_guard_unit_helpers_pin_their_contract():
    # white-box: these rendering helpers are the contract under test
    # pylint: disable=protected-access
    guard = _guard()
    # an unserializable value falls back to its repr, never a crash
    assert guard._show(object()).startswith("<")
    assert guard._key_path([]) == "(document)"
    # a key part that is not a plain identifier renders as JSON text
    assert guard._key_path(["a b"]) == '["a b"]'


def test_guard_reference_non_number_is_a_finding():
    guard = _guard()
    base, head = _budgets_document(), _budgets_document()
    base["bytes"]["code_bytes"] = "corrupt"
    head["bytes"]["code_bytes"] = 5
    findings = guard.budgets_relaxations(base, head)
    assert len(findings) == 1
    assert "reference value is not a finite number" in findings[0]


def test_guard_git_failure_outside_a_repository_is_refused(tmp_path):
    guard = _guard()
    with pytest.raises(ValueError, match="cannot tell whether"):
        guard.require_full_history(tmp_path)


def test_end_to_end_unrelated_histories_are_refused(tmp_path):
    """The PR route refuses orphan histories with no merge base."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "--orphan", "isolated")
    (repo / ".github" / "perf-budgets.json").write_text(
        json.dumps({"schema_version": 1}), encoding="utf-8")
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "an unrelated history")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    with pytest.raises(ValueError, match="no merge base"):
        guard.check_ratchets(repo, "main", head, route="pr")


def test_end_to_end_push_with_unrelated_identical_documents_is_clean(
        tmp_path, monkeypatch):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "--orphan", "rewritten")
    _git(repo, "commit", "-qm", "Rewrite the root with the same tree")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    before = _git(repo, "rev-parse", "main").stdout.strip()
    guard = _guard()
    reference, findings = guard.check_ratchets(repo, before, head)
    assert reference == before
    assert findings == []
    monkeypatch.chdir(repo)
    assert guard.main(["--allow-declared-raises", before, head]) == 0


def test_entry_kind_refuses_an_unreadable_object(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    guard = _guard()
    with pytest.raises(ValueError, match="cannot list"):
        guard.entry_kind(repo, "f" * 40, ".github/perf-budgets.json")


def test_read_document_refuses_a_non_regular_entry(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    _git(repo, "checkout", "-q", "-b", "pr")
    target = repo / ".github" / "perf-budgets.json"
    target.unlink()
    target.symlink_to("elsewhere.json")
    _git(repo, "add", ".github/perf-budgets.json")
    _git(repo, "commit", "-qm", "swap the document for a symlink")
    guard = _guard()
    with pytest.raises(ValueError, match="not a regular file"):
        guard.read_document(repo, "HEAD", ".github/perf-budgets.json")


# --- declared budget raises: the push route -----------------------------------


def _declaration(document, key, was, to):
    return f"Budget-Raise: {document} {key} {was} -> {to}"


def _push_message(*lines):
    """A push commit message body carrying declaration lines."""
    return "\n".join(["Raise budgets", "", *lines])


def _commit_budgets_here(repo, document, message, allow_empty=False):
    """Commit the budgets document on the checked-out branch — main, as
    the raise route's direct push lands it. allow_empty serves the
    tests whose declaration lines ride a commit that changes nothing."""
    _budgets_written(repo, document)
    _git(repo, "add", ".github/perf-budgets.json")
    if allow_empty:
        _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    else:
        _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _workflow_push_check(repo, before, head):
    return subprocess.run(  # pylint: disable=subprocess-run-check
        [sys.executable, str(REPO_ROOT / "scripts/ci/check_ratchets.py"),
         "--allow-declared-raises", before, head], cwd=repo,
        capture_output=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def _rewrite_commits(repo, fork, commits):
    parent = fork
    for commit in commits:
        tree = _git(repo, "rev-parse", f"{commit}^{{tree}}").stdout.strip()
        parent = _git(repo, "commit-tree", tree, "-p", parent,
                      "-m", "Rewrite the same tree").stdout.strip()
    return parent


def _rewritten_budget_push(tmp_path):
    repo = _seed_repo(tmp_path, budgets=_budgets_document(),
                      instruction_budgets=_instruction_budgets_document())
    fork = _git(repo, "rev-parse", "HEAD").stdout.strip()
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _commit_budgets_here(repo, raised, _push_message(_declaration(
        ".github/perf-budgets.json", "bytes.code_bytes", 71627, 79700)))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: add a chart")
    raise_tip = _git(repo, "rev-parse", "HEAD").stdout.strip()
    landed = _workflow_push_check(repo, fork, raise_tip)
    assert landed.returncode == 0, landed.stdout + landed.stderr
    (repo / "page.html").write_text("Rebuilt page\n", encoding="utf-8")
    _git(repo, "add", "page.html")
    _git(repo, "commit", "-qm", "Rebuild the page")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return repo, before, _rewrite_commits(repo, fork, (raise_tip, before))


def _assert_non_fast_forward(repo, before, head):
    ancestry = subprocess.run(  # pylint: disable=subprocess-run-check
        ["git", "merge-base", "--is-ancestor", before, head], cwd=repo,
        capture_output=True, encoding="utf-8")
    assert ancestry.returncode == 1, ancestry.stderr


def test_end_to_end_rewritten_push_with_identical_ratchets_is_clean(tmp_path):
    repo, before, head = _rewritten_budget_push(tmp_path)
    _assert_non_fast_forward(repo, before, head)
    for document in (".github/perf-budgets.json",
                     ".github/instruction-budgets.json"):
        blobs = [subprocess.run(
            ["git", "show", f"{rev}:{document}"], cwd=repo, check=True,
            capture_output=True).stdout for rev in (before, head)]
        assert blobs[0] == blobs[1]
    result = _workflow_push_check(repo, before, head)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count(f"against base revision {before} — ok") == 2


def test_end_to_end_rewritten_push_cannot_declare_an_additional_raise(tmp_path):
    repo, before, rewritten = _rewritten_budget_push(tmp_path)
    _git(repo, "checkout", "-q", "-b", "rewritten", rewritten)
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 80000
    head = _commit_budgets_here(repo, raised, _push_message(_declaration(
        ".github/perf-budgets.json", "bytes.code_bytes", 79700, 80000)))
    _assert_non_fast_forward(repo, before, head)
    result = _workflow_push_check(repo, before, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert (".github/perf-budgets.json: bytes.code_bytes: reference 79700, "
            "head 80000 — raised; it may only fall") in result.stdout
    assert ("Budget-Raise declarations apply only on a fast-forward push "
            "of main — this comparison is not one") in result.stdout
    assert f"against base revision {before};" in result.stdout


def test_end_to_end_push_declared_raise_is_clean(tmp_path, capsys,
                                                 monkeypatch):
    """The push route: a deliberate raise lands on main as its own commit,
    its message carrying one Budget-Raise line per raised leaf with the
    exact values the diff carries. The push invocation
    (--allow-declared-raises) passes it; the clean run prints no route
    hint."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    before = _git(repo, "rev-parse", "main").stdout.strip()
    _commit_budgets_here(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: add a chart")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 0
    out = capsys.readouterr().out
    assert out.count("not relaxed") == 2
    assert "Budget-Raise: <document>" not in out


def test_end_to_end_push_undeclared_raise_refuses_with_the_route_hint(
        tmp_path, capsys, monkeypatch):
    """The brief's non-negotiable: a raise with no declaration refuses
    even on the push path, and the refusal teaches the route."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(repo, raised, "Raise code_bytes, no line")
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "bytes.code_bytes" in out
    assert "raised; it may only fall" in out
    assert "Budget-Raise: <document> <key> <from> -> <to>" in out


@pytest.mark.parametrize("document,build_doc,write_doc,section,key,to", [
    (".github/perf-budgets.json", _budgets_document, _budgets_written,
     "bytes", "code_bytes", 79700),
    (".github/instruction-budgets.json", _instruction_budgets_document,
     _instruction_budgets_written, "scripts", "build", 999999999),
])
@pytest.mark.parametrize("feat_sibling", [True, False])
def test_end_to_end_push_declared_raise_requires_feat(
        tmp_path, capsys, monkeypatch, document, build_doc, write_doc,
        section, key, to, feat_sibling):
    """An exact push declaration needs a feat subject inside base..head."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document(),
                      instruction_budgets=_instruction_budgets_document())
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: earlier work")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    raised = build_doc()
    was = raised[section][key]
    raised[section][key] = to
    write_doc(repo, raised)
    _git(repo, "add", document)
    _git(repo, "commit", "-qm", "fix: raise budgets\n\n" + _declaration(
        document, f"{section}.{key}", was, to))
    if feat_sibling:
        _git(repo, "commit", "-q", "--allow-empty", "-m",
             "feat: add a chart")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == (
        0 if feat_sibling else 1)
    out = capsys.readouterr().out
    if feat_sibling:
        assert out.count("not relaxed") == 2
    else:
        assert "feat:" in out
        assert "feat(<scope>):" in out
        assert "CONTRIBUTING.md" in out
        assert "1 relaxation(s)" in out


@pytest.mark.parametrize("subject", ["feat: add a chart",
                                     "feat(charts): add a chart"])
def test_end_to_end_pull_request_declared_raise_is_clean(tmp_path, capsys,
                                                         monkeypatch, subject):
    """The PR route applies the same rules the push route applies. The
    window is the merge commit's own commits (HEAD^1..HEAD^2), so a pure
    raise commit carrying perfectly formed declaration lines passes with
    a feat sibling: --allow-declared-raises --route pr is the invocation
    the workflow's PR branch makes."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _commit_budgets_on_branch(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)))
    _git(repo, "commit", "-q", "--allow-empty", "-m", subject)
    head = _git(repo, "rev-parse", "pr").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head, "--allow-declared-raises",
                       "--route", "pr"]) == 0
    out = capsys.readouterr().out
    assert out.count("not relaxed") == 2
    assert "cannot ride a pull request" not in out


@pytest.mark.parametrize("subject", [
    "fix: repair a chart", "feature: add a chart", "feat!: add a chart",
    "feat(charts)add a chart", "feat(charts):add a chart", "feat(): add a chart",
    "fix: mention feat: in the subject\n\nfeat: only in the body",
])
def test_end_to_end_pull_request_declared_raise_without_feat_refuses(
        tmp_path, capsys, monkeypatch, subject):
    """A pure, exact declaration needs a feat subject in this PR's window."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    # A feature on the base is outside the window and cannot qualify it.
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: earlier work")
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _commit_budgets_on_branch(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", 71627, 79700)))
    _git(repo, "commit", "-q", "--allow-empty", "-m", subject)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head, "--allow-declared-raises",
                       "--route", "pr"]) == 1
    out = capsys.readouterr().out
    assert "feat:" in out
    assert "feat(<scope>):" in out
    assert "CONTRIBUTING.md" in out


def test_end_to_end_pull_request_without_declarations_needs_no_feat(
        tmp_path, capsys, monkeypatch):
    """Ordinary fix PRs stay clean when no declaration lines exist."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    tightened = _budgets_document()
    tightened["bytes"]["code_bytes"] = 71000
    head = _commit_budgets_on_branch(repo, tightened, "fix: trim page code")
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head, "--allow-declared-raises",
                       "--route", "pr"]) == 0
    assert capsys.readouterr().out.count("not relaxed") == 2


def test_end_to_end_pull_request_route_survives_a_moved_base(
        tmp_path, capsys, monkeypatch):
    """The route clause's discriminating input: main advanced past the
    fork point, so `main` is NOT an ancestor of the PR head. Requiring
    ancestry on the PR declaration route would refuse this pure declared
    raise after main advances; the PR route must still accept it."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _commit_budgets_on_branch(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: add a chart")
    head = _git(repo, "rev-parse", "pr").stdout.strip()
    (repo / "UNRELATED.md").write_text("main moved on", encoding="utf-8")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "add", "UNRELATED.md")
    _git(repo, "commit", "-qm", "an unrelated main commit lands first")
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head, "--allow-declared-raises",
                       "--route", "pr"]) == 0
    out = capsys.readouterr().out
    assert out.count("not relaxed") == 2


def test_end_to_end_pull_request_impure_carrier_refuses(tmp_path, capsys,
                                                        monkeypatch):
    """The purity rule crosses to the PR route unchanged, and it is a
    PER-COMMIT rule exactly as on the push route: a commit carrying
    declaration lines must touch nothing outside the two budget
    documents. The raise commit itself carries the code edit here, so
    the finding names the foreign path; a separate sibling code commit
    with no lines is the push route's own allowed shape."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _commit_budgets_on_branch(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)),
        extra_path="build.py", extra_content="# touched\n")
    head = _git(repo, "rev-parse", "pr").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head, "--allow-declared-raises",
                       "--route", "pr"]) == 1
    out = capsys.readouterr().out
    assert "carries declaration lines but also touches" in out
    assert "build.py" in out


def test_end_to_end_pull_request_undeclared_raise_refuses(tmp_path, capsys,
                                                          monkeypatch):
    """Undeclared raises refuse on the PR route exactly as on the push
    route, and the refusal teaches the route."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _commit_budgets_on_branch(repo, raised, "Raise code_bytes, no line")
    head = _git(repo, "rev-parse", "pr").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main(["main", head, "--allow-declared-raises",
                       "--route", "pr"]) == 1
    out = capsys.readouterr().out
    assert "raised; it may only fall" in out
    assert "Budget-Raise: <document> <key> <from> -> <to>" in out


def test_end_to_end_mismatched_declaration_refuses(tmp_path, capsys,
                                                   monkeypatch):
    """A declaration is only as good as its values: a to that differs
    from the diff's to refuses both the raise and the declaration."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 73000
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 74000)))
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "raised; it may only fall" in out
    assert ("declaration 71627 -> 74000 does not match a raise in this "
            "diff" in out)


def test_end_to_end_declaration_without_a_raise_refuses(tmp_path, capsys,
                                                        monkeypatch):
    """An orphan declaration — well formed, on a pure commit, but the
    diff carries no raise for it — is itself a finding."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, _budgets_document(),
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", 71627, 79700)),
        allow_empty=True)
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "does not match a raise in this diff" in out


def test_end_to_end_duplicate_declaration_refuses(tmp_path, capsys,
                                                  monkeypatch):
    """Two identical lines for one raise: the raise passes on the
    first, the duplicate is a leftover and a finding."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    before = _git(repo, "rev-parse", "main").stdout.strip()
    line = _declaration(".github/perf-budgets.json", "bytes.code_bytes",
                        was, 79700)
    head = _commit_budgets_here(repo, raised, _push_message(line, line))
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "raised; it may only fall" not in out
    assert out.count("does not match a raise in this diff") == 1


def test_end_to_end_non_fast_forward_push_cannot_declare(
        tmp_path, capsys, monkeypatch):
    """The declaration route rides a fast-forward push: with the base
    not an ancestor of the head there is no push window to collect
    from, and the raise refuses."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    _git(repo, "checkout", "-q", "-b", "raise")
    _commit_budgets_here(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)))
    raise_tip = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", "main")
    (repo / "UNRELATED.md").write_text("diverged", encoding="utf-8")
    _git(repo, "add", "UNRELATED.md")
    _git(repo, "commit", "-qm", "diverge main")
    diverged_tip = _git(repo, "rev-parse", "main").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([diverged_tip, raise_tip,
                       "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "raised; it may only fall" in out
    assert ("declarations apply only on a fast-forward push of main"
            in out)


def test_end_to_end_push_declared_raises_across_both_documents(
        tmp_path, capsys, monkeypatch):
    """One push raises a leaf in each budget document, two declaration
    lines: both consumed, clean."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document(),
                      instruction_budgets=_instruction_budgets_document())
    budgets_was = _budgets_document()["bytes"]["code_bytes"]
    instructions_was = _instruction_budgets_document()["scripts"]["build"]
    raised_budgets = _budgets_document()
    raised_budgets["bytes"]["code_bytes"] = 79700
    raised_instructions = _instruction_budgets_document()
    raised_instructions["scripts"]["build"] = 999999999
    before = _git(repo, "rev-parse", "main").stdout.strip()
    _budgets_written(repo, raised_budgets)
    _git(repo, "add", ".github/perf-budgets.json")
    _instruction_budgets_written(repo, raised_instructions)
    _git(repo, "add", ".github/instruction-budgets.json")
    _git(repo, "commit", "-qm", _push_message(
        _declaration(".github/perf-budgets.json", "bytes.code_bytes",
                     budgets_was, 79700),
        _declaration(".github/instruction-budgets.json", "scripts.build",
                     instructions_was, 999999999)))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: add a chart")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 0
    assert capsys.readouterr().out.count("not relaxed") == 2


def test_end_to_end_partially_declared_raises_refuse_the_rest(
        tmp_path, capsys, monkeypatch):
    """Exactness is per leaf: a declared raise passes while an
    undeclared sibling raise in the same push still refuses."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    raised["journeys"]["hover"]["long_task_count"] = 9
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)))
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert ("journeys.hover.long_task_count" in out
            and "raised; it may only fall" in out)
    assert not any("bytes.code_bytes" in line
                   and "raised; it may only fall" in line
                   for line in out.splitlines())


def test_end_to_end_declaration_naming_the_coverage_document_refuses(
        tmp_path, capsys, monkeypatch):
    """Only the two budget documents' raises are declarable: the
    coverage document's values are test-ratchet's report job's, and a
    declaration naming it is a finding of its own."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, _budgets_document(),
        _push_message(_declaration(".github/ci-thresholds.json",
                                   "coverage.python.measured", "91.1",
                                   "92.0")),
        allow_empty=True)
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "names a document whose values are not declarable" in out


def test_declaration_parser_pins_the_line_shape():
    """White-box: the parser is the declaration format's contract."""
    # white-box: the parser is the declaration format's contract
    # pylint: disable=protected-access
    guard = _guard()
    decls, errors = guard._parse_declarations(
        ["Budget-Raise: .github/perf-budgets.json bytes.code_bytes "
         "71627 -> 79700"])
    assert decls == [(".github/perf-budgets.json", "bytes.code_bytes",
                      Decimal("71627"), Decimal("79700"))]
    assert errors == []
    decls, errors = guard._parse_declarations(
        ['Budget-Raise: .github/perf-budgets.json bytes["odd key"] '
         "1 -> 2"])
    assert decls == [(".github/perf-budgets.json", 'bytes["odd key"]',
                      Decimal("1"), Decimal("2"))]
    assert errors == []
    decls, errors = guard._parse_declarations(
        ["Budget-Raise: .github/perf-budgets.json bytes.code_bytes 71627"])
    assert decls == []
    assert len(errors) == 1
    assert "does not parse" in errors[0]


def test_declaration_collector_reads_the_push_window(tmp_path):
    """White-box: the lines come from the window base..head with their
    carrying commit, and only Budget-Raise-prefixed ones; the paths
    walk answers the same commit with its touched files."""
    # white-box: the collector is the window's contract
    # pylint: disable=protected-access
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    before = _git(repo, "rev-parse", "main").stdout.strip()
    _commit_budgets_here(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.code_bytes", was, 79700)))
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    commits = guard._commits_with_declaration_lines(repo, before, "HEAD")
    assert len(commits) == 1
    sha, lines = commits[0]
    assert sha == head
    assert lines == [
        "Budget-Raise: .github/perf-budgets.json bytes.code_bytes "
        "71627 -> 79700"]
    assert guard._commit_paths(repo, before, "HEAD") == {
        head: [".github/perf-budgets.json"]}


def test_declaration_parser_rejects_non_finite_values():
    """A non-finite token — quiet NaN, sNaN, Infinity — is a parse
    error, never a consumable: an sNaN that parsed would raise on the
    very comparison the consumption makes."""
    # white-box: the parser is the declaration format's contract
    # pylint: disable=protected-access
    guard = _guard()
    for token in ("sNaN", "nan", "Infinity", "-Infinity"):
        decls, errors = guard._parse_declarations(
            [f"Budget-Raise: .github/perf-budgets.json bytes.code_bytes "
             f"{token} -> 79700"])
        assert decls == [], token
        assert len(errors) == 1, token
        assert "does not parse" in errors[0]


def test_end_to_end_snan_declaration_cannot_crash_the_guard(
        tmp_path, capsys, monkeypatch):
    """A declaration line carrying sNaN must be a finding, never an
    uncaught decimal.InvalidOperation from the consumption's comparisons."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, raised,
        _push_message("Budget-Raise: .github/perf-budgets.json "
                      "bytes.code_bytes sNaN -> 79700"))
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "does not parse" in out
    assert "raised; it may only fall" in out


def test_end_to_end_impure_commit_cannot_declare(tmp_path, capsys,
                                                 monkeypatch):
    """A declaration only counts on its own act: a commit that carries
    declaration lines and also touches anything outside the two budget
    documents is inert and a finding, so a raise cannot ride feature
    work onto main through a squash merge."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    was = _budgets_document()["bytes"]["code_bytes"]
    raised = _budgets_document()
    raised["bytes"]["code_bytes"] = 79700
    before = _git(repo, "rev-parse", "main").stdout.strip()
    _budgets_written(repo, raised)
    _git(repo, "add", ".github/perf-budgets.json")
    (repo / "feature.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "feature.py")
    _git(repo, "commit", "-qm",
         _push_message(_declaration(".github/perf-budgets.json",
                                    "bytes.code_bytes", was, 79700)))
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "also touches" in out
    assert "raised; it may only fall" in out


def test_end_to_end_declaration_cannot_rescue_schema_version(
        tmp_path, capsys, monkeypatch):
    """Pin the exemption predicate: schema_version may not change at
    all, and a declaration naming it cannot turn the change into a
    raise."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    raised = _budgets_document(schema=2)
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, raised,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "schema_version", 1, 2)))
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "schema_version changed" in out
    assert "does not match a raise in this diff" in out


def test_end_to_end_declaration_cannot_rescue_a_key_add(
        tmp_path, capsys, monkeypatch):
    """Pin the exemption predicate: a key added is a finding a
    declaration cannot rescue."""
    repo = _seed_repo(tmp_path, budgets=_budgets_document())
    widened = _budgets_document()
    widened["bytes"]["css_bytes"] = 1000
    before = _git(repo, "rev-parse", "main").stdout.strip()
    head = _commit_budgets_here(
        repo, widened,
        _push_message(_declaration(".github/perf-budgets.json",
                                   "bytes.css_bytes", 0, 1000)))
    guard = _guard()
    monkeypatch.chdir(repo)
    assert guard.main([before, head, "--allow-declared-raises"]) == 1
    out = capsys.readouterr().out
    assert "key added" in out
    assert "does not match a raise in this diff" in out


def test_workflow_wiring_pins_the_invocations():
    """Pin the enforcement wiring: the push branch passes the flag with
    the push route, the pull-request branch passes it with the pr route
    -- the routes' differing window guarantees are the workflow's to
    name, and dropping either flag goes red here."""
    text = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8")
    assert ('check_ratchets.py --allow-declared-raises "${AI_RESEARCHER_BEFORE}" HEAD'
            in text)
    assert "--route pr HEAD^1 HEAD^2" in text
    # Exactly two invocations carry the flag; the comment's prose mention
    # names it without the script prefix, so the prefixed count pins the
    # invocations alone.
    assert text.count("check_ratchets.py --allow-declared-raises") == 2
