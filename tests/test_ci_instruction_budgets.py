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
import io
import json
import tempfile
import unittest
from pathlib import Path

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
