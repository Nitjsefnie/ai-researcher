import argparse
import ast
import contextlib
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import diff_aa  # noqa: E402  # pylint: disable=wrong-import-position
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

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
    @staticmethod
    def without_speed(report: str) -> str:
        """A report with the rendered-speed section stripped, standing in for
        a capture where no rendered speed moved past the tolerance."""
        out, dropping = [], False
        for line in report.splitlines():
            if line.startswith("== "):
                dropping = line.startswith("== rendered speed")
            if not dropping:
                out.append(line)
        return "\n".join(out)

    @staticmethod
    def without_frontier(report: str) -> str:
        """A report with the frontier section gone.

        print_report OMITS a frontier section whose membership did not change,
        so "unchanged" is an ABSENT section, never a present one with equal
        counts. Editing the header counts and leaving the entries behind would
        build a report the differ can never emit."""
        out, dropping = [], False
        for line in report.splitlines():
            if line.startswith("== "):
                dropping = line.startswith("== efficient frontier")
            if not dropping:
                out.append(line)
        return "\n".join(out)

    def quiet(self) -> str:
        """REPORT with every material mover removed."""
        text = self.without_frontier(self.without_speed(REPORT))
        return text.replace("== models added: 6", "== models added: 0")

    def test_subject_names_who_moved_on_the_frontier(self):
        # Who is on the efficient frontier is the analytical payload, so it
        # outranks the model count and the re-sampled throughput for the
        # limited room a subject line has.
        subject = diff_aa.as_commit_message(REPORT).splitlines()[0]

        self.assertEqual(
            subject,
            "Refresh capture: 616 models, intelligence frontier: Grok 4.6 (xhigh) in")
        self.assertLessEqual(len(subject), diff_aa.SUBJECT_WIDTH)

    def test_a_frontier_swap_is_reported_even_though_the_count_holds(self):
        # One model in, one out leaves 17 -> 17. Reporting only the count made
        # the single most interesting kind of refresh look like no news at all.
        swap = REPORT.replace(
            "== efficient frontier (expanded): 16 -> 17 of 136 -> 142",
            "== efficient frontier (expanded): 17 -> 17 of 136 -> 142").replace(
            "  + Grok 4.6 (xhigh)  II 60.0  $1.04/task",
            "  + Grok 4.6 (xhigh)  II 60.0  $1.04/task\n"
            "  - Opus 4.8 (max)  II 59.0  $3.00/task")

        subject = diff_aa.as_commit_message(swap).splitlines()[0]

        self.assertIn("frontier", subject)
        self.assertLessEqual(len(subject), diff_aa.SUBJECT_WIDTH)

    def test_a_model_name_containing_spaces_survives_extraction(self):
        moves = diff_aa.frontier_moves(REPORT.splitlines())

        self.assertEqual(moves, [("intelligence", ["Grok 4.6 (xhigh)"], [])])

    def test_added_models_are_not_mistaken_for_frontier_entries(self):
        # "== models added" also lists "  + Name" lines; only the frontier
        # sections may contribute to the frontier clause.
        moves = diff_aa.frontier_moves(self.without_frontier(REPORT).splitlines())

        self.assertEqual(moves, [])

    def test_the_noisiest_clause_is_dropped_before_the_subject_overflows(self):
        # All three clauses never fit together. The body keeps every section in
        # full, so the subject drops re-sampled speed rather than truncating.
        subject = diff_aa.as_commit_message(REPORT).splitlines()[0]

        self.assertNotIn("rendered speed", subject)
        self.assertIn("rendered speed", diff_aa.as_commit_message(REPORT))

    def test_subject_says_so_when_nothing_material_moved(self):
        self.assertEqual(diff_aa.as_commit_message(self.quiet()).splitlines()[0],
                         "Refresh capture: 616 models, nothing the page renders")

    def test_speed_moves_alone_count_as_material(self):
        # Issue 9: a run whose only movement was rendered speed past the
        # tolerance was committed as "no material change" — and the moves
        # were dropped from the body. The section is already threshold-
        # filtered and the page renders those numbers, so it is material.
        speed_only = self.without_frontier(REPORT).replace(
            "== models added: 6", "== models added: 0")

        self.assertEqual(
            diff_aa.as_commit_message(speed_only).splitlines()[0],
            "Refresh capture: 616 models, 769 rendered speed moves")

    def test_a_single_speed_move_is_not_pluralised(self):
        one = self.without_frontier(REPORT).replace(
            "== models added: 6", "== models added: 0").replace(
            "more than 25%: 769 value(s)", "more than 25%: 1 value(s)")

        self.assertEqual(
            diff_aa.as_commit_message(one).splitlines()[0],
            "Refresh capture: 616 models, 1 rendered speed move")

    def test_keeps_the_thresholded_speed_section(self):
        body = diff_aa.as_commit_message(REPORT)

        self.assertIn("== rendered speed re-sampled by more than 25%", body)
        self.assertIn("Muse Spark 1.2 (xhigh)", body)
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

    def test_an_empty_list_is_absence_not_a_value(self):
        # AA seeded a per-eval array as [] on every model in one crawl.
        self.assertEqual(diff_aa.flatten({"a": [], "b": 1}), {"b": 1})

    def test_a_slug_keyed_list_flattens_to_one_leaf_per_element(self):
        # AA's per-evaluation arrays are records keyed by slug, not ordered
        # tuples. Kept whole, one re-sampled timePerTask inside compares as a
        # change to the entire 3 KB array and prints it twice per model --
        # which is what made a routine refresh a 300 KB commit message.
        flat = diff_aa.flatten({"intelligenceIndexEvaluations": [
            {"slug": "scicode", "score": 0.6, "timePerTask": 115.0},
            {"slug": "critpt", "score": 0.3, "timePerTask": 1056.0},
        ]})
        self.assertEqual(flat, {
            "intelligenceIndexEvaluations[scicode].score": 0.6,
            "intelligenceIndexEvaluations[scicode].timePerTask": 115.0,
            "intelligenceIndexEvaluations[critpt].score": 0.3,
            "intelligenceIndexEvaluations[critpt].timePerTask": 1056.0,
        })

    def test_a_list_that_is_not_slug_keyed_stays_whole(self):
        # Order is AA's; a tuple compared element-wise would report a reorder
        # as N moves.
        self.assertEqual(diff_aa.flatten({"tags": ["a", "b"]}), {"tags": ["a", "b"]})
        self.assertEqual(diff_aa.flatten({"pairs": [{"x": 1}, {"x": 2}]}),
                         {"pairs": [{"x": 1}, {"x": 2}]})


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
        "slug": (ident or name.lower().replace(" ", "-")),
        "intelligenceIndex": intelligence,
        "gdpvalNormalized": None if intelligence is None else intelligence / 100,
        "parameters": params,
        "intelligenceIndexCostPerTask": {
            "cost": {"total": cost},
            "evaluations": [
                {"slug": "gdpval-aa", "weightedCostPerTask": cost / 10},
                {"slug": "scicode", "weightedCostPerTask": cost / 4},
            ],
        },
    }
    model.update(extra)
    return model


def agent_capture(name, *, score=0.6, cost=2.0, host="fixturelab_incumbent"):
    """One Coding Agent Index row, in AA's own shape."""
    return {
        "id": name.lower().replace(" ", "-"),
        "displayLabel": name,
        "agentName": name.split(" - ")[0],
        "hostModelSlug": host,
        "display": {"creator": {"agent": "Fixture Agents", "model": "Fixture Lab"}},
        "indexScore": score,
        "mean": {"costUsd": cost, "agentWallTimeSec": 900.0},
    }


class ClassifyTests(unittest.TestCase):
    def test_speed_fields_the_page_shows_are_jitter_and_the_rest_unused(self):
        # A jitter field the page renders gets a threshold; one it never shows
        # cannot change the artifact, so it is dropped outright.
        self.assertEqual(diff_aa.classify("medianOutputTokensPerSecond"), "jitter")
        self.assertEqual(diff_aa.classify("percentile95OutputTokensPerSecond"),
                         "jitter-unused")
        self.assertEqual(diff_aa.classify("medianTimeToFirstTokenSeconds"),
                         "jitter-unused")

    def test_per_evaluation_leaves_are_never_significant(self):
        # The array element's slug is part of the path, the leaf still decides.
        self.assertEqual(
            diff_aa.classify("intelligenceIndexEvaluations[scicode].timePerTask"),
            "jitter-unused")
        self.assertEqual(
            diff_aa.classify("intelligenceIndexEvaluations[scicode].score"),
            "derived")
        self.assertEqual(
            diff_aa.classify("intelligenceIndexEvaluations[gdpval-aa].costPerTask"),
            "derived")

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

    def test_a_string_value_renders_on_one_physical_line(self):
        # The string branch of fmt() is the one escape hatch raw capture text
        # reaches the report through; numbers, bools and JSON-dumped
        # containers are already line-safe.
        self.assertEqual(diff_aa.fmt("a\n\nCo-Authored-By: crafted <c@example.invalid>"),
                         "a Co-Authored-By: crafted <c@example.invalid>")
        self.assertEqual(diff_aa.fmt(0.123456789), "0.123457")
        self.assertEqual(diff_aa.fmt({"a": 1}), '{"a":1}')


class SanitizeTests(unittest.TestCase):
    """The one-line sanitizer every rendering of captured data goes through.

    Captured text is third-party data (AA's corpus) and reaches two injection
    surfaces: `git commit -F` on main and the job summary's Markdown fence."""

    def test_a_trailer_injection_collapses_to_one_physical_line(self):
        crafted = "X\n\nCo-Authored-By: crafted <crafted@example.invalid>"
        out = diff_aa.one_line(crafted)

        self.assertNotIn("\n", out)
        self.assertFalse(any(line.startswith("Co-Authored-By")
                             for line in out.splitlines()))

    def test_every_control_and_unicode_line_break_collapses_to_a_space(self):
        self.assertEqual(
            diff_aa.one_line("a\r\nb\x00c\x0bd\x7fe\x85f\u2028g\u2029h\u00a0i"),
            "a b c d e f g h i")

    def test_a_fence_escape_stays_on_one_line(self):
        # A newline-free value cannot close the summary's ``` fence: the
        # renderer always prefixes the line, and a fence marker needs the
        # line to itself.
        out = diff_aa.one_line("```\n\ninjected markdown\n```")

        self.assertNotIn("\n", out)
        # A name that merely STARTS with a fence still needs the backticks
        # gone: the changed-models header indents it two spaces, and
        # CommonMark opens a fence at up to three.
        self.assertEqual(diff_aa.one_line("```open"), "open")
        self.assertEqual(diff_aa.one_line("`tick"), "tick")
        # Interior backticks are inert and stay.
        self.assertEqual(diff_aa.one_line("just `quoted`"), "just `quoted`")

    def test_a_long_value_is_capped_and_marked_with_an_ellipsis(self):
        self.assertEqual(diff_aa.one_line("n" * 200), "n" * 160 + "…")

    def test_a_value_exactly_at_the_cap_is_not_marked(self):
        self.assertEqual(diff_aa.one_line("n" * 160), "n" * 160)

    def test_internal_whitespace_runs_collapse_to_single_spaces(self):
        # The report delimits name/metric fields with a double space and
        # frontier_moves() parses on it, so a captured name must never carry
        # a whitespace run of its own.
        self.assertEqual(diff_aa.one_line("Model\t1   (xhigh)\n\nName"),
                         "Model 1 (xhigh) Name")

    def test_non_string_values_render_through_str(self):
        self.assertEqual(diff_aa.one_line(42), "42")
        self.assertEqual(diff_aa.one_line(None), "None")

    def test_a_sanitized_name_still_parses_back_out_of_the_report(self):
        # frontier_moves() reads "+ Name  II ..." back by splitting on the
        # double space; a name whose internal runs collapsed survives whole.
        name = diff_aa.one_line("Swap In  Up\nNow")
        lines = ["== efficient frontier (expanded): 1 -> 1 of 2 -> 2 plotted",
                 f"  + {name}  II 55.0  $0.20/task"]

        self.assertEqual(diff_aa.frontier_moves(lines),
                         [("intelligence", ["Swap In Up Now"], [])])

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

        names, rows = diff_aa.chart_frontier(models, [], "parameters")

        self.assertEqual([r["name"] for r in rows], ["Open"])
        self.assertIn("Open", names)

    def test_a_cost_chart_drops_models_with_no_measurement_for_it(self):
        models = [capture("Measured", intelligence=50),
                  capture("Unmeasured", ident="unmeasured", intelligence=50,
                          intelligenceIndexCostPerTask=None)]

        _, rows = diff_aa.chart_frontier(models, [], "agentic")

        self.assertEqual([r["name"] for r in rows], ["Measured"])

    def test_the_coding_frontier_is_drawn_over_the_agent_capture(self):
        # Coding rows come from a different AA product entirely, so feeding it
        # the model capture must not silently produce a model-shaped frontier.
        models = [capture("Incumbent", intelligence=50)]
        agents = [agent_capture("Agent - Incumbent", score=0.6, cost=2.0),
                  agent_capture("Agent - Dominated", score=0.5, cost=4.0)]

        names, rows = diff_aa.chart_frontier(models, agents, "coding")

        self.assertEqual(sorted(r["name"] for r in rows),
                         ["Agent - Dominated", "Agent - Incumbent"])
        self.assertEqual(list(names), ["Agent - Incumbent"])


class ReportTests(unittest.TestCase):
    """End-to-end: two captures in, a report out, rendered to a message."""

    def render(self, old, new, tol=0.0):
        old_path = pathlib.Path(self.tmp) / "old.json"
        new_path = pathlib.Path(self.tmp) / "new.json"
        old_path.write_text(json.dumps(old), encoding="utf-8")
        new_path.write_text(json.dumps(new), encoding="utf-8")
        args = argparse.Namespace(old=str(old_path), new=str(new_path),
                                  speed_tol=0.25, tol=tol, derived=False,
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
        subject = diff_aa.as_commit_message(report).splitlines()[0]
        # The newcomer displaces the incumbent on three charts at once. The
        # effort-collapsed frontier is a second VIEW of the intelligence
        # chart, so it must not inflate that count to four.
        self.assertEqual(
            subject,
            "Refresh capture: 2 models, 6 frontier moves across 3 charts, +1/-0")

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

    def test_a_per_evaluation_resample_never_prints_the_array(self):
        evals = [{"slug": "scicode", "score": 0.63, "costPerTask": 0.66,
                  "timePerTask": 115.36},
                 {"slug": "critpt", "score": 0.30, "costPerTask": 5.71,
                  "timePerTask": 1056.08}]
        resampled = [dict(e, timePerTask=e["timePerTask"] * 1.4) for e in evals]
        old = [capture("Steady", intelligenceIndexEvaluations=evals)]
        new = [capture("Steady", intelligenceIndexEvaluations=resampled)]

        report = self.render(old, new)

        self.assertIn("(none)", report)
        self.assertNotIn("intelligenceIndexEvaluations", report)
        self.assertIn("nothing the page renders", diff_aa.as_commit_message(report))

    def test_a_score_wiggle_inside_the_tolerance_is_discarded_and_counted(self):
        # gdpvalNormalized is an Elo renormalised over the field, so every
        # newcomer nudges every incumbent by a hundredth of a percent -- a
        # dozen lines of +0.01% per refresh that no reader can act on.
        old = [capture("Steady", intelligence=50, gdpvalNormalized=0.54762)]
        new = [capture("Steady", intelligence=50, gdpvalNormalized=0.547705)]

        report = self.render(old, new, tol=0.005)

        self.assertIn("(none)", report)
        self.assertNotIn("gdpvalNormalized", report)
        self.assertIn("1 other numeric moves <= 0.5%", report)

    def test_a_score_move_past_the_tolerance_is_still_reported(self):
        old = [capture("Mover", intelligence=50, gdpvalNormalized=0.500)]
        new = [capture("Mover", intelligence=50, gdpvalNormalized=0.504)]

        report = self.render(old, new, tol=0.005)

        self.assertIn("gdpvalNormalized: 0.5 -> 0.504", report)

    def test_the_undefined_sentinel_produces_no_hit_at_all(self):
        # The bug that made a re-encoding look like 615 models moving.
        old = [capture("Steady")]
        new = [capture("Steady", trainingTokensTrillions="$undefined")]

        report = self.render(old, new)

        self.assertIn("(none)", report)
        self.assertIn("nothing the page renders", diff_aa.as_commit_message(report))

    def test_unchanged_frontier_sections_are_omitted(self):
        # A quiet capture used to spend most of its summary on five frontier
        # sections whose only content was "(unchanged)".
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = [capture("Incumbent", intelligence=50, cost=1.0)]

        report = self.render(old, new)

        for label in ("efficient frontier (expanded)",
                      "efficient frontier (effort-collapsed)",
                      "coding agent frontier", "GDPval-AA frontier",
                      "parameter-efficiency frontier"):
            self.assertNotIn(label, report)
        self.assertNotIn("(unchanged)", report)

    def test_a_frontier_entry_is_reported_for_every_chart(self):
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = old + [capture("Cheaper", intelligence=55, cost=0.2)]

        report = self.render(old, new)

        for label in ("efficient frontier (expanded)", "GDPval-AA frontier",
                      "parameter-efficiency frontier"):
            self.assertIn(f"== {label}", report)
        self.assertIn("+ Cheaper", report)

    def test_a_crafted_name_cannot_inject_a_trailer_into_the_commit_message(self):
        # Issue 41: the report becomes `git commit -F` on main, so a crafted
        # capture name carrying newlines could forge trailers or a subject.
        crafted = "X\n\nCo-Authored-By: crafted <crafted@example.invalid>"
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = old + [capture(crafted, ident="crafted", intelligence=62, cost=0.5)]

        report = self.render(old, new)
        message = diff_aa.as_commit_message(report)

        self.assertFalse(any(line.startswith("Co-Authored-By")
                             for line in message.splitlines()))
        # The name still reads as one model on one physical line.
        self.assertIn("+ X Co-Authored-By: crafted <crafted@example.invalid>  ",
                      report)

    def test_a_crafted_name_cannot_break_the_summary_fence(self):
        # The workflow wraps diff.txt in ``` fences in GITHUB_STEP_SUMMARY.
        crafted = "```\n\ninjected markdown\n```"
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = old + [capture(crafted, ident="crafted2", intelligence=62, cost=0.5)]

        report = self.render(old, new)
        message = diff_aa.as_commit_message(report)

        for text in (report, message):
            self.assertFalse(any(line.lstrip().startswith("```")
                                 for line in text.splitlines()))


class DisputeSectionTests(unittest.TestCase):
    """The differ learns the dispute layer (issue #208).

    `genVariants` is a TOP-LEVEL record key carrying the whole per-generation
    list, so its movement between two captures is section news -- one line
    per shape -- and never a per-model field line: printing the variant list
    per model is exactly the per-field spam the section exists to prevent.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def render(self, old, new):
        root = pathlib.Path(self.tmp)
        for name, data in (("old.json", old), ("new.json", new)):
            (root / name).write_text(json.dumps(data), encoding="utf-8")
        args = argparse.Namespace(old=str(root / "old.json"),
                                  new=str(root / "new.json"),
                                  speed_tol=0.25, tol=0.0, derived=False,
                                  all=False, commit_msg=False)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            diff_aa.print_report(args)
        return buffer.getvalue()

    def test_the_dispute_key_is_its_own_class(self):
        # Explicit classification: the key is top-level and not jitter-shaped,
        # so nothing in the JITTER/derived/cosmetic machinery files it -- but
        # the class must be its own, never "significant": the default would
        # print the whole variant list, once per model, in field changes.
        self.assertEqual(diff_aa.classify("genVariants"), "disputes")

    def test_variants_appearing_are_one_section_line_never_per_model_lines(self):
        old = [capture("Incumbent", intelligence=50)]
        new = [dict(capture("Incumbent", intelligence=50), genVariants=[
            {"ii": 50.0, "cost": 0.75, "gdpval": 0.50},
            {"ii": 51.0, "cost": 0.80, "gdpval": 0.49},
        ])]

        report = self.render(old, new)

        self.assertIn("== disputes", report)
        self.assertIn("genVariants appeared on 1 model(s)", report)
        # The only cheap per-model conflict count there is: models whose
        # genVariants carry more than one variant. Labeled as what it is --
        # multiplicity -- because two agreeing variants render no red cell.
        self.assertIn("1 model(s) carry more than one variant", report)
        self.assertNotIn("genVariants:", report)

    def test_variants_disappearing_and_changing_are_one_line_each(self):
        pair = [{"ii": 50.0, "cost": 0.75}, {"ii": 51.0, "cost": 0.80}]
        old = [
            dict(capture("Dropped", ident="dropped", intelligence=50),
                 genVariants=[{"ii": 50.0, "cost": 0.75}]),
            dict(capture("Moved", ident="moved", intelligence=50),
                 genVariants=pair),
            dict(capture("Quiet", ident="quiet", intelligence=50),
                 genVariants=pair),
        ]
        new = [
            capture("Dropped", ident="dropped", intelligence=50),
            dict(capture("Moved", ident="moved", intelligence=50),
                 genVariants=[{"ii": 50.0, "cost": 0.75},
                              {"ii": 52.0, "cost": 0.80}]),
            dict(capture("Quiet", ident="quiet", intelligence=50),
                 genVariants=pair),
        ]

        report = self.render(old, new)

        self.assertIn("== disputes", report)
        self.assertIn("genVariants disappeared from 1 model(s)", report)
        self.assertIn("genVariants changed on 1 model(s)", report)
        self.assertNotIn("genVariants appeared on", report)
        # The multi-variant count is a property of the new capture -- the
        # news-free "Quiet" model counts too, because it is the bridge
        # between the capture log's carriers count and the real thing.
        self.assertIn("2 model(s) carry more than one variant", report)

    def test_no_variants_on_either_side_prints_no_section(self):
        # Today's output byte-shape: a quiet capture gains no section at all.
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = [capture("Incumbent", intelligence=58, cost=1.0)]

        report = self.render(old, new)

        self.assertNotIn("== disputes", report)
        self.assertNotIn("genVariants", report)

    def test_identical_variants_on_both_sides_print_no_section(self):
        # A disputed state that did not move between the captures is not
        # news either -- the same discipline that omits unchanged frontiers.
        pair = [{"ii": 50.0, "cost": 0.75}, {"ii": 51.0, "cost": 0.80}]
        old = [dict(capture("Steady", intelligence=50), genVariants=pair)]
        new = [dict(capture("Steady", intelligence=50), genVariants=list(pair))]

        report = self.render(old, new)

        self.assertNotIn("== disputes", report)
        self.assertNotIn("genVariants:", report)

    def test_the_disputes_section_reaches_the_commit_message_body(self):
        # as_commit_message carries the full report as its body, so the one
        # place a scheduled refresh says anything is the commit itself.
        old = [capture("Incumbent", intelligence=50)]
        new = [dict(capture("Incumbent", intelligence=50), genVariants=[
            {"ii": 50.0, "cost": 0.75}, {"ii": 51.0, "cost": 0.80},
        ])]

        report = self.render(old, new)
        message = diff_aa.as_commit_message(report)

        self.assertIn("== disputes", message)
        self.assertIn("genVariants appeared on 1 model(s)", message)

    def test_a_disputes_only_hour_is_material_in_the_subject(self):
        # A run whose ONLY news is the Disputes section used to be committed
        # as "nothing the page renders" -- while the page genuinely changed,
        # both generations rendering red on it. The section's count lines are
        # news, and the subject carries them.
        old = [capture("Incumbent", intelligence=50)]
        new = [dict(capture("Incumbent", intelligence=50), genVariants=[
            {"ii": 50.0, "cost": 0.75}, {"ii": 51.0, "cost": 0.80},
        ])]

        report = self.render(old, new)
        subject = diff_aa.as_commit_message(report).splitlines()[0]

        self.assertIn("disputed value", subject)
        self.assertNotIn("nothing the page renders", subject)

    def test_the_disputes_clause_is_derived_from_the_sections_count_lines(self):
        # N is the moved values (appeared + disappeared + changed), M the
        # models the new capture carries more than one variant on. The
        # "across" half is printed only where the two counts differ, so the
        # common appearance hour -- every carrier is a mover -- keeps the
        # clause short enough to co-fit a frontier clause within the width.
        gv = [{"ii": 50.0, "cost": 0.75}, {"ii": 51.0, "cost": 0.80}]
        old = [capture("Incumbent", intelligence=50)]
        new = [dict(capture("Incumbent", intelligence=50), genVariants=gv)]

        subject = diff_aa.as_commit_message(
            self.render(old, new)).splitlines()[0]
        self.assertEqual(
            subject, "Refresh capture: 1 models, 1 disputed value")

        carrier = dict(capture("Carrier", ident="carrier", intelligence=49),
                       genVariants=[{"ii": 49.0, "cost": 0.75},
                                    {"ii": 48.5, "cost": 0.80}])
        old = [capture("Incumbent", intelligence=50), carrier]
        new = [dict(capture("Incumbent", intelligence=50), genVariants=gv),
               dict(carrier)]

        subject = diff_aa.as_commit_message(
            self.render(old, new)).splitlines()[0]
        self.assertEqual(
            subject,
            "Refresh capture: 2 models, 1 disputed value across 2 models")

    def test_disputes_and_frontier_moves_coexist_in_the_subject(self):
        # Both clauses present: the frontier phrase names the move, the
        # disputes clause names the layer, and the pair fits the
        # conventional width -- a disputes hour is not silently demoted to
        # the body the moment a frontier also moved.
        gv = [{"ii": 50.0, "cost": 0.75}, {"ii": 49.5, "cost": 0.80}]

        def gdp(model, weighted):
            out = dict(model)
            out["intelligenceIndexCostPerTask"] = {
                "cost": {"total": 0.75},
                "evaluations": [
                    {"slug": "gdpval-aa", "weightedCostPerTask": weighted},
                    {"slug": "scicode",
                     "weightedCostPerTask": 0.75 - weighted},
                ],
            }
            return out

        old = [gdp(capture("Alpha", intelligence=50), 0.075),
               gdp(capture("Ex", ident="ex", intelligence=49), 0.030)]
        new = [dict(gdp(capture("Alpha", intelligence=50), 0.025),
                    genVariants=gv),
               gdp(capture("Ex", ident="ex", intelligence=49), 0.030)]

        subject = diff_aa.as_commit_message(
            self.render(old, new)).splitlines()[0]

        self.assertEqual(
            subject,
            "Refresh capture: 2 models, GDPval-AA frontier: Ex out, "
            "1 disputed value")

    def test_the_disputes_clause_outranks_the_speed_clause(self):
        # The width budget spends itself most-newsworthy first: a moved
        # dispute layer outranks a re-sampled speed number, so when the two
        # clauses cannot both fit, the speed clause is the one dropped --
        # into the body, which carries every section in full.
        gv = [{"ii": 50.0, "cost": 0.75}, {"ii": 49.5, "cost": 0.80}]

        def gdp(model, weighted):
            out = dict(model)
            out["intelligenceIndexCostPerTask"] = {
                "cost": {"total": 0.75},
                "evaluations": [
                    {"slug": "gdpval-aa", "weightedCostPerTask": weighted},
                    {"slug": "scicode",
                     "weightedCostPerTask": 0.75 - weighted},
                ],
            }
            return out

        old = [gdp(capture("Alpha", intelligence=50,
                           medianOutputTokensPerSecond=100.0), 0.075),
               gdp(capture("Ex", ident="ex", intelligence=49), 0.030)]
        new = [dict(gdp(capture("Alpha", intelligence=50,
                                medianOutputTokensPerSecond=180.0), 0.025),
                    genVariants=gv),
               gdp(capture("Ex", ident="ex", intelligence=49), 0.030)]

        message = diff_aa.as_commit_message(self.render(old, new))
        subject = message.splitlines()[0]

        self.assertIn("1 disputed value", subject)
        self.assertNotIn("rendered speed", subject)
        self.assertIn("rendered speed", message)

    def test_the_subject_is_unchanged_when_no_dispute_moved(self):
        # The quiet capture's subject is byte-what it was before the clause
        # existed: no disputes section, no disputes clause.
        old = [capture("Incumbent", intelligence=50)]
        new = [capture("Incumbent", intelligence=50)]

        subject = diff_aa.as_commit_message(
            self.render(old, new)).splitlines()[0]

        self.assertEqual(
            subject, "Refresh capture: 1 models, nothing the page renders")


class DisplayNameTests(unittest.TestCase):
    """Issue #88 in the differ: no report line carries AA's dict-form effort.

    The chart-frontier sections key on the row builders' names, so they clean
    through build.py; `line()` and the two section headers printed the raw
    capture name directly and wrap it in build.display_name instead. The
    exact-line pins also hold `line()`'s II/cost lookup to the CLEANED key: a
    lookup left on the raw name matches nothing and silently degrades every
    changed model's II/cost to the em-dash fallback ("62.0" -> "62",
    "$0.50" -> "—").
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def render(self, old, new, old_agents=None, new_agents=None, tol=0.0):
        """Two captures in, a report out -- with the captures named
        "...-models.json" so the coding-agents siblings resolve beside them,
        the way load() finds them for a path spec."""
        root = pathlib.Path(self.tmp)
        for name, data in (("old-models.json", old),
                           ("new-models.json", new)):
            (root / name).write_text(json.dumps(data), encoding="utf-8")
        for name, data in (("old-coding-agents.json", old_agents),
                           ("new-coding-agents.json", new_agents)):
            if data is not None:
                (root / name).write_text(json.dumps(data), encoding="utf-8")
        args = argparse.Namespace(old=str(root / "old-models.json"),
                                  new=str(root / "new-models.json"),
                                  old_agents=None, new_agents=None,
                                  speed_tol=0.25, tol=tol, derived=False,
                                  all=False, commit_msg=False)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            diff_aa.print_report(args)
        return buffer.getvalue()

    def test_no_report_line_carries_the_dict_effort_text(self):
        old = [capture("Incumbent", intelligence=50, cost=1.0)]
        new = old + [capture("Newcomer ({'reasoning_effort': 'max'})",
                             ident="newcomer", intelligence=62, cost=0.5)]
        old_agents = [agent_capture(
            "Codex - GPT-6 Luna (max) ({'reasoning_effort': 'max'})",
            score=0.5, cost=4.0)]
        new_agents = old_agents + [agent_capture(
            "Codex - GPT-6 Luna (xhigh) ({'reasoning_effort': 'xhigh'})",
            score=0.65, cost=1.5)]

        report = self.render(old, new, old_agents, new_agents)

        self.assertNotIn("reasoning_effort", report)
        self.assertIn(
            "  + Newcomer (max)  [Fixture Lab]  II 62.0  cost/task $0.50",
            report)
        self.assertIn("== coding agent frontier: 1 -> 1 of 1 -> 2 plotted",
                      report)
        self.assertIn("  + Codex - GPT-6 Luna (xhigh)  65.0  $1.50/task",
                      report)
        self.assertIn("  - Codex - GPT-6 Luna (max)  50.0  $4.00/task", report)

    def test_the_field_changes_header_carries_the_cleaned_name(self):
        # A sink the issue text does not name: the per-model header of the
        # field-changes section prints the raw capture name directly.
        old = [capture("Steady ({'reasoning_effort': 'high'})",
                       intelligence=50)]
        new = [capture("Steady ({'reasoning_effort': 'high'})",
                       intelligence=58)]

        report = self.render(old, new)

        self.assertNotIn("reasoning_effort", report)
        self.assertIn("  Steady (high)  [Fixture Lab]", report)

    def test_the_rendered_speed_section_carries_the_cleaned_name(self):
        # The rendered-speed section's per-model lines are the other raw-name
        # sink the issue text does not name.
        old = [capture("Fast ({'reasoning_effort': 'high'})", intelligence=50,
                       medianOutputTokensPerSecond=100.0)]
        new = [capture("Fast ({'reasoning_effort': 'high'})", intelligence=50,
                       medianOutputTokensPerSecond=180.0)]

        report = self.render(old, new)

        self.assertNotIn("reasoning_effort", report)
        self.assertIn(
            "  Fast (high)  [Fixture Lab]  "
            "medianOutputTokensPerSecond: 100 -> 180  (+80, +80.00%)", report)

    def test_the_differ_cleans_names_by_the_same_rule_build_does(self):
        # The shared-literal pin: the real capture's dict labels, through the
        # differ's coding-frontier sink, come out exactly build.display_name's
        # answer -- one rule, both modules.
        for raw, cleaned in (
            ("Opencode - GLM-5.3 ({'reasoning_effort': 'max'})",
             "Opencode - GLM-5.3 (max)"),
            ("Codex - GPT-6 Luna (max) ({'reasoning_effort': 'max'})",
             "Codex - GPT-6 Luna (max)"),
            ("Codex - GPT-5.6 Sol (max) ({'reasoning_effort': 'max'})",
             "Codex - GPT-5.6 Sol (max)"),
        ):
            with self.subTest(raw=raw):
                report = self.render(
                    [], [capture("Anchor", intelligence=50)],
                    [], [agent_capture(raw, score=0.6, cost=2.0)])

                self.assertIn(
                    f"  + {build.display_name(raw)}  60.0  $2.00/task", report)
                self.assertNotIn("reasoning_effort", report)
                self.assertEqual(build.display_name(raw), cleaned)

    def test_a_record_without_a_name_still_renders_one_line(self):
        # The degenerate record -- no name at all -- renders exactly as
        # before: the cleaning wraps a string name only.
        self.assertEqual(diff_aa.shown_name({}), "None")


class RealCaptureTests(unittest.TestCase):
    """Run the differ over the CAPTURE THIS REPO ACTUALLY SHIPS.

    EVERY ASSERTION HERE MUST BE AN INVARIANT, never a value read off today's
    data. The capture changes hourly by design, so a literal count, model name
    or score pinned here is a build failure with a date on it. Assert shapes,
    relationships and things derived from the capture itself.

    Every other test here builds its own records, so they all carry whatever
    fields the fixture author remembered -- which means the suite stayed green
    while AA deleted `id` from the payload and the differ, keyed on it, raised
    KeyError on the first scheduled run. Fixtures cannot catch a schema drift
    they are not made of; the committed capture can.
    """

    def test_the_differ_survives_the_committed_capture(self):
        path = str(build.RAW)
        args = argparse.Namespace(old=path, new=path,
                                  old_agents=None, new_agents=None,
                                  speed_tol=0.25, tol=0.0, derived=False,
                                  all=False, commit_msg=False)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            diff_aa.print_report(args)
        report = buffer.getvalue()

        self.assertIn("== models added: 0", report)
        self.assertIn("== models removed: 0", report)

    def test_every_committed_record_has_the_identity_the_differ_keys_on(self):
        models = json.loads(build.RAW.read_text(encoding="utf-8"))

        keys = [diff_aa.key(m) for m in models]

        self.assertEqual(len(set(keys)), len(models))

    def test_a_commit_message_renders_from_the_committed_capture(self):
        # The same two steps the workflow runs: report, then render it as a
        # message. `--commit-msg` is handled in main(), so print_report alone
        # would not exercise the renderer.
        path = str(build.RAW)
        args = argparse.Namespace(old=path, new=path,
                                  old_agents=None, new_agents=None,
                                  speed_tol=0.25, tol=0.0, derived=False,
                                  all=False, commit_msg=False)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            diff_aa.print_report(args)

        message = diff_aa.as_commit_message(buffer.getvalue())

        self.assertRegex(message, r"^Refresh capture: \d+ models")
        # DERIVED, never pinned. An earlier version of this line asserted
        # "644 models" and failed the build the next day because AA published
        # a 645th -- a test over live data asserting a live VALUE is a
        # scheduled failure, not a check. Tie it to the capture instead.
        self.assertIn(f"{len(json.loads(build.RAW.read_text(encoding='utf-8')))} models",
                      message)


class ClassifierStructureTests(unittest.TestCase):
    """The classifier's structural rule, checked over the committed capture.

    Both assertions are invariants, not a pinned field list: AA adding a
    nested family must be silent, and every field the page reads must be
    reportable. A pinned list would go red on every harmless AA addition;
    these go red only when a change could alter what the commit message says.
    """

    def test_no_nested_path_is_significant_unless_it_is_a_named_headline(self):
        # The detail-route merge brought eighteen nested families at once --
        # latency percentiles, per-prompt-type re-samples, Elo CIs -- and the
        # name-based classifier reported every one as an index move.
        models = json.loads(build.RAW.read_text(encoding="utf-8"))
        leaked = set()
        for m in models:
            for path in diff_aa.flatten(m):
                if "." in path and path not in diff_aa.HEADLINE_PATHS \
                        and diff_aa.classify(path) == "significant":
                    leaked.add(path.split(".", 1)[0])

        self.assertEqual(leaked, set(),
                         f"nested families reported as significant: {sorted(leaked)}")

    def test_every_field_the_page_reads_is_reportable(self):
        # If one of these moved and the differ swallowed it, the page would
        # change without the commit message saying so.
        rendered = {
            "name", "shortName", "slug", "modelCreatorName", "intelligenceIndex",
            "intelligenceIndexIsEstimated", "gdpvalNormalized", "parameters",
            "isOpenWeights", "deprecated", "isReasoning", "licenseName",
            "contextWindowTokens", "releaseDate", "price1mInputTokens",
            "price1mOutputTokens", "intelligenceIndexCostPerTask.cost.total",
        }
        shown_speed = {"medianOutputTokensPerSecond", "intelligenceIndexTimePerTask"}

        for path in rendered:
            self.assertEqual(diff_aa.classify(path), "significant", path)
        for path in shown_speed:
            self.assertEqual(diff_aa.classify(path), "jitter", path)

    def test_the_families_that_flooded_the_report_are_now_silent(self):
        for path in ("performanceByPromptType.medium.medianEndToEndResponseTime",
                     "endToEndResponseTime.answer", "outputSpeedVariance.p95",
                     "timeToFirstChunkVariance.q75", "timescaleData.medianTimeToFirstChunk",
                     "briefcaseBreakdown.overall.elo", "timeToFirstAnswerToken.total"):
            self.assertNotEqual(diff_aa.classify(path), "significant", path)
        for leaf in ("gdpval", "intelligenceIndexCost", "chartHighlighted",
                     "hostModelCount", "reasoningTokens"):
            self.assertNotEqual(diff_aa.classify(leaf), "significant", leaf)


class DefaultsTests(unittest.TestCase):
    def test_the_default_tolerance_hides_sub_half_percent_wiggles(self):
        # The workflow passes no --tol, so the default IS the commit-message
        # policy. Pinned here so a "tidy-up" back to 0 is a red test, not a
        # 300-line commit body the next morning.
        self.assertEqual(diff_aa.DEFAULT_TOL, 0.005)


class LoadTests(unittest.TestCase):
    def test_a_git_revision_that_does_not_exist_exits_with_a_message(self):
        with self.assertRaises(SystemExit) as caught:
            diff_aa.load("git:no-such-rev-at-all")

        self.assertIn("cannot read", str(caught.exception))


def tracked_texts(root: pathlib.Path) -> dict[str, str]:
    """Every git-tracked file's text, except captured/generated artifacts.

    data/ holds the captures and out/ the page built from them -- artifacts,
    not citations, so neither can keep a definition alive.
    """
    listed = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.split()
    return {rel: (root / rel).read_text(encoding="utf-8", errors="replace")
            for rel in listed
            if not rel.startswith(("data/", "out/"))}


def unreferenced_helpers(texts: dict[str, str], module_path: str) -> list[str]:
    """Module-level functions defined in `module_path` that nothing names.

    A reference is a whole-word occurrence of the helper's name in any of
    `texts`, other than inside the helper's own def block -- a function
    calling itself, or its own docstring promising a test that does not
    exist, is not a caller. Word-matching over file text (rather than a
    cross-module AST import graph) is deliberately cheap: the pin targets
    wholesale dead code, and a helper kept "alive" only by an unrelated
    common word is a review-visible edge.
    """
    dead = []
    for node in ast.parse(texts[module_path]).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first, last = node.lineno, node.end_lineno
        if last is None:
            continue  # no end line means no def block to exclude; skip
        referenced = False
        for path, text in texts.items():
            for hit in re.finditer(rf"\b{re.escape(node.name)}\b", text):
                if (path == module_path
                        and first <= text.count("\n", 0, hit.start()) + 1 <= last):
                    continue  # naming itself is not a caller
                referenced = True
                break
            if referenced:
                break
        if not referenced:
            dead.append(node.name)
    return dead


class NoDeadHelpersTests(unittest.TestCase):
    """Issue #61: diff_aa.py carried a helper with zero call sites whose
    docstring claimed "the real-capture test pins this set" -- no test did.
    Deleted rather than decorated; this guard is the pin that must have
    caught it, and the fixtures below prove the guard itself fires.
    """

    MODULE = "scripts/diff_aa.py"

    def test_every_module_level_function_in_diff_aa_is_referenced_somewhere(self):
        root = pathlib.Path(__file__).resolve().parent.parent

        self.assertEqual(
            unreferenced_helpers(tracked_texts(root), self.MODULE), [],
            "dead helper(s) in " + self.MODULE
            + " -- delete them or wire a real caller, not a docstring claim")

    def test_the_reference_check_fires_on_a_planted_dead_helper(self):
        # The liveness oracle: the same checker over a synthetic tree flags
        # exactly the planted orphan, so the empty result above is evidence
        # and not a check that cannot fail.
        texts = {
            "helpers.py": "def used():\n    return 1\n\n\ndef unused_one():\n    return 2\n",
            "app.py": "import helpers\n\nhelpers.used()\n",
        }

        self.assertEqual(unreferenced_helpers(texts, "helpers.py"), ["unused_one"])

    def test_naming_itself_or_its_own_docstring_does_not_count_as_a_reference(self):
        # The hole the deleted helper fell through: a self-call and a docstring
        # naming the function both live inside its own def block, so neither
        # keeps it.
        texts = {
            "helpers.py": ('def orphan():\n    """orphan is pinned elsewhere."""\n'
                           "    return orphan()\n"
                           "\n\ndef live():\n    return 3\n"),
            "app.py": "import helpers\n\nhelpers.live()\n",
        }

        self.assertEqual(unreferenced_helpers(texts, "helpers.py"), ["orphan"])


if __name__ == "__main__":
    unittest.main()
