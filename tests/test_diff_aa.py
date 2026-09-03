import argparse
import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import diff_aa  # noqa: E402  # pylint: disable=wrong-import-position

# A report in the exact shape diff_aa.report() prints, trimmed to one entry per
# section. The renderer reads this back rather than re-running the analysis, so
# the shape is the contract and this fixture is what pins it.
REPORT = """old: git:HEAD  (610 models)
new: data/aa-raw-models.json  (616 models)

== models added: 6
  + Grok 4.6 (xhigh)  [SpaceXAI]  II 60.0  cost/task $1.04
== models removed: 0

== field changes

  Claude Opus 5 (Adaptive Reasoning, Max Effort)  [Anthropic]
    mlcrOverall: — -> 0.555556

== rendered speed re-sampled by more than 25%: 769 value(s), 471 model(s)
  Muse Spark 1.2 (xhigh)  [Meta]  medianOutputTokensPerSecond: 40 -> 90
  Motif 3  [Motif Technologies]  medianOutputTokensPerSecond: 30 -> 80

== efficient frontier (expanded): 16 -> 17 of 136 -> 142 plotted
  + Grok 4.6 (xhigh)  II 60.0  $1.04/task

discarded: 7199 re-sampled speed/latency values the page never renders
"""


class CommitMessageTests(unittest.TestCase):
    def test_subject_names_what_moved(self):
        subject = diff_aa.as_commit_message(REPORT).splitlines()[0]

        self.assertEqual(
            subject,
            "Refresh capture: 616 models, +6/-0 models, frontier 16 -> 17")

    def test_subject_says_so_when_nothing_material_moved(self):
        quiet = REPORT.replace("== models added: 6", "== models added: 0") \
                      .replace("16 -> 17 of 136 -> 142", "17 -> 17 of 142 -> 142")

        self.assertEqual(diff_aa.as_commit_message(quiet).splitlines()[0],
                         "Refresh capture: 616 models, no material change")

    def test_drops_the_jitter_section_and_keeps_the_significant_one(self):
        body = diff_aa.as_commit_message(REPORT)

        # Jitter is re-measured every crawl and would bury everything else.
        self.assertNotIn("rendered speed re-sampled", body)
        self.assertNotIn("Muse Spark", body)
        # The significant move, the new model and the moved frontier survive.
        self.assertIn("mlcrOverall: — -> 0.555556", body)
        self.assertIn("+ Grok 4.6 (xhigh)  [SpaceXAI]", body)
        self.assertIn("== efficient frontier (expanded): 16 -> 17", body)
        self.assertIn("discarded: 7199", body)

    def test_undefined_sentinel_is_absence_not_a_value(self):
        # AA writes JavaScript `undefined` as this string; a key that gains it
        # has not changed, it is still unset.
        self.assertEqual(diff_aa.flatten({"a": "$undefined", "b": 1}), {"b": 1})
        self.assertEqual(diff_aa.flatten({"n": {"deep": "$undefined"}}), {})


def capture(name, *, ident=None, intelligence: float | None = 51,
            cost: float = 0.75, params: float | None = 27,
            creator="Fixture Lab", **extra):
    """One model in AA's own shape, minimal but complete enough for
    build_rows() to seat a row for it — which is what the frontier helpers and
    the added/removed lines run over."""
    model = {
        "id": ident or name.lower().replace(" ", "-"),
        "name": name,
        "modelCreatorName": creator,
        "intelligenceIndex": intelligence,
        "codingIndex": intelligence,
        "agenticIndex": intelligence,
        "totalParameters": params,
        "intelligenceIndexCostPerTask": {
            "cost": {"total": cost},
            "evaluations": [
                {"slug": "terminalbench-v2-1", "weightedCostPerTask": cost / 2},
                {"slug": "scicode", "weightedCostPerTask": cost / 4},
                {"slug": "gdpval-aa", "weightedCostPerTask": cost},
                {"slug": "tau3-banking", "weightedCostPerTask": cost / 2},
            ],
        },
    }
    model.update(extra)
    return model


class ClassifyTests(unittest.TestCase):
    def test_speed_fields_the_page_shows_are_jitter_and_the_rest_unused(self):
        # A jitter field the page renders gets a threshold; one it never shows
        # cannot change the artifact, so it is dropped outright.
        self.assertEqual(diff_aa.classify("medianOutputTokensPerSecond"), "jitter")
        self.assertEqual(diff_aa.classify("percentile95OutputTokensPerSecond"),
                         "jitter-unused")
        self.assertEqual(diff_aa.classify("medianTimeToFirstTokenSeconds"),
                         "jitter-unused")

    def test_lab_branding_is_cosmetic(self):
        self.assertEqual(diff_aa.classify("modelCreatorColor"), "cosmetic")

    def test_components_of_a_reported_headline_are_derived(self):
        self.assertEqual(diff_aa.classify("evalTokenCounts.gdpval"), "derived")
        self.assertEqual(diff_aa.classify("intelligenceIndexCostInput"), "derived")
        self.assertEqual(diff_aa.classify("price1mBlended3to1"), "derived")
        self.assertEqual(
            diff_aa.classify("intelligenceIndexCostPerTask.cost.input"), "derived")

    def test_the_headline_itself_is_significant(self):
        self.assertEqual(diff_aa.classify("intelligenceIndex"), "significant")
        self.assertEqual(
            diff_aa.classify("intelligenceIndexCostPerTask.cost.total"),
            "significant")


class FormattingTests(unittest.TestCase):
    def test_absent_renders_as_an_em_dash_never_none(self):
        self.assertEqual(diff_aa.fmt(None), "—")

    def test_values_render_by_kind(self):
        self.assertEqual(diff_aa.fmt(True), "true")
        self.assertEqual(diff_aa.fmt(0.123456789), "0.123457")
        self.assertEqual(diff_aa.fmt({"a": 1}), '{"a":1}')

    def test_delta_note_carries_absolute_and_relative_movement(self):
        self.assertEqual(diff_aa.delta_note(2.0, 3.0), "  (+1, +50.00%)")

    def test_delta_note_is_silent_when_there_is_nothing_to_say(self):
        self.assertEqual(diff_aa.delta_note(2.0, 2.0), "")     # unchanged
        self.assertEqual(diff_aa.delta_note(0, 5), "")         # infinite
        self.assertEqual(diff_aa.delta_note("a", "b"), "")     # not numeric

    def test_rel_change_treats_booleans_as_non_numeric(self):
        self.assertIsNone(diff_aa.rel_change(True, False))

    def test_parameter_sizes_read_in_billions_then_trillions(self):
        self.assertEqual(diff_aa.fmt_params(27), "27B")
        self.assertEqual(diff_aa.fmt_params(1000), "1T")
        self.assertEqual(diff_aa.fmt_params(1500), "1.5T")


class FrontierTests(unittest.TestCase):
    def test_only_undominated_models_are_named(self):
        models = [
            capture("Cheap Smart", intelligence=60, cost=0.10),
            capture("Dear Dim", intelligence=40, cost=5.00),
        ]

        names, rows = diff_aa.frontier_names(models)

        self.assertEqual(len(rows), 2)
        self.assertIn("Cheap Smart", names)
        self.assertNotIn("Dear Dim", names)

    def test_collapsing_effort_keeps_each_model_at_its_ceiling(self):
        # Same base model at two effort settings: collapsed, only the ceiling
        # is drawn, which is what "which model" rather than "which
        # configuration" means.
        models = [
            capture("Fixture (high)", ident="hi", intelligence=60, cost=1.0),
            capture("Fixture (low)", ident="lo", intelligence=45, cost=0.2),
        ]

        _, expanded = diff_aa.frontier_names(models)
        _, collapsed = diff_aa.frontier_names(models, collapse=True)

        self.assertEqual(len(expanded), 2)
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["ii"], 60)

    def test_the_parameter_chart_only_sees_disclosed_sizes(self):
        models = [
            capture("Open", intelligence=50, params=27),
            capture("Closed", ident="closed", intelligence=55, params=None),
        ]

        names, rows = diff_aa.chart_frontier(models, "parameters")

        self.assertEqual([r["name"] for r in rows], ["Open"])
        self.assertIn("Open", names)

    def test_a_cost_chart_drops_models_with_no_measurement_for_it(self):
        models = [capture("Measured", intelligence=50)]

        _, rows = diff_aa.chart_frontier(models, "coding")

        self.assertEqual([r["name"] for r in rows], ["Measured"])


class ReportTests(unittest.TestCase):
    """End-to-end: two captures in, a report out, rendered to a message."""

    def render(self, old, new):
        old_path = pathlib.Path(self.tmp) / "old.json"
        new_path = pathlib.Path(self.tmp) / "new.json"
        old_path.write_text(json.dumps(old), encoding="utf-8")
        new_path.write_text(json.dumps(new), encoding="utf-8")
        args = argparse.Namespace(old=str(old_path), new=str(new_path),
                                  speed_tol=0.25, tol=0.0, derived=False,
                                  all=False, commit_msg=False)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            diff_aa.print_report(args)
        return buffer.getvalue()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_a_new_model_is_reported_and_reaches_the_subject_line(self):
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = old + [capture("Newcomer", intelligence=62, cost=0.5)]

        report = self.render(old, new)

        self.assertIn("== models added: 1", report)
        self.assertIn("+ Newcomer  [Fixture Lab]", report)
        self.assertIn("Refresh capture: 2 models, +1/-0 models",
                      diff_aa.as_commit_message(report))

    def test_a_removed_model_is_reported(self):
        old = [capture("Incumbent"), capture("Doomed", ident="doomed")]
        new = [capture("Incumbent")]

        report = self.render(old, new)

        self.assertIn("== models removed: 1", report)
        self.assertIn("- Doomed  [Fixture Lab]", report)

    def test_open_weights_and_retirement_are_marked_on_the_line(self):
        old = []
        new = [capture("Freebie", isOpenWeights=True, deprecated=True)]

        report = self.render(old, new)

        self.assertIn("open-weights", report)
        self.assertIn("RETIRED", report)

    def test_a_headline_move_is_significant_and_jitter_is_not(self):
        old = [capture("Mover", intelligence=50, cost=1.0,
                       medianOutputTokensPerSecond=100.0)]
        new = [capture("Mover", intelligence=58, cost=1.0,
                       medianOutputTokensPerSecond=180.0)]

        report = self.render(old, new)

        self.assertIn("intelligenceIndex: 50 -> 58", report)
        # Rendered speed moved past the tolerance, so it is reported — but in
        # its own section, not interleaved with the real news.
        self.assertIn("== rendered speed re-sampled", report)
        self.assertNotIn("medianOutputTokensPerSecond: 100 -> 180",
                         report.split("== rendered speed")[0])

    def test_the_undefined_sentinel_produces_no_hit_at_all(self):
        # The bug that made a re-encoding look like 615 models moving.
        old = [capture("Steady")]
        new = [capture("Steady", trainingTokensTrillions="$undefined")]

        report = self.render(old, new)

        self.assertIn("(none)", report)
        self.assertIn("no material change", diff_aa.as_commit_message(report))

    def test_unchanged_frontier_sections_are_omitted(self):
        # A quiet capture used to spend most of its summary on five frontier
        # sections whose only content was "(unchanged)".
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = [capture("Incumbent", intelligence=50, cost=1.0)]

        report = self.render(old, new)

        for label in ("efficient frontier (expanded)",
                      "efficient frontier (effort-collapsed)",
                      "coding frontier", "agentic frontier",
                      "parameter-efficiency frontier"):
            self.assertNotIn(label, report)
        self.assertNotIn("(unchanged)", report)

    def test_a_frontier_entry_is_reported_for_every_chart(self):
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = old + [capture("Cheaper", intelligence=55, cost=0.2)]

        report = self.render(old, new)

        for label in ("efficient frontier (expanded)", "coding frontier",
                      "agentic frontier", "parameter-efficiency frontier"):
            self.assertIn(f"== {label}", report)
        self.assertIn("+ Cheaper", report)


class LoadTests(unittest.TestCase):
    def test_a_git_revision_that_does_not_exist_exits_with_a_message(self):
        with self.assertRaises(SystemExit) as caught:
            diff_aa.load("git:no-such-rev-at-all")

        self.assertIn("cannot read", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
