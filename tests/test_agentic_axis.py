"""The GDPval-AA v2.1 axis (issue #356): the leaderboard's Elo against the
cost per task AA's GDPval-AA evaluation page computes."""

import contextlib
import io
import json
import pathlib
import re
import sys
import tempfile
import unittest
from html import escape as html_escape
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import argparse  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import capture_gate  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import diff_aa  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import fetch_gdpval  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import page_format  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_capture_gate  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_fetch_aa_membership as membership  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
from test_build import agent_fixture, model_fixture  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
from test_diff_aa import capture as diff_capture  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

PIPELINE_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "pipeline"
SCORE = "gdpval-aa-normalized"
GDPVAL_NOTE = ("agentic: no GDPval-AA evaluation cost joined this capture (the evaluation read "
               "matched none of the run's leaderboard generations, or its fields changed shape)")


def agentic(record):
    """The record's GDPval-AA pair as build_rows renders it, or None."""
    rows = build.build_rows([record])
    return rows[0]["metrics"]["agentic"] if rows else None


class AgenticPairTests(unittest.TestCase):
    def test_the_leaderboard_elo_wins_over_a_differing_detail_gdpval(self):
        leaderboard = {"slug": "m", "name": "M", "intelligenceIndex": 51,
                       "intelligenceIndexCostPerTask": 0.75, "scores": {SCORE: 1200.5}}
        detail = {"slug": "m", "name": "M", "gdpval": 980.0, "gdpvalCostPerTask": 4.0}
        merged = build.merge_captures([leaderboard], [detail])[0]

        self.assertEqual(merged["gdpval"], 980.0)
        self.assertEqual(agentic(merged), {"score": 1200.5, "cost": 4.0})

    def test_the_detail_gdpval_scores_only_a_record_the_leaderboard_lacks(self):
        detail_only = {"slug": "m", "name": "M", "gdpval": 980.0, "gdpvalCostPerTask": 4.0}
        silent = dict(detail_only, scores={"tau3-banking": 70.0})

        self.assertEqual(agentic(detail_only), {"score": 980.0, "cost": 4.0})
        self.assertIsNone(agentic(silent))

    def test_the_elo_is_rendered_unscaled_and_the_legacy_fraction_is_unused(self):
        rows = build.build_rows([model_fixture(gdpval=1047.25)])
        _, main = build.render_static_tbodies(rows)
        legacy = dict(model_fixture(gdpval=None), gdpvalNormalized=0.47)

        self.assertEqual(rows[0]["metrics"]["agentic"], {"score": 1047.25, "cost": 8.0})
        self.assertIn('<td class="n">1047.3 <span class="tag f">frontier</span></td>', main)
        self.assertIsNone(agentic(legacy))

    def test_a_negative_elo_renders_and_stays_on_its_frontier(self):
        weak = dict(model_fixture(gdpval=-401.79, gdpval_cost=0.5, slug="weak"), name="Weak")
        rows = build.build_rows([model_fixture(), weak])
        frontier, main = build.render_static_tbodies(rows)

        self.assertEqual([r["name"] for r in build.frontier_layer(rows, "agentic")],
                         ["Weak", "Fixture Model (high)"])
        self.assertIn('<td class="n">-401.8 <span class="tag f">frontier</span></td>', main)
        self.assertIn('<td class="n">-401.8</td><td class="n">$0.500</td>'
                      '<td class="n">—</td>', frontier)

    def test_score_without_cost_and_cost_without_score_have_no_row(self):
        unpriced = model_fixture(gdpval_cost=None)
        unscored = model_fixture(gdpval=None)
        free = model_fixture(gdpval_cost=0)

        for record in (unpriced, unscored, free):
            with self.subTest(record=record["scores"], cost=record["gdpvalCostPerTask"]):
                self.assertIsNone(agentic(record))
        rows = build.build_rows([unpriced, unscored])
        _, main = build.render_static_tbodies(rows)
        self.assertNotIn("1047.0", main)
        self.assertEqual(build.undominated(rows, "agentic"), [])

    def test_the_producers_cost_field_reaches_the_axis(self):
        record = {"slug": "m", "name": "M", "scores": {SCORE: 900.0}}
        joined = fetch_gdpval.join([record], {"m": 3.5})

        self.assertEqual(agentic(joined[0]), {"score": 900.0, "cost": 3.5})

    def test_the_elo_and_the_cost_dispute_on_their_own_fields(self):
        row = build.build_rows([dict(model_fixture(), genVariants=[
            {"ii": 51, "cost": 0.75, "gdpval": 1047.0, "gdpvalCost": 8.0},
            {"ii": 50.5, "cost": 0.75, "gdpval": -12.0, "gdpvalCost": 8.4}])])[0]
        agreeing = build.build_rows([dict(model_fixture(), genVariants=[
            {"ii": 51, "gdpval": 1047.0}, {"ii": 50.5, "gdpval": 1047.0}])])[0]

        self.assertEqual(build._variant_cells(row, "agentic"),  # pylint: disable=protected-access
                         ("1047.0 / -12.0", "$8.00 / $8.40", True, True))
        self.assertEqual(build._variant_cells(agreeing, "agentic"),  # pylint: disable=protected-access
                         (None, None, False, False))

    def test_an_elo_has_no_dollars_per_point_while_other_axes_keep_theirs(self):
        frontier, _ = build.render_static_tbodies(build.build_rows([model_fixture(gdpval=1500.0)]))

        self.assertIn('<td class="n">1500.0</td><td class="n">$8.00</td><td class="n">—</td>', frontier)
        self.assertIn('<td class="n">$0.0147</td>', frontier)

    def test_a_disputed_cost_renders_on_a_row_without_a_gdpval_score(self):
        _, main = build.render_static_tbodies(build.build_rows([dict(model_fixture(gdpval=None), genVariants=[
            {"ii": 51, "cost": 0.75, "gdpvalCost": 8.0}, {"ii": 51, "cost": 0.75, "gdpvalCost": 8.4}])]))

        self.assertIn('frontier</span></td><td class="n">—</td><td class="n dispute">$8.00 / $8.40</td>', main)


class EloDisputeCaptureTests(unittest.TestCase):
    def test_the_elo_reaches_variants_and_the_revisit_fingerprint(self):
        lead, detail_only = {"slug": "m", "scores": {SCORE: 1000.0}, "gdpval": 5.0}, {"slug": "d", "gdpval": 7.0}
        moved = dict(lead, scores={SCORE: 1200.0})

        self.assertEqual(fetch_aa.variant_fields(lead)["gdpval"], 1000.0)
        self.assertEqual(fetch_aa.variant_fields(detail_only)["gdpval"], 7.0)
        self.assertNotEqual(fetch_aa.revisit_key([lead]), fetch_aa.revisit_key([moved]))
        self.assertEqual(fetch_aa.revisit_key([lead]), fetch_aa.revisit_key([dict(lead, scores={SCORE: 1000.0, "x": 1})]))
        self.assertEqual(fetch_aa.revisit_key([{"slug": "m"}]),
                         fetch_aa.generation_key([{"slug": "m"}], set(fetch_aa.DISPUTE_CAPABLE)))

    def test_the_in_run_merge_fills_an_elo_the_canonical_look_lacks(self):
        def look(tag, elo):
            scores = {"tau3-banking": tag, **({SCORE: elo} if elo else {})}
            return [{"slug": "m", "intelligenceIndex": 51, "scores": scores}]
        universe = {"slug", "intelligenceIndex", "scores"}
        tag = next(t for t in range(1, 200)
                   if fetch_aa.generation_key(look(t, None), universe) < fetch_aa.generation_key(look(t, 900.0), universe))
        merged = fetch_aa.cross_generation_merge([look(tag, 900.0), look(tag, None)], universe)[0]

        self.assertEqual((fetch_aa.gdpval_elo(merged), merged["scores"]["tau3-banking"]), (900.0, tag))

    def test_a_held_render_fills_an_elo_the_canonical_generation_lacks(self):
        bare = {"slug": "m", "intelligenceIndex": 51, "scores": {"tau3-banking": 1}}
        with_elo = dict(bare, scores={"tau3-banking": 1, SCORE: 900.0})
        out, _ = fetch_aa.render_revisit_hold({"generations": {"a": [bare], "b": [with_elo]}}, [bare])

        self.assertEqual(fetch_aa.gdpval_elo(out[0]), 900.0)

    def test_an_elo_only_revisit_holds_both_generations(self):
        harness = test_fetch_aa.TestGenerationRevisit()
        harness.setUp()
        try:
            for elo in (1000.0, 1200.0):
                harness.run_hour(50, scores={SCORE: elo})
            models, _ = harness.run_hour(50, scores={SCORE: 1000.0})
            row = next(m for m in models if m["slug"] == "fixture-model")

            self.assertIsNotNone(harness.state()["held"])
            self.assertEqual(sorted(v["gdpval"] for v in row["genVariants"]), [1000.0, 1200.0])
        finally:
            harness.doCleanups()


def test_two_looks_differing_only_in_elo_hold_both(tmp_path, monkeypatch):
    first, second = membership.leaderboard(), membership.leaderboard()
    first[1]["scores"], second[1]["scores"] = {SCORE: 1000.0}, {SCORE: 1200.0}
    captured = membership.capture_pages(tmp_path, monkeypatch, first, second, [membership.detail_record()])
    row = next(m for m in captured.models if m["slug"] == "current")

    assert sorted(v["gdpval"] for v in row["genVariants"]) == [1000.0, 1200.0]
    assert fetch_aa.gdpval_elo(row) == row["genVariants"][0]["gdpval"]  # the canonical value wins


class NegativeFormatTests(unittest.TestCase):
    def test_to_fixed_matches_v8_below_zero(self):
        # V8 (node v24.17.0) prints these for Number.prototype.toFixed: the
        # magnitude rounds with ties away from zero, and -0 prints unsigned.
        for value, digits, v8 in ((-2.25, 1, "-2.3"), (-2.675, 2, "-2.67"),
                                  (-0.04, 1, "-0.0"), (-0.0, 1, "0.0"),
                                  (-401.79, 1, "-401.8"), (-1.45, 1, "-1.4")):
            with self.subTest(value=value, digits=digits):
                self.assertEqual(page_format.js_to_fixed(value, digits), v8)


class AgenticEmptyAxisTests(unittest.TestCase):
    WINDOW = ("every cost breakdown dropped as another generation's: "
              "185 model(s), first apodex-1-1; 3 generation(s) observed in-run\n")

    def refusal(self, model, window=False):
        harness = test_build.EmptyAxisGuardTests()
        with harness.capture([model], [agent_fixture()]) as output:
            if window:
                (output.parent / "cost-breakdown-window.txt").write_text(self.WINDOW, encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                harness.run_build()
            self.assertFalse(output.exists(), "refusal still wrote the page")
        return str(raised.exception)

    def test_a_capture_with_no_agentic_pair_is_refused_naming_agentic(self):
        message = self.refusal(model_fixture(gdpval=None))

        self.assertIn("no rows carry a score/cost pair for: agentic --", message)
        self.assertIn("changed shape", message)
        self.assertIn(GDPVAL_NOTE, message)
        self.assertNotIn(GDPVAL_NOTE, self.refusal(model_fixture(intelligence=None)))

    def test_an_empty_agentic_axis_never_holds_in_a_window_hour(self):
        # The hold covers parameters alone: an emptied agentic axis beside a
        # three-generation marker refuses, alone or beside parameters.
        corner = model_fixture(gdpval_cost=None)
        del corner["parameters"]
        for model, axes in ((model_fixture(gdpval_cost=None), "agentic"),
                            (corner, "agentic, parameters")):
            with self.subTest(axes=axes):
                message = self.refusal(model, window=True)
                self.assertIn(f"for: {axes} -- the capture records a cross-generation AA window", message)
                self.assertIn(GDPVAL_NOTE, message)
                self.assertNotIn("holding the page", message)


def without_agentic(models: bytes) -> bytes:
    """The capture with every GDPval-AA cost gone, as an unmatched evaluation read leaves it."""
    return json.dumps([fetch_gdpval.join([m], {})[0] for m in json.loads(models)]).encode("utf-8")


class AgenticGateTests(unittest.TestCase):
    def test_the_gate_fails_red_when_the_fresh_capture_empties_agentic(self):
        err = io.StringIO()
        fixture = (test_capture_gate.FIXTURE_MODELS, test_capture_gate.FIXTURE_AGENTS)
        with test_capture_gate.head_serving(*fixture), \
                mock.patch.object(capture_gate, "read_fresh_captures", return_value=(
                    without_agentic(fixture[0]), fixture[1])), contextlib.redirect_stderr(err):
            code, out = test_capture_gate.run_gate()

        self.assertEqual((code, out), (1, ""))
        self.assertIn("no rows carry a score/cost pair for: agentic", err.getvalue())

    def test_the_hold_probe_reads_an_empty_agentic_corner_as_broken(self):
        corner = without_agentic(test_capture_gate.corner_capture(test_capture_gate.FIXTURE_MODELS))
        with mock.patch.object(capture_gate, "read_fresh_generation_state", return_value=None), \
                mock.patch.object(capture_gate, "read_fresh_captures", return_value=(
                    corner, test_capture_gate.FIXTURE_AGENTS)), \
                mock.patch.object(capture_gate, "read_fresh_window_marker",
                                  return_value=test_capture_gate.WINDOW_MARKER):
            code, out, err = test_capture_gate.FreshHoldProbeTests.run_probe()

        self.assertEqual((code, out), (1, ""))
        self.assertIn("for: agentic, parameters", err)


def scored(name, elo, gdpval_cost, **extra):
    """A model the differ reads, carrying a GDPval-AA pair."""
    return diff_capture(name, scores={SCORE: elo}, gdpvalCostPerTask=gdpval_cost, **extra)


class AgenticDiffTests(unittest.TestCase):
    @staticmethod
    def render(old, new):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [pathlib.Path(tmp) / name for name in ("old.json", "new.json")]
            for path, data in zip(paths, (old, new)):
                path.write_text(json.dumps(data), encoding="utf-8")
            args = argparse.Namespace(old=str(paths[0]), new=str(paths[1]), speed_tol=0.25,
                                      tol=0.0, derived=False, all=False, commit_msg=False)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                diff_aa.print_report(args)
        return buffer.getvalue()

    def test_score_and_cost_moves_report_with_their_deltas(self):
        report = self.render([scored("A", 1000.0, 2.0, gdpval=900.0)],
                             [scored("A", 1100.0, 2.5, gdpval=950.0)])

        self.assertIn("scores.gdpval-aa-normalized: 1000 -> 1100  (+100, +10.00%)", report)
        self.assertIn("    gdpval: 900 -> 950  (+50, +5.56%)", report)
        self.assertIn("gdpvalCostPerTask: 2 -> 2.5  (+0.5, +25.00%)", report)

    def test_other_leaderboard_scores_stay_derived(self):
        report = self.render([diff_capture("A", scores={SCORE: 1000.0, "tau3-banking": 60.0})],
                             [diff_capture("A", scores={SCORE: 1000.0, "tau3-banking": 70.0})])

        self.assertNotIn("tau3-banking", report)
        self.assertIn("1 derived breakdown values", report)

    def test_a_model_scored_only_on_gdpval_reports_without_an_intelligence_pair(self):
        old = [scored("A", 1000.0, 2.0), diff_capture("N", intelligence=10, cost=5.0),
               scored("G (low)", 800.0, 1.0, intelligence=10, cost=5.0)]
        report = self.render(old, old + [scored("G (high)", 1100.0, 3.0, intelligence=None)])

        self.assertIn("  + G (high)  [Fixture Lab]  II —  cost/task —\n", report)
        self.assertNotIn("efficient frontier", report)
        self.assertIn("== GDPval-AA frontier: 2 -> 3 of 2 -> 3 plotted\n  + G (high)  1100.0  $3.00/task", report)

    def test_the_gdpval_frontier_section_names_who_moved(self):
        old = [scored("A", 1000.0, 2.0), scored("B", 900.0, 3.0)]
        # C is new and cheapest on GDPval-AA, dominated on the other charts.
        new = [scored("A", 1000.0, 2.0), scored("B", 1200.0, 3.0),
               scored("C", -50.0, 0.5, intelligence=10, cost=5.0, params=1000)]
        report = self.render(old, new)
        section = report[report.index("== GDPval-AA frontier"):]

        self.assertTrue(section.startswith("== GDPval-AA frontier: 1 -> 3 of 2 -> 3 plotted\n"))
        self.assertIn("  + B  1200.0  $3.00/task\n", section)
        self.assertIn("  + C  -50.0  $0.50/task\n", section)
        self.assertEqual(diff_aa.frontier_moves(report.splitlines()),
                         [("GDPval-AA", ["B", "C"], [])])
        self.assertEqual(diff_aa.as_commit_message(report).splitlines()[0],
                         "Refresh capture: 3 models, GDPval-AA frontier: B in, C in, +1/-0")


class FrontierZeroScoreTests(unittest.TestCase):
    """Issue #146: a zero score is legal (GDPval-AA's Elo also goes negative)
    and sits on an axis's frontier when it holds that axis's minimum cost.
    Its $/point cell renders the em dash, never a ZeroDivisionError or
    "$Infinity", and the JS mirror must match or the browser drift test fails.
    """

    def _rows(self):
        """Two rows; the strictly cheapest scores 0.0 on intelligence."""
        return [
            {
                "name": "Cheap Zero", "creator": "Zero Lab", "open": False,
                "lic": None,
                "metrics": {
                    "coding": {"score": 40.0, "cost": 0.5},
                    "intelligence": {"score": 0.0, "cost": 0.3},
                },
            },
            {
                "name": "Costly Smart", "creator": "Other Lab", "open": True,
                "lic": "mit",
                "metrics": {
                    "coding": {"score": 60.0, "cost": 2.0},
                    "intelligence": {"score": 50.0, "cost": 2.0},
                },
            },
        ]

    def test_the_frontier_table_renders_zero_score_rows(self):
        tbody = build.render_frontier_tbody(self._rows())
        self.assertIn(
            '<tr><td>Intelligence Index</td><td class="name">Cheap Zero</td>'
            "<td>Zero Lab</td>"
            '<td class="n">0.0</td><td class="n">$0.300</td>'
            '<td class="n">—</td>'
            '<td><span class="tag">proprietary</span></td></tr>',
            tbody)
        # A positive-score sibling still renders its $/point: 2.0/50.
        self.assertIn('<td class="n">$0.0400</td>', tbody)

    def test_zero_score_capture_builds_through_main(self):
        # One fixture model zeroed and priced below every other, so it lands
        # on the intelligence frontier with a zero score.
        models = json.loads(
            (PIPELINE_FIXTURES / "aa-raw-models.json").read_bytes())
        floor = None
        target = None
        for m in models:
            cost = build.cost_per_task(m)
            if cost is not None and cost > 0 and (floor is None or cost < floor):
                floor = cost
            if target is None and cost is not None and cost > 0 and "(" not in (
                    m.get("shortName") or m.get("name") or ""):
                target = m
        self.assertIsNotNone(target)
        # The asserts narrow for pyright.
        assert target is not None
        assert floor is not None
        target["intelligenceIndex"] = 0
        target["intelligenceIndexCostPerTask"] = floor / 2
        # Derive the rendered name through build's own cleaning.
        name = build.display_name(target.get("name") or target.get("shortName"))

        with tempfile.TemporaryDirectory(
                prefix=".issue-146-build-", dir=build.ROOT) as tmp:
            raw = pathlib.Path(tmp) / "models.json"
            agents_raw = pathlib.Path(tmp) / "coding-agents.json"
            page_path = pathlib.Path(tmp) / "frontier-models.html"
            raw.write_bytes(
                json.dumps(models, indent=1).encode("utf-8"))
            agents_raw.write_bytes(
                (PIPELINE_FIXTURES / "aa-raw-coding-agents.json").read_bytes())
            saved = (build.RAW, build.AGENTS_RAW, build.OUT)
            build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, page_path
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main(generation_state=None)
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = saved
            page = page_path.read_text(encoding="utf-8")

        ftable = page[page.index('id="fTable"'):page.index("</table>", page.index('id="fTable"'))]
        row_re = re.compile(
            r'<tr><td>Intelligence Index</td><td class="name">'
            + re.escape(html_escape(name)) + r"</td>(.*?)</tr>")
        match = row_re.search(ftable)
        self.assertIsNotNone(
            match, f"no intelligence frontier row for the mutated model {name}")
        assert match is not None
        self.assertIn('<td class="n">0.0</td>', match.group(1))
        self.assertIn('<td class="n">—</td>', match.group(1))
