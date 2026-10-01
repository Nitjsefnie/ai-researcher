"""Tests for the performance-budgets loader and gate (issue #109).

The pure half of scripts/ci/perf_budgets.py: the budgets-document
validation and the gate over a measurement. No playwright anywhere in
this module -- the measurement half runs a browser and is exercised by
hand (`perf_budgets.py --measure`), never from pytest here.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    """Import a scripts/ci module by path.

    scripts/ci is not a package and deliberately has no __init__.py -- it
    holds standalone CI entry points, not an importable library.
    """
    path = REPO_ROOT / "scripts" / "ci" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


perf = _load("perf_budgets")


def _document():
    """A valid budgets document: maxima over every budgetable metric."""
    return {
        "schema_version": 1,
        "bytes": {"raw": 600000, "gzip": 120000},
        "journeys": {
            "load": {"dom_nodes_mutated": 5000, "long_task_count": 2},
            "filter": {"dom_nodes_mutated": 3000, "long_task_count": 1},
            "sort": {"dom_nodes_mutated": 8000, "long_task_count": 1},
            "hover": {"dom_nodes_mutated": 40, "long_task_count": 0},
        },
    }


def _measurement(**overrides):
    """A synthetic measurement matching _document, at or under budget."""
    journeys = {
        "load": {"dom_nodes_mutated": 4800, "long_task_count": 2,
                 "wall_ms_median": 61.0},
        "filter": {"dom_nodes_mutated": 2900, "long_task_count": 0,
                   "wall_ms_median": 9.5},
        "sort": {"dom_nodes_mutated": 7900, "long_task_count": 1,
                 "wall_ms_median": 12.0},
        "hover": {"dom_nodes_mutated": 38, "long_task_count": 0,
                  "wall_ms_median": 2.5},
    }
    data = {
        "schema_version": 1,
        "page": {"output": "frontier-models.html", "sha256": "ab" * 32},
        "bytes": {"raw": 599000, "gzip": 119000},
        "journeys": journeys,
    }
    for path, value in overrides.items():
        section, key = path.split(".", 1)
        if section == "bytes":
            data["bytes"][key] = value
        else:
            journey, metric = key.split(".", 1)
            data["journeys"][journey][metric] = value
    return data


def _written(tmp_path, payload, name="perf-budgets.json"):
    target = tmp_path / name
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


# --- budgets-document validation ---------------------------------------------


def test_valid_document_loads(tmp_path):
    doc = perf.load_budgets(_written(tmp_path, _document()))
    assert doc["schema_version"] == 1
    assert doc["bytes"] == {"raw": 600000, "gzip": 120000}
    assert doc["journeys"]["hover"] == {
        "dom_nodes_mutated": 40, "long_task_count": 0}


def test_unknown_top_level_field_refused(tmp_path):
    payload = _document()
    payload["coverage"] = {}
    with pytest.raises(ValueError, match="unknown field: coverage"):
        perf.load_budgets(_written(tmp_path, payload))


def test_unknown_journey_refused(tmp_path):
    payload = _document()
    payload["journeys"]["scroll"] = {"dom_nodes_mutated": 1,
                                     "long_task_count": 0}
    with pytest.raises(ValueError, match="unknown journey: scroll"):
        perf.load_budgets(_written(tmp_path, payload))


def test_missing_journey_refused(tmp_path):
    payload = _document()
    del payload["journeys"]["sort"]
    with pytest.raises(ValueError, match="missing journey: sort"):
        perf.load_budgets(_written(tmp_path, payload))


def test_report_only_metric_is_an_unknown_field_in_a_budget(tmp_path):
    # wall_ms_median is measured but never budgeted -- a budget document
    # that tries to cap it is refused rather than silently gating on it.
    payload = _document()
    payload["journeys"]["sort"]["wall_ms_median"] = 50
    with pytest.raises(ValueError,
                       match="unknown field.*wall_ms_median"):
        perf.load_budgets(_written(tmp_path, payload))


def test_unknown_bytes_field_refused(tmp_path):
    payload = _document()
    payload["bytes"]["brotli"] = 90000
    with pytest.raises(ValueError, match="unknown field: brotli"):
        perf.load_budgets(_written(tmp_path, payload))


def test_missing_metric_refused(tmp_path):
    payload = _document()
    del payload["journeys"]["hover"]["long_task_count"]
    with pytest.raises(ValueError, match="missing field"):
        perf.load_budgets(_written(tmp_path, payload))


def test_float_budget_refused(tmp_path):
    payload = _document()
    payload["journeys"]["filter"]["dom_nodes_mutated"] = 3000.5
    with pytest.raises(ValueError, match="must be an integer"):
        perf.load_budgets(_written(tmp_path, payload))


def test_integral_float_budget_refused(tmp_path):
    # 3000.0 is a whole number but not the canonical spelling: a budget
    # is an integer in the document, exactly like the thresholds doc's
    # one-decimal-place rule for coverage numbers.
    payload = _document()
    payload["journeys"]["filter"]["dom_nodes_mutated"] = 3000.0
    with pytest.raises(ValueError, match="must be an integer"):
        perf.load_budgets(_written(tmp_path, payload))


def test_negative_budget_refused(tmp_path):
    payload = _document()
    payload["bytes"]["gzip"] = -1
    with pytest.raises(ValueError, match="must not be negative"):
        perf.load_budgets(_written(tmp_path, payload))


def test_boolean_budget_refused(tmp_path):
    payload = _document()
    payload["bytes"]["raw"] = True
    with pytest.raises(ValueError, match="must be an integer"):
        perf.load_budgets(_written(tmp_path, payload))


def test_string_budget_refused(tmp_path):
    payload = _document()
    payload["bytes"]["raw"] = "600000"
    with pytest.raises(ValueError, match="must be a JSON number"):
        perf.load_budgets(_written(tmp_path, payload))


def test_non_finite_budget_refused(tmp_path):
    target = tmp_path / "perf-budgets.json"
    target.write_text(
        '{"schema_version": 1, "bytes": {"raw": Infinity, "gzip": 1},'
        ' "journeys": {"load": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}, "filter": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}, "sort": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}, "hover": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}}}',
        encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        perf.load_budgets(target)


def test_wrong_schema_version_refused(tmp_path):
    payload = _document()
    payload["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported schema_version"):
        perf.load_budgets(_written(tmp_path, payload))


def test_boolean_schema_version_refused(tmp_path):
    payload = _document()
    payload["schema_version"] = True
    with pytest.raises(ValueError, match="must be an integer"):
        perf.load_budgets(_written(tmp_path, payload))


def test_duplicate_key_refused(tmp_path):
    target = tmp_path / "perf-budgets.json"
    target.write_text(
        '{"schema_version": 1, "schema_version": 1, "bytes": {"raw": 1,'
        ' "gzip": 1}, "journeys": {"load": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}, "filter": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}, "sort": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}, "hover": {"dom_nodes_mutated": 1,'
        ' "long_task_count": 0}}}',
        encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        perf.load_budgets(target)


def test_invalid_json_refused(tmp_path):
    target = tmp_path / "perf-budgets.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid budgets JSON"):
        perf.load_budgets(target)


def test_non_object_document_refused(tmp_path):
    target = tmp_path / "perf-budgets.json"
    target.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="budgets must be an object"):
        perf.load_budgets(target)


# --- the gate ----------------------------------------------------------------


def test_gate_exceeded_names_journey_metric_and_both_values():
    findings = perf.gate(perf.validate_budgets(_document()), _measurement(
        **{"journeys.filter.dom_nodes_mutated": 3001}))
    assert findings == ["journeys.filter.dom_nodes_mutated: "
                        "head 3001 exceeds base 3000"]


def test_gate_bytes_exceeded():
    findings = perf.gate(perf.validate_budgets(_document()), _measurement(
        **{"bytes.gzip": 120001}))
    assert findings == ["bytes.gzip: head 120001 exceeds base 120000"]


def test_gate_equal_budget_passes():
    assert perf.gate(perf.validate_budgets(_document()), _measurement(
        **{"bytes.raw": 600000})) == []


def test_gate_below_budget_passes():
    assert perf.gate(perf.validate_budgets(_document()),
                     _measurement()) == []


def test_gate_ignores_report_only_metrics():
    # wall_ms_median rides along in every measurement journey and is
    # never gated -- even a huge wall cannot produce a finding.
    measurement = _measurement(**{"journeys.load.wall_ms_median": 99999.0})
    assert perf.gate(perf.validate_budgets(_document()), measurement) == []


def test_gate_reports_every_exceeded_budget_in_order():
    measurement = _measurement(
        **{"bytes.gzip": 200000},
        **{"journeys.load.long_task_count": 9},
        **{"journeys.hover.dom_nodes_mutated": 41})
    findings = perf.gate(perf.validate_budgets(_document()), measurement)
    assert findings == [
        "bytes.gzip: head 200000 exceeds base 120000",
        "journeys.load.long_task_count: head 9 exceeds base 2",
        "journeys.hover.dom_nodes_mutated: head 41 exceeds base 40",
    ]


def test_gate_missing_journey_in_measurement_is_loud():
    measurement = _measurement()
    del measurement["journeys"]["sort"]
    with pytest.raises(ValueError, match="missing journey: sort"):
        perf.gate(perf.validate_budgets(_document()), measurement)


def test_gate_missing_bytes_section_is_loud():
    measurement = _measurement()
    del measurement["bytes"]
    with pytest.raises(ValueError, match="missing section: bytes"):
        perf.gate(perf.validate_budgets(_document()), measurement)


# --- CLI closed behaviour, in-process ----------------------------------------


def test_check_with_missing_budgets_fails_closed(tmp_path, capsys):
    # Task 1 ships no budgets document yet: --check must refuse with
    # exit 2 and a line naming the missing path -- never measure first
    # and never pass for want of a document.
    missing = tmp_path / "absent.json"
    assert perf.main(["--check", "--budgets", str(missing)]) == 2
    captured = capsys.readouterr()
    assert str(missing) in captured.err
    assert "cannot read budgets" in captured.err


# --- module-level laziness, subprocess-isolated ------------------------------
#
# In-process assertions on sys.modules cannot work: the full suite's
# browser tests import playwright into the shared interpreter. The
# property is judged in a fresh interpreter instead.

_LAZY_IMPORT_PROBE = """
import importlib.util, pathlib, sys
root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "perf_budgets", root / "scripts" / "ci" / "perf_budgets.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert "playwright" not in sys.modules, "module import pulled in playwright"
"""

_LAZY_CHECK_PROBE = _LAZY_IMPORT_PROBE + """
rc = module.main(["--check", "--budgets",
                  str(root / ".github" / "perf-budgets.json")])
assert rc == 2, rc
assert "playwright" not in sys.modules, (
    "--check on a missing budgets file reached the browser path")
print("ok")
"""


def test_importing_the_module_never_imports_playwright():
    result = subprocess.run(
        [sys.executable, "-c", _LAZY_IMPORT_PROBE + 'print("ok")',
         str(REPO_ROOT)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "ok"


def test_check_never_reaches_the_browser_path_for_a_missing_document():
    result = subprocess.run(
        [sys.executable, "-c", _LAZY_CHECK_PROBE, str(REPO_ROOT)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "ok"
