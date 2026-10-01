"""Tests for the instruction-count budgets gate (issue #110).

Three layers, and none of them runs valgrind. The committed pipeline
fixture (tests/fixtures/pipeline/) is the fixed input every measured run
reads -- pinning the budgets to it is what keeps the ratchet invariant to
live-capture growth, so its bytes must be exactly what the generator in
this module produces and build.py must accept it and render all four
axes. The budgets-document validation and the gate itself run on
synthetic measurements. The mini-tree seeding functions are exercised on
real files and a real git repository, but the callgrind subprocesses of
the measure path run only where the gate runs: locally and in the
coverage job -- pytest here never invokes valgrind.

Every number in this module's docstrings is either labelled synthetic
(a test input, judged for its comparison behaviour only) or measured
(a callgrind total, printed by the gate; none is asserted).
"""
from __future__ import annotations

import contextlib
import functools
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

import build

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "pipeline"
FIXTURE_MODELS = FIXTURE_DIR / "aa-raw-models.json"
FIXTURE_AGENTS = FIXTURE_DIR / "aa-raw-coding-agents.json"
FIXTURE_STAMP = FIXTURE_DIR / "captured-at.txt"

# The stamp fetch_aa.py writes beside a capture, frozen at the fixture's
# introduction. build.read_capture_stamp validates the shape; capture_gate
# substitutes its own synthetic stamp ("2000-01-01") for both sides of its
# comparison and never reads this one.
FIXTURE_DATE = "2026-10-01"

COMMITTED_BUDGETS = REPO_ROOT / ".github" / "instruction-budgets.json"


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


# --- the committed pipeline fixture -------------------------------------------
#
# slug, lab, name, ii, gdpval (0-1 fraction), params (billions), intelligence
# cost total, gdpval-aa weighted cost, scicode weighted cost, open weights.
# The gdpval-aa weightedCostPerTask values are the agentic task cost times the
# 10% index weight (build.GDPVAL_INDEX_WEIGHT), so build's recovery
# `weighted / 0.10` lands on clean numbers -- e.g. 0.42 / 0.10 = 4.20.

_MODEL_TABLE = (
    ("alpha-1", "Alpha Fixtures", "Alpha One", 62.1, 0.58, 405, 1.20, 0.42,
     0.30, False),
    ("beta-2", "Beta Fixtures", "Beta Two", 55.4, 0.51, 235, 0.80, 0.38,
     0.22, True),
    ("gamma-3", "Alpha Fixtures", "Gamma Three", 48.9, 0.44, 72, 0.50, 0.31,
     0.18, True),
    ("delta-4", "Gamma Fixtures", "Delta Four", 43.2, 0.39, 32, 0.28, 0.25,
     0.12, False),
    ("epsilon-5", "Beta Fixtures", "Epsilon Five", 38.6, 0.30, 8, 0.14, 0.19,
     0.07, True),
    ("zeta-6", "Gamma Fixtures", "Zeta Six", 33.0, 0.21, 3, 0.06, 0.14,
     0.04, False),
)


def fixture_models() -> list:
    """The fixture's model records, in AA's merged leaderboard/detail shape
    (mirrors tests/test_build.py's `model_fixture`)."""
    return [
        {
            "name": name,
            "slug": slug,
            "modelCreatorName": lab,
            "isOpenWeights": open_weights,
            "intelligenceIndex": ii,
            # AA reports GDPval as a 0-1 fraction; the page shows it out of
            # 100.
            "gdpvalNormalized": gdpval,
            "parameters": params,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": total},
                "evaluations": [
                    {"slug": "gdpval-aa",
                     "weightedCostPerTask": gdpval_weighted},
                    {"slug": "scicode",
                     "weightedCostPerTask": scicode_weighted},
                ],
            },
        }
        for (slug, lab, name, ii, gdpval, params, total, gdpval_weighted,
             scicode_weighted, open_weights) in _MODEL_TABLE
    ]


# label, agent, host model slug (provider-prefixed; the model slug must be a
# suffix of it so the weights status is inherited), index score (0-1 fraction,
# rendered x100), cost USD, wall seconds, the MODEL lab the row files under.

_AGENT_TABLE = (
    ("Fixture Code - Alpha One", "Fixture Code", "alphafixtures_alpha-1",
     0.741, 2.40, 900.0, "Alpha Fixtures"),
    ("Fixture Code - Beta Two", "Fixture Code", "betafixtures_beta-2",
     0.662, 1.10, 840.0, "Beta Fixtures"),
    ("Fixture Code - Gamma Three", "Fixture Code", "alphafixtures_gamma-3",
     0.588, 0.42, 780.0, "Alpha Fixtures"),
)


def fixture_agents() -> list:
    """The fixture's Coding Agent Index records (mirrors
    tests/test_build.py's `agent_fixture`)."""
    return [
        {
            "id": label,
            "displayLabel": label,
            "agentName": agent,
            "hostModelSlug": host_slug,
            "display": {"creator": {"agent": agent, "model": lab}},
            "indexScore": score,
            "mean": {"costUsd": cost, "agentWallTimeSec": wall},
        }
        for (label, agent, host_slug, score, cost, wall, lab) in _AGENT_TABLE
    ]


def fixture_bytes(records) -> bytes:
    """The deterministic serialization the committed fixture carries.

    indent=1, sort_keys=True, one trailing newline: a fixed byte string for
    a fixed record set, on any Python (shortest-repr floats).
    """
    return (json.dumps(records, indent=1, sort_keys=True)
            + "\n").encode("utf-8")


# --- the committed fixture equals the generator functions' output --------------


def test_fixture_files_parse_and_the_stamp_is_a_valid_capture_stamp():
    """Both capture files load as JSON lists and the stamp is a zero-padded
    ISO date with the trailing newline fetch_aa.py writes beside a capture
    (build.read_capture_stamp strips it on read)."""
    models = json.loads(FIXTURE_MODELS.read_text(encoding="utf-8"))
    agents = json.loads(FIXTURE_AGENTS.read_text(encoding="utf-8"))
    assert isinstance(models, list) and len(models) == 6
    assert isinstance(agents, list) and len(agents) == 3
    assert FIXTURE_STAMP.read_text(encoding="utf-8") == FIXTURE_DATE + "\n"


def test_committed_fixture_is_the_generator_output_byte_for_byte():
    """Determinism pin: the committed bytes are regenerated by this module,
    never maintained by hand -- any edit must go through the generator."""
    assert FIXTURE_MODELS.read_bytes() == fixture_bytes(fixture_models())
    assert FIXTURE_AGENTS.read_bytes() == fixture_bytes(fixture_agents())


def test_fixture_covers_two_labs_and_matching_agent_hosts():
    """The fixture's shape requirements: at least two labs, and at least two
    agent rows whose hostModelSlug suffix-matches a model slug so the
    weights status is inherited (build.build_agent_rows' matching rule)."""
    models = json.loads(FIXTURE_MODELS.read_text(encoding="utf-8"))
    agents = json.loads(FIXTURE_AGENTS.read_text(encoding="utf-8"))
    slugs = {m["slug"] for m in models}
    labs = {m["modelCreatorName"] for m in models}
    assert len(labs) >= 2
    matched = 0
    for agent in agents:
        parts = agent["hostModelSlug"].split("_")
        if any("_".join(parts[i:]) in slugs for i in range(len(parts))):
            matched += 1
    assert matched >= 2


class FixtureBuildsEveryAxis(unittest.TestCase):
    """build.py accepts the committed fixture and renders all four axes.

    In-process, the import-and-call style of tests/test_build.py:
    RAW/AGENTS_RAW/OUT redirected to the fixture and a temp output under
    build.ROOT, build.main() run for real.
    """

    def test_build_accepts_the_fixture_and_renders_all_four_axes(self):
        stats = self._build_fixture()
        self.assertEqual(
            stats["metricCounts"],
            {"coding": 3, "intelligence": 6, "agentic": 6})
        self.assertEqual(stats["parameterCount"], 6)
        self.assertEqual(stats["total"], 6)

    def test_the_built_page_carries_all_four_chart_svgs(self):
        html = self._page_text()
        for svg in ("svg-coding", "svg-intelligence", "svg-agentic",
                    "svg-parameters"):
            self.assertIn(f'id="{svg}"', html)

    # -- helpers --------------------------------------------------------------

    def _page_text(self) -> str:
        with tempfile.TemporaryDirectory(
                prefix=".instruction-fixture-", dir=build.ROOT) as tmp:
            output = Path(tmp) / "frontier-models.html"
            old = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW = FIXTURE_MODELS
                build.AGENTS_RAW = FIXTURE_AGENTS
                build.OUT = output
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old
            return output.read_text(encoding="utf-8")

    def _build_fixture(self):
        with tempfile.TemporaryDirectory(
                prefix=".instruction-fixture-", dir=build.ROOT) as tmp:
            output = Path(tmp) / "frontier-models.html"
            old = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW = FIXTURE_MODELS
                build.AGENTS_RAW = FIXTURE_AGENTS
                build.OUT = output
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old
            html = output.read_text(encoding="utf-8")
        return json.loads(self._payload(html))["stats"]

    @staticmethod
    def _payload(html: str) -> str:
        marker = "const DATA = "
        start = html.index(marker) + len(marker)
        end = html.index(";\n(function(){", start)
        return html[start:end]


# --- the budgets document and the gate (all inputs here are synthetic) --------


@functools.lru_cache(maxsize=1)
def _gate():
    """The gate module, loaded once so every test shares one instance."""
    return _load("instruction_budgets")


def _budgets_document():
    """Synthetic budgets in the committed document's shape.

    The committed document's own values are the measured medians plus 3%,
    rounded up to the next million (CONTRIBUTING.md); these are round
    stand-ins judged only for their comparison behaviour.
    """
    return {"schema_version": 1,
            "scripts": {"build": 200, "capture_gate": 300, "diff_aa": 400}}


def _measurement(**overrides):
    """A synthetic measurement at or under _budgets_document."""
    values = {"build": 200, "capture_gate": 300, "diff_aa": 400}
    values.update(overrides)
    return values


def test_gate_passes_at_and_under_the_budgets():
    gate = _gate()
    document = _budgets_document()
    assert gate.gate(document, _measurement()) == []
    assert gate.gate(document, _measurement(build=199, capture_gate=0,
                                            diff_aa=1)) == []


def test_gate_exceeded_names_the_script_and_both_values():
    gate = _gate()
    findings = gate.gate(_budgets_document(), _measurement(diff_aa=401))
    assert findings == ["scripts.diff_aa: head 401 exceeds base 400"]


def test_gate_missing_script_is_a_loud_error():
    gate = _gate()
    measured = _measurement()
    del measured["capture_gate"]
    with pytest.raises(ValueError, match="missing script: capture_gate"):
        gate.gate(_budgets_document(), measured)


def test_gate_non_object_measurement_is_a_loud_error():
    gate = _gate()
    with pytest.raises(ValueError, match="must be an object"):
        gate.gate(_budgets_document(), [200, 300, 400])


# --- the callgrind summary parser ---------------------------------------------


def _callgrind_file(tmp_path, body):
    target = tmp_path / "cg.out"
    target.write_text(body, encoding="utf-8")
    return target


def test_summary_total_parses_the_summary_line(tmp_path):
    gate = _gate()
    body = ("# callgrind format\nversion: 1\ncreator: callgrind-3.24.0\n"
            "events: Ir\n\ncost line data...\nsummary: 72795950\n")
    assert gate.summary_total(_callgrind_file(
        tmp_path, body)) == 72795950  # synthetic: a fake dump's shape


def test_summary_total_takes_the_last_of_several_summary_lines(tmp_path):
    gate = _gate()
    body = "events: Ir\nsummary: 111\nsummary: 222\nsummary: 333\n"
    assert gate.summary_total(
        _callgrind_file(tmp_path, body)) == 333  # synthetic


def test_summary_total_refuses_a_missing_file(tmp_path):
    gate = _gate()
    with pytest.raises(ValueError, match="cannot read callgrind output"):
        gate.summary_total(tmp_path / "absent.out")


def test_summary_total_refuses_no_summary_line(tmp_path):
    gate = _gate()
    body = "events: Ir\ntotals: 72795950\n"  # synthetic: totals is not summary
    with pytest.raises(ValueError, match="no summary line"):
        gate.summary_total(_callgrind_file(tmp_path, body))


def test_summary_total_refuses_an_unparseable_summary(tmp_path):
    gate = _gate()
    body = "events: Ir\nsummary: many\n"  # synthetic
    with pytest.raises(ValueError, match="unparseable summary line"):
        gate.summary_total(_callgrind_file(tmp_path, body))


# --- the four exit codes through main(), measurements injected -----------------


def _run_main(monkeypatch, argv, measured=None, measure_raises=None):
    """main() with the measure path replaced by a synthetic result.

    Nothing here goes near valgrind: the callable under test is main()'s
    exit contract, not callgrind.
    """
    gate = _gate()

    def fake_measure():
        if measure_raises is not None:
            raise measure_raises
        assert measured is not None
        return measured

    monkeypatch.setattr(gate, "measure", fake_measure)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gate.main(argv)
    return code, out.getvalue(), err.getvalue()


def _write_budgets(tmp_path, document):
    target = tmp_path / "instruction-budgets.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def test_main_check_at_budget_passes(monkeypatch, tmp_path):
    document = _budgets_document()
    code, out, err = _run_main(
        monkeypatch, ["--budgets", str(_write_budgets(tmp_path, document))],
        measured=_measurement())
    assert code == 0
    assert err == ""
    assert "instruction budgets met" in out


def test_main_check_budget_minus_one_passes(monkeypatch, tmp_path):
    document = _budgets_document()
    code, _out, _err = _run_main(
        monkeypatch, ["--budgets", str(_write_budgets(tmp_path, document))],
        measured=_measurement(build=199, capture_gate=299, diff_aa=399))
    assert code == 0


def test_main_check_budget_plus_one_exits_1_naming_the_script(
        monkeypatch, tmp_path):
    """The mutation proof: a synthetic regression of one instruction per
    script must exit 1 and name every offending script."""
    document = _budgets_document()
    code, out, err = _run_main(
        monkeypatch, ["--budgets", str(_write_budgets(tmp_path, document))],
        measured=_measurement(build=201, capture_gate=301, diff_aa=401))
    assert code == 1
    assert "exceeded" in out
    assert "scripts.build: head 201 exceeds base 200" in err
    assert "scripts.target" not in err  # only real target names appear
    assert "scripts.capture_gate: head 301 exceeds base 300" in err
    assert "scripts.diff_aa: head 401 exceeds base 400" in err


def test_main_missing_document_exits_2_without_measuring(monkeypatch):
    gate = _gate()

    def explode():
        raise AssertionError("measure must not run for an invalid document")

    monkeypatch.setattr(gate, "measure", explode)
    assert gate.main(["--budgets", "/nonexistent/instruction-budgets.json"]) == 2


def _broken_document_cases():
    """Synthetic invalid documents: (name, document-or-text)."""
    cases = [
        ("schema_version 2", {"schema_version": 2, "scripts": {
            "build": 1, "capture_gate": 1, "diff_aa": 1}}),
        ("unknown top-level key", {"schema_version": 1, "scripts": {
            "build": 1, "capture_gate": 1, "diff_aa": 1}, "extra": {}}),
        ("missing script leaf", {"schema_version": 1, "scripts": {
            "build": 1, "capture_gate": 1}}),
        ("unknown script leaf", {"schema_version": 1, "scripts": {
            "build": 1, "capture_gate": 1, "diff_aa": 1, "fetch": 1}}),
        ("boolean value", {"schema_version": 1, "scripts": {
            "build": True, "capture_gate": 1, "diff_aa": 1}}),
        ("float spelling", {"schema_version": 1, "scripts": {
            "build": 1.0, "capture_gate": 1, "diff_aa": 1}}),
        ("negative value", {"schema_version": 1, "scripts": {
            "build": -1, "capture_gate": 1, "diff_aa": 1}}),
        ("string value", {"schema_version": 1, "scripts": {
            "build": "1", "capture_gate": 1, "diff_aa": 1}}),
        ("non-finite literal", {"schema_version": 1, "scripts": {
            "build": 1, "capture_gate": 1, "diff_aa": float("nan")}}),
        ("duplicate key", '{"schema_version": 1, "scripts": {"build": 1, '
         '"build": 2, "capture_gate": 1, "diff_aa": 1}}'),
    ]
    return cases


@pytest.mark.parametrize("name,document", _broken_document_cases(),
                         ids=[c[0] for c in _broken_document_cases()])
def test_main_invalid_document_exits_2(monkeypatch, tmp_path, name, document):
    """Every invalid shape is exit 2 before the measure path runs."""
    target = tmp_path / "instruction-budgets.json"
    if isinstance(document, str):
        target.write_text(document, encoding="utf-8")
    else:
        target.write_text(json.dumps(document), encoding="utf-8")
    gate = _gate()

    def explode():
        raise AssertionError("measure must not run for an invalid document")

    monkeypatch.setattr(gate, "measure", explode)
    assert gate.main(["--budgets", str(target)]) == 2


def test_main_measure_path_failure_exits_3(monkeypatch, tmp_path):
    document = _budgets_document()
    gate = _gate()
    code, _out, err = _run_main(
        monkeypatch, ["--budgets", str(_write_budgets(tmp_path, document))],
        measure_raises=gate.MeasureError("valgrind exploded"))
    assert code == 3
    assert "measurement failed: valgrind exploded" in err


def test_main_measure_mode_prints_counts_and_exits_0(monkeypatch):
    code, out, err = _run_main(monkeypatch, ["--measure"],
                               measured=_measurement())
    assert code == 0
    assert err == ""
    assert "build: 200 instructions" in out  # synthetic measurement
    assert "capture_gate: 300 instructions" in out
    assert "diff_aa: 400 instructions" in out


def test_main_measure_mode_ignores_an_invalid_or_missing_document(monkeypatch):
    """--measure bootstraps: it must not demand a budgets document that
    does not exist yet."""
    code, _out, _err = _run_main(
        monkeypatch,
        ["--measure", "--budgets", "/nonexistent/instruction-budgets.json"],
        measured=_measurement())
    assert code == 0


def test_valgrind_missing_raises_the_measure_error(monkeypatch):
    """The broken-harness arm with the real _require_valgrind: no valgrind
    on PATH raises the measure error main() maps to exit 3 (pinned by
    test_main_measure_path_failure_exits_3) -- never a clean pass or a
    budget breach."""
    gate = _gate()
    monkeypatch.setattr(gate.shutil, "which", lambda name: None)
    with pytest.raises(gate.MeasureError, match="valgrind is not installed"):
        gate.measure()


# --- the committed budgets document itself -------------------------------------


def test_the_committed_budgets_document_is_valid():
    """The committed document validates to exactly the three integer maxima
    under the gate's own loader."""
    gate = _gate()
    budgets = gate.load_budgets(COMMITTED_BUDGETS)
    assert budgets["schema_version"] == 1
    assert set(budgets["scripts"]) == {"build", "capture_gate", "diff_aa"}
    assert all(isinstance(value, int) and not isinstance(value, bool)
               for value in budgets["scripts"].values())


def test_the_committed_budgets_hold_a_measurement_at_their_own_values():
    """The committed document is consistent with itself: synthetic
    measurements exactly at the committed budgets pass the committed
    document -- the calibration a later tighten-only PR starts from."""
    gate = _gate()
    budgets = gate.load_budgets(COMMITTED_BUDGETS)
    assert gate.gate(budgets, dict(budgets["scripts"])) == []


def test_the_committed_budgets_fail_a_measurement_one_over():
    """Synthetic +1 on the committed values: the finding names the script
    and both numbers, so a regression cannot slip past the committed
    calibration."""
    gate = _gate()
    budgets = gate.load_budgets(COMMITTED_BUDGETS)
    over = {name: value + 1 for name, value in budgets["scripts"].items()}
    findings = gate.gate(budgets, over)
    assert len(findings) == 3
    assert all("exceeds base" in line for line in findings)


# --- the mini-tree the measure path builds --------------------------------------


def test_stage_tree_copies_the_code_under_test_and_the_fixture(tmp_path):
    """The mini-tree gets the CURRENT tree's four code files and the
    fixture's three data files -- never the live data/ captures."""
    gate = _gate()
    mini = tmp_path / "mini"
    mini.mkdir()
    # white-box: the staging layout IS the contract under test
    # pylint: disable-next=protected-access
    gate._stage_tree(mini)
    assert (mini / "build.py").read_bytes() == (
        REPO_ROOT / "build.py").read_bytes()
    assert (mini / "page_format.py").read_bytes() == (
        REPO_ROOT / "page_format.py").read_bytes()
    assert (mini / "scripts" / "capture_gate.py").is_file()
    assert (mini / "scripts" / "diff_aa.py").is_file()
    for name in ("aa-raw-models.json", "aa-raw-coding-agents.json",
                 "captured-at.txt"):
        assert (mini / "data" / name).read_bytes() == (
            FIXTURE_DIR / name).read_bytes()


def test_stage_tree_refuses_a_missing_fixture_file(tmp_path, monkeypatch):
    gate = _gate()
    monkeypatch.setattr(gate, "FIXTURE", tmp_path)
    mini = tmp_path / "mini"
    mini.mkdir()
    with pytest.raises(gate.MeasureError, match="fixture file missing"):
        gate._stage_tree(mini)  # pylint: disable=protected-access


def test_stage_tree_refuses_a_corrupt_fixture_file(tmp_path, monkeypatch):
    gate = _gate()
    fixture_copy = tmp_path / "fixture"
    fixture_copy.mkdir()
    for name in gate.FIXTURE_FILES:
        shutil.copy2(FIXTURE_DIR / name, fixture_copy / name)
    (fixture_copy / "aa-raw-models.json").write_text(
        "{not json", encoding="utf-8")
    monkeypatch.setattr(gate, "FIXTURE", fixture_copy)
    mini = tmp_path / "mini"
    mini.mkdir()
    with pytest.raises(gate.MeasureError, match="fixture file corrupt"):
        gate._stage_tree(mini)  # pylint: disable=protected-access


def test_commit_captures_seeds_a_head_the_gate_can_read(tmp_path):
    """After _commit_captures, `git show HEAD:data/<capture>` from the
    mini-tree returns the fixture bytes -- the read capture_gate makes."""
    gate = _gate()
    mini = tmp_path / "mini"
    (mini / "data").mkdir(parents=True)
    for name in ("aa-raw-models.json", "aa-raw-coding-agents.json"):
        (mini / "data" / name).write_bytes((FIXTURE_DIR / name).read_bytes())
    # white-box: the HEAD commit shape is the contract under test
    # pylint: disable-next=protected-access
    gate._commit_captures(mini)
    shown = subprocess.run(
        ["git", "-C", str(mini), "show", "HEAD:data/aa-raw-models.json"],
        capture_output=True, text=True, check=True)
    assert shown.stdout == (FIXTURE_DIR / "aa-raw-models.json").read_text(
        encoding="utf-8")


def test_callgrind_invocation_carries_the_load_bearing_pins(monkeypatch):
    """White-box pin on the measured command: nice 19, a timeout, callgrind
    with an out file, the interpreter under test -- and the three env pins
    whose absence was measured at a 1.6% run-to-run swing
    (PYTHONDONTWRITEBYTECODE) plus dict-order jitter (PYTHONHASHSEED) and
    user-site .pth execution (PYTHONNOUSERSITE)."""
    gate = _gate()
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    # white-box: the measured argv/env is the contract under test
    # pylint: disable-next=protected-access
    gate._callgrind("/tmp/cg.out", "/tmp/mini", ("build.py",))
    assert seen["argv"][:5] == ["nice", "-n", "19", "timeout",
                                str(gate.TIMEOUT_SECONDS)]
    assert seen["argv"][5:7] == ["valgrind", "--tool=callgrind"]
    assert seen["argv"][7].startswith("--callgrind-out-file=/tmp/cg.out")
    assert seen["argv"][8] == sys.executable
    assert seen["argv"][9:] == ["build.py"]
    env = seen["kwargs"]["env"]
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONHASHSEED"] == "0"
    assert env["PYTHONNOUSERSITE"] == "1"
