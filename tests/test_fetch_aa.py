import contextlib
import datetime
import email.message
import http.client
import io
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
import diff_aa  # noqa: E402  # pylint: disable=wrong-import-position
import build  # noqa: E402  # pylint: disable=wrong-import-position


def flight_html(*payloads: str) -> str:
    """A page carrying the RSC chunks the extractor reassembles. Each chunk is
    a JSON string literal in a self.__next_f.push call, exactly as Next.js
    emits it."""
    return "".join(
        f"<script>self.__next_f.push([1,{json.dumps(p)}])</script>"
        for p in payloads)


def model(fields: int, tag: str) -> dict:
    return {f"f{i}": f"{tag}{i}" for i in range(fields)}


class BalancedArrayTests(unittest.TestCase):
    def test_stops_at_the_matching_bracket(self):
        text = 'x=[1,[2],3] trailing'

        self.assertEqual(fetch_aa.balanced_array(text, 2), '[1,[2],3]')

    def test_brackets_inside_strings_do_not_count(self):
        # A model name containing a bracket would otherwise truncate the array.
        text = '["Grok 4.6 [xhigh]", 2]'

        self.assertEqual(fetch_aa.balanced_array(text, 0), text)

    def test_escaped_quote_does_not_open_a_string(self):
        text = '["a\\"]", 1]'

        self.assertEqual(fetch_aa.balanced_array(text, 0), text)

    def test_unterminated_array_is_none(self):
        self.assertIsNone(fetch_aa.balanced_array('[1,2', 0))


class FlightPayloadTests(unittest.TestCase):
    def test_concatenates_every_chunk_in_order(self):
        html = flight_html('{"a":', '1}')

        self.assertEqual(fetch_aa.flight_payload(html), '{"a":1}')

    def test_a_page_without_chunks_exits_rather_than_returning_empty(self):
        # The designed signal that AA changed its page structure.
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.flight_payload("<html>nothing here</html>")

        self.assertIn("page structure changed", str(caught.exception))


class RichestModelsArrayTests(unittest.TestCase):
    def test_picks_the_array_with_the_most_fields(self):
        thin = json.dumps([model(21, "thin")])
        rich = json.dumps([model(30, "rich")])
        payload = f'{{"models":{thin},"other":1,"models":{rich}}}'

        got = fetch_aa.richest_models_array(payload)

        self.assertEqual(len(got[0]), 30)
        self.assertEqual(got[0]["f0"], "rich0")

    def test_a_thin_array_exits_as_a_schema_change(self):
        payload = f'{{"models":{json.dumps([model(5, "thin")])}}}'

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.richest_models_array(payload)

        self.assertIn("schema changed", str(caught.exception))

    def test_an_identical_duplicate_record_is_collapsed(self):
        # AA has emitted one model twice in the same array, byte-identical.
        # Downstream keys on slug; a duplicate must not reach it.
        rec = model(25, "dup")
        rec["slug"] = "granite-4-1-8b"
        payload = f'{{"models":{json.dumps([rec, rec])}}}'

        got = fetch_aa.richest_models_array(payload)

        self.assertEqual(len(got), 1)

    def test_records_without_a_slug_are_never_collapsed_together(self):
        # Only a shared SLUG identifies a duplicate; two slug-less records
        # are two records.
        payload = f'{{"models":{json.dumps([model(25, "a"), model(25, "b")])}}}'

        self.assertEqual(len(fetch_aa.richest_models_array(payload)), 2)

    def test_unparseable_candidate_is_skipped_not_fatal(self):
        broken = '"models":[{"a":,}]'
        good = f'"models":{json.dumps([model(25, "good")])}'
        payload = "{" + broken + "," + good + "}"

        self.assertEqual(len(fetch_aa.richest_models_array(payload)[0]), 25)


def costed(name="M", *, total=1.0, evaluations=None):
    """A model carrying the cost breakdown build.py reads."""
    if evaluations is None:
        evaluations = [
            {"slug": "gdpval-aa", "weightedCostPerTask": total * 0.4},
            {"slug": "scicode", "weightedCostPerTask": total * 0.6},
        ]
    return {"name": name,
            "intelligenceIndexCostPerTask": {"cost": {"total": total},
                                             "evaluations": evaluations}}


class IndexVersionTests(unittest.TestCase):
    """Issue #220: the version string left the leaderboard payload, so the pin
    reads AA's methodology page. The contract has two halves: a genuinely
    bumped major.minor still refuses the capture (the v4.2 rebalance shipped
    well-formed data with wrong costs, which is the whole point of the pin),
    and an ABSENT version string proves nothing and must NOT fail."""

    def test_a_point_release_within_the_pinned_generation_passes(self):
        # AA ships point releases (v4.3.2) inside a generation without
        # rebalancing, so the pin compares at MAJOR.MINOR granularity -- and
        # the FULL found version is what the capture log reports.
        text = (f"Artificial Analysis Intelligence Index "
                f"v{fetch_aa.INDEX_VERSION}.2 incorporates 10 evaluations")

        self.assertEqual(fetch_aa.check_index_version(text),
                         f"{fetch_aa.INDEX_VERSION}.2")

    def test_a_historical_citation_alone_names_no_version(self):
        # The page's prose cites superseded generations WITHOUT the brand
        # prefix ("Superseded by Terminal-Bench 4.0 in Intelligence Index
        # v4.3"); only the full prefix identifies the live version, so such a
        # citation alone is absence -- and absence passes (contract b).
        stderr, stdout = io.StringIO(), io.StringIO()

        with contextlib.redirect_stderr(stderr), \
                contextlib.redirect_stdout(stdout):
            got = fetch_aa.check_index_version(
                "Superseded by Terminal-Bench 4.0 in Intelligence Index v4.3")

        self.assertIsNone(got)
        # The absence note reaches BOTH streams, and both are pinned: the
        # refresh's capture step tees only stdout into its log on a green
        # run (stderr is cat'd on the failure branch alone), so a stdout-
        # only note would leave the green hour silent about the pass.
        for stream in (stderr, stdout):
            self.assertIn("methodology", stream.getvalue())
            self.assertIn("proves nothing", stream.getvalue())

    def test_unrelated_text_passes_on_absence_with_a_note_on_both_streams(self):
        stderr, stdout = io.StringIO(), io.StringIO()

        with contextlib.redirect_stderr(stderr), \
                contextlib.redirect_stdout(stdout):
            got = fetch_aa.check_index_version("nothing here")

        self.assertIsNone(got)
        for stream in (stderr, stdout):
            self.assertIn("methodology", stream.getvalue())
            self.assertIn("proves nothing", stream.getvalue())

    def test_a_bumped_version_exits_naming_both_versions(self):
        # v4.2 rebalanced the weights without changing a single field name --
        # undetectable from the data, which is the whole reason for the pin.
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_index_version(
                "Artificial Analysis Intelligence Index v9.9")

        message = str(caught.exception)
        self.assertIn("v9.9", message)
        self.assertIn(f"v{fetch_aa.INDEX_VERSION}", message)
        self.assertIn("methodology", message)

    def test_a_multi_part_minor_bump_exits_against_the_string_compare(self):
        # "4.10" sorts below "4.3" as a plain string; the pin compares the
        # integer parts, so a v4.10 page refuses the v4.3 pin exactly like a
        # single-digit bump would.
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_index_version(
                "Artificial Analysis Intelligence Index v4.10")

        message = str(caught.exception)
        self.assertIn("v4.10", message)
        self.assertIn(f"v{fetch_aa.INDEX_VERSION}", message)

    def test_the_live_version_is_the_maximum_full_prefix_citation(self):
        # The page's prose can quote an older generation's full name verbatim;
        # the live version is the version-sorted MAXIMUM of every full-prefix
        # match, never the first.
        text = ("Earlier the Artificial Analysis Intelligence Index v4.1 ran "
                "three evals. Today the Artificial Analysis Intelligence "
                "Index v4.3.2 incorporates 10 evaluations")

        self.assertEqual(fetch_aa.check_index_version(text), "4.3.2")


class CostBreakdownTests(unittest.TestCase):
    def test_a_consistent_breakdown_passes_and_is_counted(self):
        models = [costed("A"), costed("B"), {"name": "unpriced"}]

        self.assertEqual(fetch_aa.check_cost_breakdown(models), (2, []))

    def test_a_dropped_breakdown_is_reported_and_is_not_an_error(self):
        # merge_captures leaves the leaderboard's bare number when the detail
        # route's breakdown is another generation's (issue #200). The validator
        # reads that as a dropped model and NAMES it -- it is a model whose
        # GDPval cost renders absent until the routes converge, which a count
        # alone would not say.
        models = [costed("A"),
                  {"slug": "b-dropped", "intelligenceIndexCostPerTask": 1.5}]

        priced, dropped = fetch_aa.check_cost_breakdown(models)

        self.assertEqual(priced, 1)
        self.assertEqual(dropped, ["b-dropped"])

    def test_a_capture_whose_every_breakdown_was_dropped_names_the_window(self):
        # The merge is holding the line through a cross-generation window: the
        # all-dropped state is REPORTED AND RETURNED, never refused -- during
        # a window the refresh publishes from the fresh route or leaves the
        # page as-is, and only a real schema change fails the capture (issue
        # #217). The report still names the models it is talking about and
        # still refuses to blame the schema for a window that closes on its
        # own.
        models = [{"slug": f"dropped-{i}", "intelligenceIndexCostPerTask": 1.5}
                  for i in range(3)]
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            priced, dropped = fetch_aa.check_cost_breakdown(models)

        self.assertEqual(priced, 0)
        self.assertEqual(dropped, ["dropped-0", "dropped-1", "dropped-2"])
        message = stdout.getvalue()
        self.assertIn("two generations", message)
        self.assertIn("dropped-0", message)
        self.assertNotIn("schema changed", message)

    def test_the_window_marker_is_written_on_a_window_and_cleared_after(self):
        # The capture step records the window state to a sidecar marker so
        # the build layer can tell a window hour from a broken capture (issue
        # #217). Window on: the file appears with ONE human-readable line.
        # Window off: the file goes, so a stale marker can never outlive its
        # hour. Clearing when it is already absent is not an error -- that is
        # the common hour, and the schema sys.exit paths run BEFORE any
        # record call, so a schema-broken run never leaves a marker. Since
        # #223 the line also carries the observed in-run generation count
        # when the caller supplies one -- the build layer's refusal reads
        # that integer, so a window hour that empties an axis beyond the
        # #217 exemption names the window instead of blaming a shape change.
        with tempfile.TemporaryDirectory() as tmp:
            marker = pathlib.Path(tmp) / "cost-breakdown-window.txt"

            fetch_aa.record_cost_window(
                0, ["dropped-0", "dropped-1"], marker, generations=3)
            note = marker.read_text(encoding="utf-8")
            self.assertIn("every cost breakdown dropped", note)
            self.assertIn("dropped-0", note)
            self.assertIn("; 3 generation(s) observed in-run", note)
            self.assertEqual(len(note.splitlines()), 1)

            fetch_aa.record_cost_window(0, ["dropped-2"], marker)
            self.assertNotIn(
                "generation(s) observed in-run",
                marker.read_text(encoding="utf-8"),
                "a countless hour must not inherit the previous one's count")

            fetch_aa.record_cost_window(2, ["dropped-3"], marker)
            self.assertFalse(marker.exists(), "stale marker outlived its hour")

            fetch_aa.record_cost_window(2, [], marker)
            self.assertFalse(marker.exists())

    def test_a_dropped_slug_exits_before_the_chart_can_empty(self):
        # Exactly what v4.3 did to terminalbench-v2-1 and tau3-banking.
        models = [costed(evaluations=[{"slug": "scicode", "weightedCostPerTask": 1.0}])]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown(models)

        self.assertIn("gdpval-aa", str(caught.exception))

    def test_components_that_stop_summing_to_the_total_exit(self):
        # build.py divides an index weight back out of these; that is only
        # valid while the parts still make up the published whole.
        models = [costed(total=1.0, evaluations=[
            {"slug": "gdpval-aa", "weightedCostPerTask": 0.1},
            {"slug": "scicode", "weightedCostPerTask": 0.1},
        ])]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown(models)

        self.assertIn("sum to", str(caught.exception))

    def test_a_capture_with_no_priced_model_at_all_exits(self):
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown([{"name": "unpriced"}])

        self.assertIn("schema changed", str(caught.exception))

    def test_the_guard_names_the_model_by_slug_not_by_a_droppable_field(self):
        # These messages fire exactly when AA's schema moved, and `name` is a
        # field it has already deleted once -- which reduced a real diagnostic
        # to "None: cost breakdown lost its evaluations".
        models = [{"slug": "a-model",
                   "intelligenceIndexCostPerTask": {"evaluations": []}}]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown(models)

        self.assertIn("a-model", str(caught.exception))
        self.assertNotIn("None", str(caught.exception))

    def test_a_model_with_no_identifier_at_all_still_reads_as_a_message(self):
        models = [{"intelligenceIndexCostPerTask": {"evaluations": []}}]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown(models)

        self.assertIn("unidentifiable", str(caught.exception))

    def test_a_breakdown_missing_its_total_exits(self):
        models = [{"name": "M", "intelligenceIndexCostPerTask": {"evaluations": []}}]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown(models)

        self.assertIn("schema changed", str(caught.exception))


class WindowMarkerSpanTests(unittest.TestCase):
    """The marker filename is a three-leg contract, and each leg has a test
    on its own side -- but nothing held the legs together. The producer
    writes under fetch_aa.COST_WINDOW_MARKER, the build layer's reader
    accepts that name by its own literal, and the deny-by-default .gitignore
    must carry the negation for the same name or the marker is invisible to
    git. One span test: a rename on any leg fails here instead of silently
    orphaning the other two (review finding, issue #217).
    """

    def test_producer_consumer_and_gitignore_share_one_marker_name(self):
        # Passes as written against the shipped code -- the pin exists so a
        # future rename on any leg fails, not to drive a change.
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp)

            fetch_aa.record_cost_window(
                0, ["x"], data_dir / fetch_aa.COST_WINDOW_MARKER.name)

            self.assertTrue(build.cost_breakdown_window(data_dir))

        gitignore = (pathlib.Path(fetch_aa.ROOT) / ".gitignore").read_text(
            encoding="utf-8")
        self.assertIn(f"!/data/{fetch_aa.COST_WINDOW_MARKER.name}", gitignore)

    def test_the_generation_count_round_trips_from_producer_to_reader(self):
        # Issue #223's second contract leg: the integer record_cost_window
        # writes into the marker is the integer build.py's refusal reads.
        # The name was already pinned leg-by-leg above; this pins the
        # FORMAT -- a producer rename or reformat must fail here, not as a
        # "generation count not recorded" refusal on the next window hour.
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp)

            fetch_aa.record_cost_window(
                0, ["x"], data_dir / fetch_aa.COST_WINDOW_MARKER.name,
                generations=3)
            self.assertEqual(build.window_generations(data_dir), 3)

            fetch_aa.record_cost_window(
                0, ["y"], data_dir / fetch_aa.COST_WINDOW_MARKER.name)
            self.assertIsNone(build.window_generations(data_dir))


def agent_row(label: str, score: float | None = 0.64,
              cost: float | None = 1.5) -> dict:
    row: dict = {"id": label, "displayLabel": label,
                 "agentName": label.split(" - ")[0]}
    if score is not None:
        row["indexScore"] = score
    row["mean"] = {} if cost is None else {"costUsd": cost}
    return row


def agent_payload(rows: list[dict], key: str = "rows") -> str:
    """The coding-agents flight payload interleaves RSC marker strings with the
    row objects, exactly as the extractor must tolerate."""
    # Next.js emits the payload compact; the extractor anchors on that shape.
    body = json.dumps(rows, separators=(",", ":"))[1:-1]
    return '{"' + key + '":[' + body + ',"$L1c"]}'


class CodingAgentRowsTests(unittest.TestCase):
    def test_extracts_rows_carrying_a_paired_score_and_cost(self):
        rows = [agent_row(f"Agent - Model {i}") for i in range(25)]

        got = fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertEqual(len(got), 25)
        self.assertEqual(got[0]["indexScore"], 0.64)
        self.assertEqual(got[0]["mean"]["costUsd"], 1.5)

    def test_marker_strings_between_rows_are_skipped(self):
        # RSC splices "$L1c"-style references into the same array.
        payload = fetch_aa.coding_agent_rows(
            agent_payload([agent_row(f"A - {i}") for i in range(21)]))

        self.assertTrue(all(isinstance(r, dict) for r in payload))

    def test_rows_are_collected_from_every_array_not_just_the_biggest(self):
        # AA splits the set across `rows` (its highlighted selection) and
        # `benchmarkRows` (the remainder). Taking only the largest array
        # published 10 of 13 rows silently -- and the dropped ones included the
        # cheapest run on the chart, which is a frontier point.
        highlighted = agent_payload([agent_row(f"H - {i}") for i in range(10)])
        rest = agent_payload([agent_row(f"R - {i}") for i in range(3)],
                             key="benchmarkRows")

        got = fetch_aa.coding_agent_rows(highlighted + rest)

        self.assertEqual(len(got), 13)

    def test_an_array_starting_with_a_back_reference_is_not_skipped(self):
        # `benchmarkRows` begins with an RSC back-reference STRING pointing at
        # a row in the other array, so the array does not start with an object.
        rows = [agent_row(f"A - {i}") for i in range(13)]
        body = json.dumps(rows, separators=(",", ":"))[1:-1]
        payload = ('{"benchmarkRows":["$d:props:children:1:props:rows:0",'
                   + body + ']}')

        self.assertEqual(len(fetch_aa.coding_agent_rows(payload)), 13)

    def test_a_row_reachable_twice_is_counted_once(self):
        rows = [agent_row(f"A - {i}") for i in range(13)]
        doubled = agent_payload(rows) + agent_payload(rows, key="benchmarkRows")

        self.assertEqual(len(fetch_aa.coding_agent_rows(doubled)), 13)

    def test_overlapping_arrays_union_rather_than_replace(self):
        # The page has embedded the highlighted rows AND a fuller set at once.
        # Neither may win outright: the union is the chart.
        highlights = agent_payload([agent_row(f"H - {i}") for i in range(10)])
        full = agent_payload([agent_row(f"F - {i}") for i in range(58)])

        got = fetch_aa.coding_agent_rows(highlights + full)

        self.assertEqual(len(got), 68)

    def test_rows_without_a_cost_do_not_count_toward_the_floor(self):
        rows = [agent_row(f"A - {i}", cost=None) for i in range(58)]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertIn("schema changed", str(caught.exception))

    def test_a_collapsed_table_exits_rather_than_publishing_a_stub(self):
        rows = [agent_row(f"A - {i}") for i in range(fetch_aa.CODING_ROW_FLOOR - 1)]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertIn("schema changed", str(caught.exception))

    def test_the_highlighted_selection_alone_is_enough(self):
        # AA no longer server-renders the full table, only its highlighted
        # rows. That selection is the chart now, so it must not trip the floor.
        rows = [agent_row(f"A - {i}") for i in range(10)]

        self.assertEqual(len(fetch_aa.coding_agent_rows(agent_payload(rows))), 10)


class MergeCapturesTests(unittest.TestCase):
    def test_detail_only_fields_fill_gaps_without_touching_the_leaderboard(self):
        base = [{"slug": "a", "intelligenceIndex": 50, "modelCreatorName": "Lab"}]
        detail = [{"slug": "a", "intelligenceIndex": 50, "name": "A (high)",
                   "parameters": 27}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertEqual(got[0]["name"], "A (high)")
        self.assertEqual(got[0]["parameters"], 27)
        self.assertEqual(got[0]["modelCreatorName"], "Lab")

    def test_a_nested_stub_does_not_shadow_the_complete_breakdown(self):
        # The shape AA shipped before it flattened the cost to a bare number:
        # the leaderboard kept intelligenceIndexCostPerTask.cost and dropped
        # .evaluations. A key-level merge leaves the stub in place and the
        # GDPval axis silently loses its cost. The breakdown here sums to the
        # leaderboard's total, which is what AA publishes -- so it survives
        # this arm's sum check as well as the one-level-deep fill.
        base = [{"slug": "a",
                 "intelligenceIndexCostPerTask": {"cost": {"total": 1.0}}}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
            "cost": {"total": 1.0},
            "evaluations": [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4},
                            {"slug": "scicode", "weightedCostPerTask": 0.6}]}}]

        got = fetch_aa.merge_captures(base, detail)

        cost = got[0]["intelligenceIndexCostPerTask"]
        self.assertEqual(cost["cost"]["total"], 1.0)
        self.assertEqual(
            [e["slug"] for e in cost["evaluations"]], ["gdpval-aa", "scicode"])

    def test_a_nested_stub_whose_breakdown_will_not_sum_is_dropped_too(self):
        # The same shape, where the detail breakdown does NOT decompose the
        # leaderboard's total (0.85 against 1.0). This arm carried no sum check
        # at all, so a cross-generation breakdown decomposing someone else's
        # total shipped unnoticed -- the flattened-scalar arm's guard is
        # hoisted so both arms share it. The leaderboard's own number is what
        # is left, and the GDPval axis reads absent rather than lying.
        base = [{"slug": "a",
                 "intelligenceIndexCostPerTask": {"cost": {"total": 1.0}}}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
            "cost": {"total": 1.0},
            "evaluations": [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4},
                            {"slug": "scicode", "weightedCostPerTask": 0.45}]}}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertEqual(got[0]["intelligenceIndexCostPerTask"], 1.0)

    def test_an_unpriced_leaderboard_value_is_never_promoted_to_a_price(self):
        # AA writes "$undefined" for a model it did not price, and null for
        # one it has no cost for; the detail route describes such a model too,
        # sometimes with a total from an older generation. Neither is a total
        # to reshape -- both are a published "no cost" -- so taking the detail
        # object there would promote a stale price for a model the fresh route
        # says is unpriced, which is exactly what this precedence prevents.
        # The field stays as the leaderboard published it and renders absent.
        for unpriced in ("$undefined", None):
            with self.subTest(unpriced=unpriced):
                base = [{"slug": "a", "intelligenceIndexCostPerTask": unpriced}]
                detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
                    "cost": {"total": 1.0},
                    "evaluations": [
                        {"slug": "gdpval-aa", "weightedCostPerTask": 0.4},
                        {"slug": "scicode", "weightedCostPerTask": 0.6}]}}]

                got = fetch_aa.merge_captures(base, detail)

                self.assertEqual(
                    got[0]["intelligenceIndexCostPerTask"], unpriced)
                # And the cost axis reads it as absent rather than raising.
                self.assertIsNone(build.cost_per_task(got[0]))

    def test_a_flattened_scalar_wins_and_the_breakdown_hangs_under_it(self):
        # AA flattened the leaderboard's intelligenceIndexCostPerTask to its
        # bare total while the detail route kept the object with the
        # per-evaluation breakdown. Same key, different shapes -- and the
        # leaderboard's number WINS: it is the fresh generation's measured
        # total, and it is the value the cost axis plots. The object is taken
        # whole as a fill with its cost.total replaced by that number, so the
        # breakdown decomposes exactly the total it is hung under. Here the
        # detail object publishes 1.2 and the leaderboard 1.5, so the total
        # that lands proves which side won.
        base = [{"slug": "a", "intelligenceIndexCostPerTask": 1.5}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
            "cost": {"total": 1.2},
            "evaluations": [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4},
                            {"slug": "scicode", "weightedCostPerTask": 1.1}]}}]

        got = fetch_aa.merge_captures(base, detail)

        cost = got[0]["intelligenceIndexCostPerTask"]
        self.assertEqual(cost["cost"]["total"], 1.5)
        self.assertEqual(len(cost["evaluations"]), 2)

    def test_a_breakdown_that_will_not_sum_to_the_leaderboards_total_is_dropped(self):
        # The same shape-split pair, where the detail route's breakdown does
        # NOT sum to the leaderboard's number (0.85 against 1.5). It is not
        # this total's breakdown, whatever route it came from, so it is
        # dropped whole and the plain scalar stays: the GDPval axis reads
        # absent for this model rather than decomposing someone else's total.
        base = [{"slug": "a", "intelligenceIndexCostPerTask": 1.5}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
            "cost": {"total": 1.5},
            "evaluations": [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4},
                            {"slug": "scicode", "weightedCostPerTask": 0.45}]}}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertEqual(got[0]["intelligenceIndexCostPerTask"], 1.5)

    def test_a_detail_value_never_overrides_a_leaderboard_field(self):
        # The whole contract (issue #200): wherever BOTH routes carry a field
        # with different values -- two generations of AA's data mixed into one
        # capture is what made the page oscillate -- the detail route's value
        # simply loses, while a field only it ships still fills.
        base = [{"slug": "a", "intelligenceIndex": 51, "name": "Fresh",
                 "modelCreatorName": "Lab"}]
        detail = [{"slug": "a", "intelligenceIndex": 52, "name": "Stale",
                   "modelCreatorName": "Other Lab", "parameters": 27}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertEqual(got[0]["intelligenceIndex"], 51)
        self.assertEqual(got[0]["name"], "Fresh")
        self.assertEqual(got[0]["modelCreatorName"], "Lab")
        self.assertEqual(got[0]["parameters"], 27)

    def test_a_scalar_never_overwrites_a_structured_value(self):
        # The reverse direction: the leaderboard's object must not be
        # replaced by a detail-route scalar, should the shapes ever swap.
        base = [{"slug": "a", "intelligenceIndexCostPerTask": {"cost": {"total": 1.5}}}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": 1.5}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertIsInstance(got[0]["intelligenceIndexCostPerTask"], dict)

    def test_a_model_absent_from_the_detail_route_is_kept_as_is(self):
        # A detail page lists every model EXCEPT its own, so exactly one model
        # never gets widened. Dropping it would silently shrink the corpus.
        base = [{"slug": "host", "intelligenceIndex": 10}]

        self.assertEqual(fetch_aa.merge_captures(base, []), base)


class DetailHostSlugTests(unittest.TestCase):
    def test_picks_an_unpriced_model_so_the_exclusion_costs_nothing(self):
        models = [
            {"slug": "priced", "intelligenceIndexCostPerTask": {"cost": {"total": 1.0}}},
            {"slug": "free"},
        ]

        self.assertEqual(fetch_aa.detail_host_slug(models), "free")

    def test_the_choice_is_deterministic_so_captures_do_not_churn(self):
        models = [{"slug": s} for s in ("zeta", "alpha", "mid")]

        self.assertEqual(fetch_aa.detail_host_slug(models), "alpha")

    def test_a_bare_numeric_cost_counts_as_priced(self):
        # The leaderboard's flattened shape. Treating it as unpriced would
        # make a costed model the detail host and strip its breakdown.
        models = [{"slug": "priced", "intelligenceIndexCostPerTask": 1.5},
                  {"slug": "free"}]

        self.assertEqual(fetch_aa.detail_host_slug(models), "free")

    def test_an_undefined_cost_string_counts_as_unpriced(self):
        # AA writes absent fields as the string "$undefined".
        models = [{"slug": "a", "intelligenceIndexCostPerTask": "$undefined"}]

        self.assertEqual(fetch_aa.detail_host_slug(models), "a")

    def test_no_free_host_exits_rather_than_silently_dropping_a_model(self):
        models = [{"slug": "a",
                   "intelligenceIndexCostPerTask": {"cost": {"total": 1.0}}}]

        with self.assertRaises(SystemExit):
            fetch_aa.detail_host_slug(models)


class FetchHtmlTests(unittest.TestCase):
    def test_cached_file_is_read_instead_of_the_network(self):
        # --html is how you re-extract without hitting AA again. The cache is
        # the page text and nothing else: fetch_html hands back the string
        # the extractor parses, per route.
        path = pathlib.Path(__file__).resolve().parent / "_cached.html"
        path.write_text("<html>cached</html>", encoding="utf-8")
        try:
            self.assertEqual(fetch_aa.fetch_html(str(path)),
                             "<html>cached</html>")
            # The other two routes read their own cache through the same
            # helper, which the URL argument only names.
            self.assertEqual(
                fetch_aa.fetch_html(str(path), fetch_aa.AGENTS_URL),
                "<html>cached</html>")
        finally:
            path.unlink()


def leaderboard_record(**overrides: object) -> dict:
    """fixture-model as the leaderboard route carries it: the flattened cost
    total plus the filler fields AA still ships there. The filler is
    identical on both routes -- only a deliberate delta may make a shared
    field differ, and the leaderboard's copy is then the one that lands."""
    return {**model(21, "shared"), "slug": "fixture-model",
            "intelligenceIndex": 51, "intelligenceIndexCostPerTask": 0.75,
            **overrides}


def detail_record(**overrides: object) -> dict:
    """fixture-model as the model-detail route carries it: the full cost
    object with its per-evaluation breakdown, plus the same filler fields."""
    return {**model(21, "shared"), "slug": "fixture-model",
            "intelligenceIndex": 51,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": 0.75},
                "evaluations": [
                    {"slug": "gdpval-aa", "weightedCostPerTask": 0.30},
                    {"slug": "scicode", "weightedCostPerTask": 0.45},
                ]},
            **overrides}


def leaderboard_payload() -> str:
    """A leaderboard flight payload: the pinned index version and the model
    array, one unpriced detail host plus the shared model. Compact JSON --
    the extractor anchors on that shape."""
    host = {"slug": "detail-host-model",
            "intelligenceIndexCostPerTask": "$undefined"}
    return json.dumps({
        "intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
        "models": [host, leaderboard_record()],
    }, separators=(",", ":"))


def detail_payload(**record_overrides: object) -> str:
    return json.dumps({"models": [detail_record(**record_overrides)]},
                      separators=(",", ":"))


def methodology_html(version: str | None = fetch_aa.INDEX_VERSION) -> str:
    """The methodology page as a plain HTML document -- no flight wrapper,
    the version pin reads the page text directly (issue #220). The default
    version is exactly the pin, so fixtures that expect a pass need no
    argument; None writes a page that names no index version at all."""
    if version is None:
        return ("<html><body>The methodology page describes the benchmark "
                "suite.</body></html>")
    return (f"<html><body><h1>Artificial Analysis Intelligence Index "
            f"v{version}</h1><p>incorporates 10 evaluations</p></body>"
            "</html>")


class CaptureGapFillWiringTests(unittest.TestCase):
    """Issue #200: capture() reads both routes and merges them under one rule.

    The detail route is a GAP FILL: it supplies the fields the leaderboard
    does not ship and loses every field the leaderboard does carry. The merge
    rule lives in build.merge_captures (pinned there), but only the capture
    function is what CALLS it with a detail host computed from THIS
    leaderboard's own rows -- a call site no unit test observes, which is
    exactly the gap a refactor could delete silently. These pins drive
    fetch_aa.capture() over two cached pages: the returned Capture names the
    host it widened from and the index version the costs belong to, and the
    merged corpus carries the leaderboard's value wherever the two routes
    differ.
    """

    @contextlib.contextmanager
    def cached_routes(self, **record_overrides: object):
        """Three cached pages for capture(cached_base, cached_detail,
        cached_methodology) to read. The dispute-look spacing wait (issue
        #208) is real in production and stubbed at the seam like every other
        wait."""
        with tempfile.TemporaryDirectory(prefix=".issue-200-gapfill-") as tmp:
            root = pathlib.Path(tmp)
            base = root / "leaderboard.html"
            detail = root / "detail.html"
            methodology = root / "methodology.html"
            base.write_text(flight_html(leaderboard_payload()), encoding="utf-8")
            detail.write_text(flight_html(detail_payload(**record_overrides)),
                              encoding="utf-8")
            methodology.write_text(methodology_html(), encoding="utf-8")
            with unittest.mock.patch.object(fetch_aa, "_sleep",
                                            side_effect=lambda s: None):
                yield str(base), str(detail), str(methodology)

    def test_capture_names_the_host_it_widened_from_and_the_index_version(self):
        # detail_host_slug is computed from THIS leaderboard's rows: the
        # detail page is chosen for what its page excludes, so the corpus
        # must never be paired with a host picked from a different read.
        # capture() pins the version from the methodology page BEFORE the
        # leaderboard fetches, so a bumped index fails the capture without
        # spending the other page reads (issue #220).
        with self.cached_routes() as (base, detail, methodology):
            captured = fetch_aa.capture(base, detail, methodology)

        self.assertEqual(captured.host, "detail-host-model")
        self.assertEqual(captured.version, fetch_aa.INDEX_VERSION)
        self.assertEqual([m["slug"] for m in captured.models],
                         ["detail-host-model", "fixture-model"])

    def test_a_divergent_detail_value_never_reaches_the_captured_corpus(self):
        # The end of the old agreement machinery: the two routes disagreeing
        # is no longer a state to detect or resolve, it is simply a detail
        # value that loses. The capture lands, and the leaderboard's 51 is
        # what build.py reads.
        with self.cached_routes(intelligenceIndex=52) as (base, detail,
                                                          methodology):
            captured = fetch_aa.capture(base, detail, methodology)

        by_slug = {m["slug"]: m for m in captured.models}
        self.assertEqual(by_slug["fixture-model"]["intelligenceIndex"], 51)

    def test_the_capture_log_names_the_host_and_the_filling_rule(self):
        # The capture log is where an operator reads which page filled the
        # gaps, and it states the rule the capture ran under.
        with tempfile.TemporaryDirectory(prefix=".issue-200-log-") as tmp:
            root = pathlib.Path(tmp)
            pages = [root / name for name in
                     ("leaderboard.html", "detail.html", "agents.html",
                      "methodology.html")]
            payloads = (leaderboard_payload(), detail_payload(),
                        agent_payload([agent_row(f"Agent - Model {i}")
                                       for i in range(5)]))
            for path, payload in zip(pages, payloads):
                path.write_text(flight_html(payload), encoding="utf-8")
            # The methodology page is plain HTML -- the pin reads the page
            # text directly, no flight wrapper (issue #220).
            pages[3].write_text(methodology_html(), encoding="utf-8")
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                sys.argv = ["fetch_aa.py", "--html", str(pages[0]),
                            "--detail-html", str(pages[1]),
                            "--agents-html", str(pages[2]),
                            "--methodology-html", str(pages[3])]
                buffer = io.StringIO()
                # The dispute-look spacing wait (issue #208) is real in
                # production and stubbed at the seam like every other wait.
                with contextlib.redirect_stdout(buffer), \
                        unittest.mock.patch.object(fetch_aa, "_sleep",
                                                   side_effect=lambda s: None):
                    fetch_aa.main()
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

        stdout = buffer.getvalue()
        self.assertIn("/models/detail-host-model", stdout)
        self.assertIn("the leaderboard's own value wins wherever both routes "
                      "carry the field", stdout)
        self.assertIn(f"v{fetch_aa.INDEX_VERSION} cost breakdown", stdout)
        # Issue #208: the run's one-line generation summary, quiet shape.
        self.assertIn("1 generation(s) observed in-run; 0 models carry "
                      "disputed values", stdout)

    def test_the_capture_log_stays_honest_when_the_page_names_no_version(self):
        # Contract b, end to end: a methodology page with no version string
        # does not fail the run, and the success line does not interpolate a
        # version where none was found -- no "vNone", and the absence is
        # named for the operator who reads the log.
        with tempfile.TemporaryDirectory(prefix=".issue-220-log-") as tmp:
            root = pathlib.Path(tmp)
            pages = [root / name for name in
                     ("leaderboard.html", "detail.html", "agents.html",
                      "methodology.html")]
            payloads = (leaderboard_payload(), detail_payload(),
                        agent_payload([agent_row(f"Agent - Model {i}")
                                       for i in range(5)]))
            for path, payload in zip(pages, payloads):
                path.write_text(flight_html(payload), encoding="utf-8")
            pages[3].write_text(methodology_html(None), encoding="utf-8")
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            stderr = io.StringIO()
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                sys.argv = ["fetch_aa.py", "--html", str(pages[0]),
                            "--detail-html", str(pages[1]),
                            "--agents-html", str(pages[2]),
                            "--methodology-html", str(pages[3])]
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer), \
                        contextlib.redirect_stderr(stderr), \
                        unittest.mock.patch.object(fetch_aa, "_sleep",
                                                   side_effect=lambda s: None):
                    fetch_aa.main()
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

        stdout = buffer.getvalue()
        self.assertIn("wrote aa-raw-models.json", stdout)
        self.assertNotIn("vNone", stdout)
        self.assertIn("whose index version the methodology page did not "
                      "name", stdout)
        self.assertIn("proves nothing", stderr.getvalue())


class AtomicCaptureWritesTests(unittest.TestCase):
    """Issue #66: capture writes must not leave a half-written capture.

    fetch_aa.py wrote the captures with a bare write_text: a crash mid-write
    (ENOSPC, a killed runner) left a truncated file where the previous good
    capture -- the one the page builds from, committed and trusted -- used
    to be. write_atomic stages the text in a temp file in the destination's
    own directory and os.replace()s it into place, so the swap is atomic and
    the previous capture survives every failure. The failure is injected at
    the write boundary itself (os.replace raising), and the observable is
    the pre-existing capture on disk staying byte-identical.
    """

    @contextlib.contextmanager
    def capture_over_existing(self, replace_raiser=None):
        """fetch_aa.main() over cached pages, with previous captures already
        on disk. Yields (root, run) -- call run() inside the block; it
        returns the capture's stdout."""
        with tempfile.TemporaryDirectory(prefix=".issue-66-atomic-") as tmp:
            root = pathlib.Path(tmp)
            pages = [root / name for name in
                     ("leaderboard.html", "detail.html", "agents.html",
                      "methodology.html")]
            payloads = (leaderboard_payload(), detail_payload(),
                        agent_payload([agent_row(f"Agent - Model {i}")
                                       for i in range(5)]))
            for path, payload in zip(pages, payloads):
                path.write_text(flight_html(payload), encoding="utf-8")
            # The methodology page is plain HTML, no flight wrapper (issue
            # #220), and it must be cached for these tests: with every page
            # flag passed, no test here can reach the real network.
            pages[3].write_text(methodology_html(), encoding="utf-8")
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            patcher = None
            if replace_raiser is not None:
                # The real os module: the boundary the fix writes through,
                # patched where it lives rather than through fetch_aa's
                # attribute, so the pin cannot be defeated by an import
                # reshuffle.
                patcher = unittest.mock.patch.object(
                    os, "replace", side_effect=replace_raiser)
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                # The previous capture, as a crashed run would have left it.
                fetch_aa.OUT.write_bytes(b"PREVIOUS MODELS CAPTURE")
                fetch_aa.AGENTS_OUT.write_bytes(b"PREVIOUS AGENTS CAPTURE")
                fetch_aa.STAMP.write_text("2020-01-01\n", encoding="utf-8")
                sys.argv = ["fetch_aa.py", "--html", str(pages[0]),
                            "--detail-html", str(pages[1]),
                            "--agents-html", str(pages[2]),
                            "--methodology-html", str(pages[3])]
                if patcher is not None:
                    patcher.start()

                def run() -> str:
                    buffer = io.StringIO()
                    # The dispute-look spacing wait (issue #208) is real in
                    # production and stubbed at the seam like every other
                    # wait; a recorder here would only restate that the
                    # healthy path waits once.
                    with contextlib.redirect_stdout(buffer), \
                            unittest.mock.patch.object(
                                fetch_aa, "_sleep",
                                side_effect=lambda s: None):
                        fetch_aa.main()
                    return buffer.getvalue()

                yield root, run
            finally:
                if patcher is not None:
                    patcher.stop()
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def test_a_failed_replace_leaves_the_previous_capture_byte_identical(self):
        # The write boundary fails after the staging file is written: the
        # previous captures on disk must be untouched, and no staging litter
        # may remain.
        def disk_full(staged, dest):
            raise OSError(28, "No space left on device")

        with self.capture_over_existing(disk_full) as (root, run):
            with self.assertRaises(OSError):
                run()

            self.assertEqual(
                (root / "aa-raw-models.json").read_bytes(),
                b"PREVIOUS MODELS CAPTURE")
            self.assertEqual(
                (root / "aa-raw-coding-agents.json").read_bytes(),
                b"PREVIOUS AGENTS CAPTURE")
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                "2020-01-01\n",
                "the stamp moved even though the capture did not land")
            self.assertEqual(
                [p.name for p in root.iterdir() if p.name.endswith(".tmp")], [],
                "a failed write left staging litter behind")

    def test_a_failed_second_replace_leaves_the_agents_capture_byte_identical(self):
        # The mirror limb: an injector that raises on EVERY replace dies at
        # the first write_atomic (OUT) and never reaches the AGENTS_OUT
        # boundary, so a one-site revert of that write to a bare write_text
        # would survive the suite. This injector lets replace #1 (OUT) land
        # and raises on #2, holding each capture's failure limb to its own
        # control.
        real_replace = os.replace
        seen = []

        def fail_on_second(staged, dest):
            seen.append(dest)
            if len(seen) == 2:
                raise OSError(28, "No space left on device")
            return real_replace(staged, dest)

        with self.capture_over_existing(fail_on_second) as (root, run):
            with self.assertRaises(OSError):
                run()

            self.assertEqual(
                seen,
                [root / "aa-raw-models.json", root / "aa-raw-coding-agents.json"],
                "the fault did not land on the AGENTS_OUT boundary")
            # OUT's own boundary already succeeded, so ITS capture landed:
            self.assertEqual(
                [m["slug"] for m in json.loads(
                    (root / "aa-raw-models.json").read_text(encoding="utf-8"))],
                ["detail-host-model", "fixture-model"])
            # ...while the failed AGENTS_OUT boundary leaves the previous
            # capture byte-intact, the stamp unmoved and no litter behind.
            self.assertEqual(
                (root / "aa-raw-coding-agents.json").read_bytes(),
                b"PREVIOUS AGENTS CAPTURE")
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                "2020-01-01\n",
                "the stamp moved even though the agents capture did not land")
            self.assertEqual(
                [p.name for p in root.iterdir() if p.name.endswith(".tmp")], [],
                "a failed write left staging litter behind")

    def test_a_healthy_capture_replaces_both_files_and_lands_no_litter(self):
        with self.capture_over_existing() as (root, run):
            stdout = run()

            self.assertIn("wrote aa-raw-models.json", stdout)
            models = json.loads(
                (root / "aa-raw-models.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [m["slug"] for m in models],
                ["detail-host-model", "fixture-model"])
            self.assertEqual(
                len(json.loads(
                    (root / "aa-raw-coding-agents.json").read_text(encoding="utf-8"))),
                5)
            self.assertEqual(
                [p.name for p in root.iterdir() if p.name.endswith(".tmp")], [],
                "a healthy capture left staging files behind")
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                datetime.date.today().isoformat() + "\n")


class _FakeResponse:
    """The urlopen context-manager result, for a modeled healthy page."""

    def __init__(self, body: str):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body.encode("utf-8")


class LoudUrlopenStub:
    """Stand-in for urllib.request.urlopen that models only what a test
    wires. Every other URL fails LOUDLY -- an AssertionError, not an empty
    response -- so a test cannot pass by accident against an unmodeled
    boundary, and a wiring mistake cannot reach the real network."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, request, timeout=None):
        url = (request.full_url if isinstance(request, urllib.request.Request)
               else str(request))
        self.calls.append(url)
        handler = self.routes.get(url)
        if handler is None:
            raise AssertionError(f"urlopen stub: unmodeled call to {url}")
        return handler()


class TransportErrorTests(unittest.TestCase):
    """Issue #66: raw transport errors must exit guarded, not as tracebacks.

    fetch_html let URLError, HTTPError and socket.timeout escape raw: the
    hourly refresh logged a traceback and the workflow page showed the
    stack, instead of the one actionable line every schema-change refusal
    produces. The boundary itself -- urllib.request.urlopen -- is stubbed
    here, never an internal function, and the stub refuses unmodeled URLs
    so no test can reach the real network.
    """

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")

    def run_capture_through_boundary(self, routes: dict):
        """fetch_aa.main() over the stubbed urlopen, no cache flags: every
        page comes through the stub. -> (stub, SystemExit-free stdout)."""
        stub = LoudUrlopenStub(routes)
        with tempfile.TemporaryDirectory(prefix=".issue-66-transport-") as tmp:
            root = pathlib.Path(tmp)
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                sys.argv = ["fetch_aa.py"]
                with unittest.mock.patch.object(
                        urllib.request, "urlopen", stub), \
                        unittest.mock.patch.object(
                            fetch_aa, "_sleep",
                            side_effect=lambda s: None):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        fetch_aa.main()
                    return stub, buffer.getvalue()
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def healthy_routes(self) -> dict:
        agents = flight_html(agent_payload(
            [agent_row(f"Agent - Model {i}") for i in range(5)]))
        return {
            fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(methodology_html()),
            fetch_aa.URL: lambda: _FakeResponse(flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(agents),
        }

    def test_a_healthy_fetch_still_succeeds_through_the_boundary(self):
        # The control: the wrap must catch transport failures only, and the
        # healthy capture runs all four modeled pages through the real
        # urlopen call shape (methodology, leaderboard, detail, agents) to
        # its writes.
        stub, stdout = self.run_capture_through_boundary(self.healthy_routes())

        # Issue #208: the leaderboard route is read TWICE (the dispute
        # looks), so the healthy capture is five pages in this order -- the
        # methodology version pin FIRST (issue #220: fail fast before
        # spending the other fetches), the first look, the detail page, the
        # spaced second look, the coding agents.
        self.assertEqual(stub.calls,
                         [fetch_aa.METHODOLOGY_URL, fetch_aa.URL,
                          self.DETAIL_URL, fetch_aa.URL,
                          fetch_aa.AGENTS_URL])
        self.assertIn("wrote aa-raw-models.json", stdout)

    def test_transport_failures_exit_as_a_guarded_refusal(self):
        # URLError covers DNS/connect failures, HTTPError (its subclass)
        # refused status codes, socket.timeout (an OSError) a dead read --
        # each becomes the same clean exit shape the schema guards use,
        # naming the URL and carrying the underlying reason. Every raiser
        # here is retryable, so the refusal names the exhaustion (issue
        # #154) rather than pretending attempt 1 was final.
        raisers = (
            ("URLError", urllib.error.URLError("Connection refused")),
            ("HTTPError", urllib.error.HTTPError(
                fetch_aa.URL, 503, "Service Unavailable",
                email.message.Message(), None)),
            ("timeout", socket.timeout("The read operation timed out")),
        )
        for why, error in raisers:
            with self.subTest(why=why):
                def raiser(e=error):
                    raise e

                # The methodology pin passes (fail fast lives BEFORE the
                # leaderboard only when the page itself is healthy), then the
                # leaderboard fetch exercises the transport failure.
                with self.assertRaises(SystemExit) as caught:
                    self.run_capture_through_boundary({
                        fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(
                            methodology_html()),
                        fetch_aa.URL: raiser})

                message = str(caught.exception)
                self.assertIn(fetch_aa.URL, message)
                self.assertIn("fetch failed", message)
                self.assertIn(str(error), message)
                self.assertIn(
                    f"after {fetch_aa.PAGE_ATTEMPTS} attempts", message)

    def test_the_guarded_refusal_is_the_whole_of_stderr_at_exit_one(self):
        # End to end: a subprocess whose urlopen is stubbed before fetch_aa
        # loads. The observable is the process's -- exit 1, the actionable
        # line LAST on stderr after the page-retry lines (issue #154), and
        # no traceback anywhere.
        with tempfile.TemporaryDirectory(prefix=".issue-66-subproc-") as tmp:
            runner = pathlib.Path(tmp) / "runner.py"
            runner.write_text(
                "import sys, urllib.request, urllib.error\n"
                "sys.path.insert(0, " +
                repr(str(pathlib.Path(fetch_aa.__file__).parent)) + ")\n"
                "def refused(request, timeout=None):\n"
                "    raise urllib.error.URLError('Connection refused')\n"
                "urllib.request.urlopen = refused\n"
                "sys.argv = ['fetch_aa.py']\n"
                "import fetch_aa\n"
                "fetch_aa._sleep = lambda seconds: None\n"
                "fetch_aa.main()\n",
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(runner)],
                capture_output=True, text=True, timeout=120, check=False)

        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        lines = proc.stderr.strip().splitlines()
        self.assertEqual(len(lines), fetch_aa.PAGE_ATTEMPTS, proc.stderr)
        self.assertIn("retrying", lines[0], proc.stderr)
        self.assertIn("fetch failed", lines[-1])
        self.assertIn("Connection refused", lines[-1])
        self.assertEqual(proc.stdout, "")


def flaky(*events):
    """A urlopen route handler whose outcomes run in sequence: BaseException
    events are raised, str events are served as pages, and the last repeats.
    This is what AA answering one transient 500 before the real page looks
    like to the stub (issue #154)."""
    remaining = list(events)

    def handler() -> object:
        event = remaining.pop(0) if remaining else events[-1]
        if isinstance(event, BaseException):
            raise event
        return _FakeResponse(event)

    return handler


class PageFetchRetryTests(unittest.TestCase):
    """Issue #154: a transient upstream answer -- a 429, a 5xx, a timeout,
    a dropped connection -- on any page the capture fetches is retried a
    bounded number of times with backoff before the capture gives up, so
    one momentary 500 (run 37113891861) fails an attempt, not the hour.

    Every page comes through LoudUrlopenStub (unmodeled URLs raise rather
    than touch the network) and the sleep seam is a recorder, so no test
    really sleeps. The retry is the ONLY level left (issue #200 removed the
    pair-level disagreement loop above it): a refusal here still ends the
    capture, which is what keeps a hard-down site failing fast inside the
    single bound documented beside fetch_aa's constants.
    """

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")
    LEADERBOARD = flight_html(leaderboard_payload())
    DETAIL = flight_html(detail_payload())
    AGENTS = flight_html(agent_payload(
        [agent_row(f"Agent - Model {i}") for i in range(5)]))

    @contextlib.contextmanager
    def capture_over_boundary(self, routes: dict, *, seed: bool = False):
        """fetch_aa.main() over the stubbed urlopen with the sleep seam
        recorded. Yields (root, stub, sleeps, run, captured); `captured`
        holds both buffers even when run() raises."""
        stub = LoudUrlopenStub(routes)
        sleeps: list = []
        with tempfile.TemporaryDirectory(prefix=".issue-154-page-retry-") as tmp:
            root = pathlib.Path(tmp)
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                if seed:
                    # The previous capture, as a refused run must leave it.
                    fetch_aa.OUT.write_bytes(b"SENTINEL MODELS CAPTURE")
                    fetch_aa.AGENTS_OUT.write_bytes(b"SENTINEL AGENTS CAPTURE")
                    fetch_aa.STAMP.write_text("2020-01-01\n", encoding="utf-8")
                sys.argv = ["fetch_aa.py"]
                with unittest.mock.patch.object(urllib.request, "urlopen",
                                                stub), \
                        unittest.mock.patch.object(fetch_aa, "_sleep",
                                                   side_effect=sleeps.append,
                                                   create=True):
                    def run() -> tuple[str, str]:
                        out, err = io.StringIO(), io.StringIO()
                        with contextlib.redirect_stdout(out), \
                                contextlib.redirect_stderr(err):
                            try:
                                fetch_aa.main()
                            finally:
                                captured["stdout"] = out.getvalue()
                                captured["stderr"] = err.getvalue()
                        return captured["stdout"], captured["stderr"]

                    captured: dict = {"stdout": "", "stderr": ""}
                    yield root, stub, sleeps, run, captured
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def test_a_transient_500_on_the_leaderboard_is_retried_and_captured(self):
        # The incident shape: attempt 1 refuses with 500, attempt 2 reads
        # the real page, and the capture lands -- with the backoff sleep
        # and the stderr retry line as the only traces.
        routes = {
            fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(methodology_html()),
            fetch_aa.URL: flaky(
                urllib.error.HTTPError(fetch_aa.URL, 500,
                                       "Internal Server Error",
                                       email.message.Message(), None),
                self.LEADERBOARD),
            self.DETAIL_URL: lambda: _FakeResponse(self.DETAIL),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_boundary(routes) as (root, stub, sleeps, run,
                                                    _captured):
            stdout, stderr = run()

            self.assertEqual(stub.calls,
                             [fetch_aa.METHODOLOGY_URL, fetch_aa.URL,
                              fetch_aa.URL, self.DETAIL_URL, fetch_aa.URL,
                              fetch_aa.AGENTS_URL])
            self.assertEqual(sleeps,
                             [fetch_aa.PAGE_BACKOFF_SECONDS,
                              fetch_aa.DISPUTE_LOOK_SPACING_SECONDS])
            self.assertIn("attempt 1 of 3", stderr)
            self.assertIn(
                f"retrying in {fetch_aa.PAGE_BACKOFF_SECONDS}s", stderr)
            self.assertIn("wrote aa-raw-models.json", stdout)
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                datetime.date.today().isoformat() + "\n")

    def test_a_page_down_past_the_bound_is_refused_with_the_named_reason(self):
        # Every attempt answers 503: the refusal is the same one-line exit
        # as before the retry existed, naming the URL, the exhaustion and
        # the last reason -- and the previous capture on disk is untouched,
        # because a refused run writes nothing.
        def unavailable():
            raise urllib.error.HTTPError(fetch_aa.URL, 503,
                                         "Service Unavailable",
                                         email.message.Message(), None)

        routes = {fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(
                      methodology_html()),
                  fetch_aa.URL: unavailable}
        with self.capture_over_boundary(routes, seed=True) as (root, stub,
                                                               sleeps, run,
                                                               _captured):
            with self.assertRaises(SystemExit) as caught:
                run()

            message = str(caught.exception)
            self.assertIn(fetch_aa.URL, message)
            self.assertIn(
                f"fetch failed after {fetch_aa.PAGE_ATTEMPTS} attempts",
                message)
            self.assertIn("503", message)
            self.assertIn("Service Unavailable", message)
            self.assertEqual(
                sleeps,
                [k * fetch_aa.PAGE_BACKOFF_SECONDS
                 for k in range(1, fetch_aa.PAGE_ATTEMPTS)])
            self.assertEqual(
                stub.calls,
                [fetch_aa.METHODOLOGY_URL]
                + [fetch_aa.URL] * fetch_aa.PAGE_ATTEMPTS)
            self.assertEqual((root / "aa-raw-models.json").read_bytes(),
                             b"SENTINEL MODELS CAPTURE")
            self.assertEqual((root / "aa-raw-coding-agents.json").read_bytes(),
                             b"SENTINEL AGENTS CAPTURE")
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                "2020-01-01\n", "the stamp moved on a refused capture")

    def test_a_non_retryable_4xx_fails_fast_without_a_retry(self):
        # A 404 is an answer, not an outage: attempt 1 refuses and the
        # capture exits -- no backoff sleep, no retry line, nothing
        # written.
        def not_found():
            raise urllib.error.HTTPError(fetch_aa.URL, 404, "Not Found",
                                         email.message.Message(), None)

        routes = {fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(
                      methodology_html()),
                  fetch_aa.URL: not_found}
        with self.capture_over_boundary(routes, seed=True) as (root, stub,
                                                               sleeps, run,
                                                               captured):
            with self.assertRaises(SystemExit) as caught:
                run()

            message = str(caught.exception)
            self.assertIn(fetch_aa.URL, message)
            self.assertIn("fetch failed", message)
            self.assertIn("404", message)
            self.assertEqual(sleeps, [], "the 404 was retried")
            self.assertEqual(stub.calls,
                             [fetch_aa.METHODOLOGY_URL, fetch_aa.URL],
                             "the 404 was retried")
            self.assertNotIn("retrying", captured["stderr"])
            self.assertNotIn("wrote", captured["stdout"])
            self.assertEqual((root / "aa-raw-models.json").read_bytes(),
                             b"SENTINEL MODELS CAPTURE")

    def test_a_detail_route_divergence_is_merged_not_re_read(self):
        # The nesting pin, restated against the issue #200 rule. The detail
        # fetch eats one transient 500 (page retry, 5s backoff) and then
        # answers a snapshot whose intelligenceIndex is 52 against the
        # leaderboard's 51. There is no pair-level retry any more: the
        # leaderboard is the authority, so the capture lands on the first
        # read of each route (four calls, one wait) with the LEADERBOARD's
        # copy of the shared value in the written capture.
        routes = {
            fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(methodology_html()),
            fetch_aa.URL: lambda: _FakeResponse(self.LEADERBOARD),
            self.DETAIL_URL: flaky(
                urllib.error.HTTPError(self.DETAIL_URL, 500,
                                       "Internal Server Error",
                                       email.message.Message(), None),
                flight_html(detail_payload(intelligenceIndex=52))),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_boundary(routes) as (root, stub, sleeps, run,
                                                    _captured):
            stdout, stderr = run()

            self.assertEqual(
                stub.calls,
                [fetch_aa.METHODOLOGY_URL, fetch_aa.URL, self.DETAIL_URL,
                 self.DETAIL_URL, fetch_aa.URL, fetch_aa.AGENTS_URL])
            self.assertEqual(sleeps,
                             [fetch_aa.PAGE_BACKOFF_SECONDS,
                              fetch_aa.DISPUTE_LOOK_SPACING_SECONDS])
            self.assertIn(
                f"retrying in {fetch_aa.PAGE_BACKOFF_SECONDS}s", stderr)
            self.assertIn("wrote aa-raw-models.json", stdout)
            models = json.loads(
                (root / "aa-raw-models.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {m["slug"]: m for m in models}["fixture-model"]["intelligenceIndex"],
                51)


class TransportErrorClassifierTests(unittest.TestCase):
    """The page-retry classifier's verdicts, at the fetch_html boundary
    itself: which answers are transient (retried to the bound) and which
    are final (attempt 1 refuses). The status table is audit.yml's
    pip-audit retry (issue #128, PR #142) transplanted: 429 rides with the
    5xx family, every other 4xx fails fast."""

    def attempts_through_boundary(self, raiser) -> tuple[int, list]:
        """fetch_html against a stubbed urlopen that always raises
        `raiser`. -> (urlopen call count, recorded backoff sleeps)."""
        calls: list = []
        sleeps: list = []

        def stub(request, timeout=None):
            calls.append(request.full_url)
            raiser()

        with unittest.mock.patch.object(urllib.request, "urlopen", stub), \
                unittest.mock.patch.object(fetch_aa, "_sleep",
                                           side_effect=sleeps.append,
                                           create=True):
            with self.assertRaises(SystemExit):
                fetch_aa.fetch_html(None, fetch_aa.URL)
        return len(calls), sleeps

    def test_http_status_verdicts(self):
        # The 4xx picks sit at the classifier's edges: 430 is just past the
        # one retried 4xx, 499 just under the >= 500 floor, so a sloppy
        # range like 400 <= code < 500 or code >= 400 fails here.
        for code, retried in ((429, True), (430, False), (499, False),
                              (500, True), (502, True),
                              (503, True), (504, True),
                              (400, False), (403, False), (404, False),
                              (409, False), (451, False)):
            with self.subTest(code=code, retried=retried):
                error = urllib.error.HTTPError(fetch_aa.URL, code, "nope",
                                               email.message.Message(), None)

                def raise_it(e=error):
                    raise e

                calls, sleeps = self.attempts_through_boundary(raise_it)

                self.assertEqual(calls,
                                 fetch_aa.PAGE_ATTEMPTS if retried else 1)
                self.assertEqual(
                    sleeps,
                    [k * fetch_aa.PAGE_BACKOFF_SECONDS
                     for k in range(1, calls)])

    def test_transport_shapes_are_all_retryable(self):
        # DNS (gaierror rides URLError), connection refused, a socket
        # timeout, and dropped connections -- before the response
        # (RemoteDisconnected) and mid-body (IncompleteRead): each is an
        # outage shape, retried to the bound, never mistaken for an
        # answer.
        raisers = (
            ("dns failure", urllib.error.URLError(
                socket.gaierror(-2, "Name or service not known"))),
            ("connection refused", urllib.error.URLError(
                ConnectionRefusedError(111, "Connection refused"))),
            ("socket timeout", socket.timeout(
                "The read operation timed out")),
            ("dropped before response", http.client.RemoteDisconnected(
                "Remote end closed connection without response")),
            ("dropped mid-body", http.client.IncompleteRead(b"partial")),
        )
        for why, error in raisers:
            with self.subTest(why=why):
                def raise_it(e=error):
                    raise e

                calls, sleeps = self.attempts_through_boundary(raise_it)

                self.assertEqual(calls, fetch_aa.PAGE_ATTEMPTS)
                self.assertEqual(
                    sleeps,
                    [k * fetch_aa.PAGE_BACKOFF_SECONDS
                     for k in range(1, calls)])


class RetryBoundArithmeticTests(unittest.TestCase):
    """The capture's worst case must fit inside refresh.yml's 30-minute
    job timeout WITHOUT editing the workflow, so the fit is pinned as an
    assertion rather than narrated. A future constant bump that would crowd
    out the rest of the job (checkout, pip + Chromium, the browser suite,
    build, publish -- ~7 min measured) fails here instead of timing out a
    real run."""

    # One page fetch's bound: PAGE_ATTEMPTS attempts, each stalling at most
    # FETCH_TIMEOUT_SECONDS, plus the linear backoff sleeps between them.
    PAGE_BOUND = (fetch_aa.PAGE_ATTEMPTS * fetch_aa.FETCH_TIMEOUT_SECONDS
                  + sum(k * fetch_aa.PAGE_BACKOFF_SECONDS
                        for k in range(1, fetch_aa.PAGE_ATTEMPTS)))
    # The capture fetches exactly five pages (the methodology version pin,
    # two spaced leaderboard looks, the detail page, the coding agents),
    # each at that bound, plus one dispute-look spacing wait (issue #208);
    # the page retry is the only retry level left (issue #200). 1200 s is
    # the capture budget that leaves the ~7-min remainder room in the job's
    # 1800 s, with slack.
    CAPTURE_BUDGET = 1200

    def test_worst_case_stays_within_the_capture_budget(self):
        # The comment in fetch_aa.py commits to exactly this arithmetic.
        worst_case = (5 * self.PAGE_BOUND
                      + fetch_aa.DISPUTE_LOOK_SPACING_SECONDS)

        self.assertLessEqual(worst_case, self.CAPTURE_BUDGET)

    def test_a_hard_down_site_fails_inside_the_first_page_bound(self):
        # Issue #154's fail-fast half: transport exhaustion short-circuits
        # the capture, so a dead AA is refused inside ONE page bound -- never
        # the three-page product -- and the hour's run goes red fast instead
        # of hanging toward the job timeout.
        self.assertLessEqual(self.PAGE_BOUND, self.CAPTURE_BUDGET)

    def test_the_sleep_seam_actually_sleeps(self):
        # The seam exists so no TEST ever really sleeps -- and so the wait
        # is real in production. Patching time.sleep itself proves the seam
        # delegates rather than no-ops. (The seam itself is the unit under
        # test here, hence the protected-access.)
        with unittest.mock.patch.object(fetch_aa.time, "sleep") as fake:
            fetch_aa._sleep(5)  # pylint: disable=protected-access

        fake.assert_called_once_with(5)


def look_payload(ii: float, **overrides: object) -> str:
    """A leaderboard flight payload whose fixture model carries `ii` plus
    any record overrides; the unpriced detail host is unchanged, so the
    host pick never churns."""
    host = {"slug": "detail-host-model",
            "intelligenceIndexCostPerTask": "$undefined"}
    return json.dumps({
        "intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
        "models": [host, leaderboard_record(intelligenceIndex=ii, **overrides)],
    }, separators=(",", ":"))


def host_priced_payload(host_ii: float, host_cost: object,
                        fixture_ii: float) -> str:
    """A leaderboard payload whose HOST carries `host_ii`/`host_cost` --
    the lever for disputes that live on a slug the detail route never
    carries (its own subject)."""
    host = {"slug": "detail-host-model", "intelligenceIndex": host_ii,
            "intelligenceIndexCostPerTask": host_cost}
    return json.dumps({
        "intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
        "models": [host, leaderboard_record(intelligenceIndex=fixture_ii)],
    }, separators=(",", ":"))


def _look(slug, ii=40.0, cost=2.0, gdp=0.31, speed=120.0, **extra):
    rec = {"slug": slug, "name": slug, "intelligenceIndex": ii,
           "intelligenceIndexCostPerTask": cost, "gdpvalNormalized": gdp,
           "medianOutputTokensPerSecond": speed, "contextWindowTokens": 200000,
           "price1mInputTokens": 0.5, "price1mOutputTokens": 1.5}
    rec.update(extra)
    return rec


def priced_look(slug, total, gdpval_part, **extra):
    """A look whose cost carries the per-evaluation breakdown shape; its
    parts sum to the total unless the caller breaks them on purpose."""
    rec = _look(slug, **extra)
    rec["intelligenceIndexCostPerTask"] = {
        "cost": {"total": total},
        "evaluations": [
            {"slug": "gdpval-aa", "weightedCostPerTask": gdpval_part},
            {"slug": "scicode", "weightedCostPerTask": total - gdpval_part},
        ],
    }
    return rec


class TestCrossGenerationMerge(unittest.TestCase):
    """Issue #208: when the two leaderboard looks carry DIFFERENT published
    values, the corpus holds both generations -- genVariants per record,
    canonical (ascending generation_key) order -- while agreeing looks, a
    speed-only movement and a missing-marker-vs-value flip all stay exactly
    today's single-generation corpus."""

    def test_agreeing_looks_write_no_variants(self):
        out = fetch_aa.cross_generation_merge([[_look("a")], [_look("a")]])
        self.assertTrue(all("genVariants" not in r for r in out))

    def test_speed_only_difference_is_not_a_generation(self):
        out = fetch_aa.cross_generation_merge(
            [[_look("a")], [_look("a", speed=999.0)]])
        self.assertTrue(all("genVariants" not in r for r in out))

    def test_disagreement_writes_variants_canonical_order(self):
        out = fetch_aa.cross_generation_merge(
            [[_look("a", ii=41.0)], [_look("a", ii=40.5)]])
        r = out[0]
        self.assertEqual(len(r["genVariants"]), 2)
        self.assertEqual([v["ii"] for v in r["genVariants"]],
                         sorted(v["ii"] for v in r["genVariants"]))
        self.assertEqual(r["intelligenceIndex"],
                         r["genVariants"][0]["ii"])

    def test_reversed_look_order_identical_bytes(self):
        x = fetch_aa.cross_generation_merge(
            [[_look("a", ii=41.0)], [_look("a", ii=40.5)]])
        y = fetch_aa.cross_generation_merge(
            [[_look("a", ii=40.5)], [_look("a", ii=41.0)]])
        self.assertEqual(json.dumps(x), json.dumps(y))

    def test_union_of_models(self):
        out = fetch_aa.cross_generation_merge(
            [[_look("a"), _look("b")], [_look("a"), _look("c")]])
        self.assertEqual(sorted(m["slug"] for m in out), ["a", "b", "c"])

    def test_a_model_in_one_corpus_only_is_a_presence_dispute(self):
        # Issue #211 (Overseer ruling, 2026-10-06): presence in one
        # generation and absence from the other is an inconsistency between
        # the generations. The union keeps the model, disputed by presence,
        # and every record's genVariants is padded to one entry per corpus
        # in canonical order -- `{}` at each position whose corpus does not
        # carry the record.
        corpora = [[_look("a")], [_look("a"), _look("b")]]
        universe = fetch_aa.leaderboard_universe(corpora)
        ranked = sorted(range(len(corpora)),
                        key=lambda i: fetch_aa.generation_key(corpora[i],
                                                              universe))
        carrier_at = ranked.index(1)

        out = fetch_aa.cross_generation_merge(corpora)

        self.assertTrue(all("genVariants" in r for r in out))
        b = next(r for r in out if r["slug"] == "b")
        self.assertEqual(len(b["genVariants"]), 2)
        self.assertEqual(b["genVariants"][carrier_at],
                         fetch_aa.variant_fields(_look("b")))
        self.assertEqual(b["genVariants"][1 - carrier_at], {})
        # The carried variant is never `{}`: variant_fields emits at least
        # one field for any record the leaderboard writes.
        self.assertTrue(b["genVariants"][carrier_at])
        # The plain fields are the carrier's own values.
        self.assertEqual(b["intelligenceIndex"],
                         _look("b")["intelligenceIndex"])

    def test_presence_dispute_reversed_corpora_identical_bytes(self):
        # Canonical order is ascending generation_key, so the padded corpus
        # does not depend on which corpus the caller listed first.
        x = fetch_aa.cross_generation_merge(
            [[_look("a")], [_look("a"), _look("b")]])
        y = fetch_aa.cross_generation_merge(
            [[_look("a"), _look("b")], [_look("a")]])
        self.assertEqual(json.dumps(x), json.dumps(y))

    def test_undefined_folds_to_missing_not_a_dispute(self):
        out = fetch_aa.cross_generation_merge(
            [[_look("a", price1mInputTokens="$undefined")],
             [_look("a", price1mInputTokens=2.5)]])
        r = out[0]
        self.assertNotIn("genVariants", r)
        self.assertEqual(r["price1mInputTokens"], 2.5)

    def test_variant_fields_recovered_per_generation(self):
        # gdpvalCost comes from EACH variant's own breakdown; the variant
        # whose breakdown does not sum to its own total renders that axis
        # absent, never fabricated from the other generation's parts.
        good = priced_look("a", total=2.0, gdpval_part=0.16, ii=40.0)
        bad = priced_look("a", total=2.0, gdpval_part=0.40, ii=40.5)
        bad["intelligenceIndexCostPerTask"]["evaluations"] = [
            {"slug": "gdpval-aa", "weightedCostPerTask": 0.40},
            {"slug": "scicode", "weightedCostPerTask": 0.45},
        ]
        out = fetch_aa.cross_generation_merge([[good], [bad]])

        r = out[0]
        self.assertEqual(len(r["genVariants"]), 2)
        by_ii = {v["ii"]: v for v in r["genVariants"]}
        self.assertIn("gdpvalCost", by_ii[40.0])
        self.assertNotIn("gdpvalCost", by_ii[40.5])
        self.assertAlmostEqual(by_ii[40.0]["gdpvalCost"], 1.6)


class CarriedVariantNeverEmptyTests(unittest.TestCase):
    """The padded interface's load-bearing invariant, enforced on the one
    corpus a reviewer cannot hand-pick: variant_fields() emits at least one
    field for EVERY record in the committed capture. The page reads `{}` as
    "this generation does not carry the model" (issue #211), so a genuine
    `{}` variant would flip carried fields to false red "value / —" cells;
    if a real record can be empty, the encoding needs a third marker, not a
    silent lie."""

    def test_every_committed_record_yields_a_non_empty_variant_map(self):
        capture_path = (pathlib.Path(__file__).resolve().parent.parent
                        / "data" / "aa-raw-models.json")
        records = json.loads(capture_path.read_text(encoding="utf-8"))

        self.assertTrue(all(fetch_aa.variant_fields(m) for m in records))


class MultiLookCaptureTests(unittest.TestCase):
    """Issue #208: capture() reads the leaderboard TWICE -- L1, the detail
    page, one DISPUTE_LOOK_SPACING_SECONDS wait, then L2 -- and holds both
    generations when the looks disagree. The boundary is the stubbed
    urlopen (unmodeled URLs raise), and the sleep seam is a recorder, so no
    test really sleeps or touches the network."""

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")

    def capture_two_looks(self, leaderboard_pages, **detail_overrides):
        """capture(None, None, None) over a stubbed urlopen that answers the
        leaderboard route with `leaderboard_pages` in sequence (the two
        looks read that route twice), the methodology route with the pinned
        generation's page, and the detail route with the standard detail
        page, record-overridden by `detail_overrides`.
        -> (Capture, recorded sleeps, stub)."""
        stub = LoudUrlopenStub({
            fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(methodology_html()),
            fetch_aa.URL: flaky(*leaderboard_pages),
            self.DETAIL_URL: lambda: _FakeResponse(
                flight_html(detail_payload(**detail_overrides))),
        })
        sleeps: list = []
        with unittest.mock.patch.object(urllib.request, "urlopen", stub), \
                unittest.mock.patch.object(fetch_aa, "_sleep",
                                           side_effect=sleeps.append,
                                           create=True):
            return fetch_aa.capture(None, None, None), sleeps, stub

    def test_one_generation_writes_no_variants_and_keeps_todays_corpus(self):
        # The quiet hour: both looks and the detail route carry one
        # generation, the wiring is exactly today's (L1, D, L2, agents
        # never), the one wait is the spacing, and the corpus is byte-what
        # today's writer produces -- no genVariants key anywhere.
        captured, sleeps, stub = self.capture_two_looks(
            [flight_html(look_payload(51))])

        self.assertEqual(stub.calls, [fetch_aa.METHODOLOGY_URL, fetch_aa.URL,
                                      self.DETAIL_URL, fetch_aa.URL])
        self.assertEqual(sleeps, [fetch_aa.DISPUTE_LOOK_SPACING_SECONDS])
        self.assertFalse(captured.disputed)
        self.assertEqual(captured.generations, 1)
        self.assertTrue(all("genVariants" not in m for m in captured.models))
        host = {"slug": "detail-host-model",
                "intelligenceIndexCostPerTask": "$undefined"}
        self.assertEqual(captured.models,
                         build.merge_captures(
                             [host, leaderboard_record()],
                             [detail_record()]))

    def test_two_generations_are_held_as_variants(self):
        # The update lands between the looks: L1 says 51, L2 says 52, and
        # the capture holds BOTH, canonical (ascending generation_key)
        # first, with the plain fields the canonical generation's.
        captured, sleeps, _stub = self.capture_two_looks(
            [flight_html(look_payload(51)), flight_html(look_payload(52))])

        self.assertEqual(sleeps, [fetch_aa.DISPUTE_LOOK_SPACING_SECONDS])
        self.assertTrue(captured.disputed)
        self.assertEqual(captured.generations, 2)
        by_slug = {m["slug"]: m for m in captured.models}
        variants = by_slug["fixture-model"]["genVariants"]
        iis = [v["ii"] for v in variants]
        self.assertEqual(iis, sorted(iis))
        self.assertEqual(by_slug["fixture-model"]["intelligenceIndex"], iis[0])

    def test_the_detail_fill_lands_on_the_generation_it_belongs_to(self):
        # The detail route carries ii 51, so its breakdown widens the 51
        # generation ONLY: that variant's gdpvalCost is recovered from its
        # own parts, and the 52 variant -- whose corpus the detail route
        # did not describe -- renders the axis absent rather than
        # decomposing another generation's total.
        captured, _sleeps, _stub = self.capture_two_looks(
            [flight_html(look_payload(51)), flight_html(look_payload(52))])

        by_slug = {m["slug"]: m for m in captured.models}
        by_ii = {v["ii"]: v
                 for v in by_slug["fixture-model"]["genVariants"]}
        self.assertIn("gdpvalCost", by_ii[51])
        self.assertAlmostEqual(by_ii[51]["gdpvalCost"], 3.0)
        self.assertNotIn("gdpvalCost", by_ii[52])

    def test_a_speed_only_difference_between_looks_is_not_a_generation(self):
        # Review Focus 2's capture-level pin: the speed family re-samples
        # every hour BY DESIGN, so a mutant that stopped subtracting
        # NEVER_RED_FIELDS in generation_key would flip every hourly run
        # onto the disputed path (and, with the detail route then matching
        # no look's mutated key, strip its detail fills). Both looks here
        # differ ONLY on medianOutputTokensPerSecond; the capture must
        # hold the quiet shape end to end.
        host = {"slug": "detail-host-model",
                "intelligenceIndexCostPerTask": "$undefined"}
        look1 = [host, leaderboard_record(intelligenceIndex=51,
                                          medianOutputTokensPerSecond=120.0)]
        captured, sleeps, stub = self.capture_two_looks(
            [flight_html(look_payload(51, medianOutputTokensPerSecond=120.0)),
             flight_html(look_payload(51, medianOutputTokensPerSecond=999.0))])

        self.assertEqual(stub.calls, [fetch_aa.METHODOLOGY_URL, fetch_aa.URL,
                                      self.DETAIL_URL, fetch_aa.URL])
        self.assertEqual(sleeps, [fetch_aa.DISPUTE_LOOK_SPACING_SECONDS])
        self.assertFalse(captured.disputed)
        self.assertEqual(captured.generations, 1)
        self.assertTrue(all("genVariants" not in m for m in captured.models))
        self.assertEqual(captured.models,
                         build.merge_captures(look1, [detail_record()]))

    def test_a_detail_generation_matching_neither_look_fills_nothing(self):
        # D a third generation: it widens no corpus that hour -- both
        # variants render their own generation's values with the GDPval
        # cost absent (no breakdown is that generation's own), the summary
        # counts three observed generations, and the hour self-heals once
        # the routes converge.
        captured, _sleeps, _stub = self.capture_two_looks(
            [flight_html(look_payload(51)), flight_html(look_payload(52))],
            intelligenceIndex=53)

        self.assertTrue(captured.disputed)
        self.assertEqual(captured.generations, 3)
        by_slug = {m["slug"]: m for m in captured.models}
        variants = by_slug["fixture-model"]["genVariants"]
        self.assertEqual(sorted(v["ii"] for v in variants), [51, 52])
        self.assertTrue(all("gdpvalCost" not in v for v in variants))

    def presence_flip_pages(self):
        """Two leaderboard pages shaped like the real alternating captures
        this pins (305b827 / 75eb62b / c18d95a): every shared slug carries
        IDENTICAL normalized values -- the cost field churns null on the
        first look and "$undefined" on the second, which
        normalize_for_comparison folds to one marker, and the speed family
        re-samples -- while the slug sets differ by exactly one model:
        solar-pro-2 present in the first look only."""
        def page(records):
            return flight_html(json.dumps(
                {"intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
                 "models": records}, separators=(",", ":")))

        host = {"slug": "detail-host-model",
                "intelligenceIndexCostPerTask": "$undefined"}
        solar = {"slug": "solar-pro-2", "name": "Solar Pro 2",
                 "intelligenceIndex": 48.5,
                 "intelligenceIndexCostPerTask": None,
                 "contextWindowTokens": 200000}
        look1 = [host,
                 leaderboard_record(intelligenceIndex=51,
                                    intelligenceIndexCostPerTask=None,
                                    medianOutputTokensPerSecond=120.0),
                 solar]
        look2 = [host,
                 leaderboard_record(intelligenceIndex=51,
                                    intelligenceIndexCostPerTask="$undefined",
                                    medianOutputTokensPerSecond=999.0)]
        return page(look1), page(look2)

    def test_a_slug_set_flip_between_looks_is_a_presence_dispute(self):
        # Issue #211's real flip, pinned at the boundary the dispute decision
        # actually runs at: the looks' shared slugs carry identical values
        # under every churn AA's two cache generations show (cost null vs
        # "$undefined", a never-red speed re-sample), so the old branch
        # condition -- shared-slug keys equal -- took the quiet path and the
        # published slug set flipped with AA's cache. Presence in one look
        # and absence from the other is an inconsistency between the
        # generations: 2 generations, disputed, the union keeps the model.
        page1, page2 = self.presence_flip_pages()
        # The detail route shows the same churned shape as the looks (its
        # own cache generation), so its fill lands on both corpora.
        captured, sleeps, stub = self.capture_two_looks(
            [page1, page2], intelligenceIndexCostPerTask=None)

        self.assertEqual(stub.calls, [fetch_aa.METHODOLOGY_URL, fetch_aa.URL,
                                      self.DETAIL_URL, fetch_aa.URL])
        self.assertEqual(sleeps, [fetch_aa.DISPUTE_LOOK_SPACING_SECONDS])
        self.assertTrue(captured.disputed)
        self.assertEqual(captured.generations, 2)
        by_slug = {m["slug"]: m for m in captured.models}
        self.assertIn("solar-pro-2", by_slug)
        solar = by_slug["solar-pro-2"]
        self.assertEqual(len(solar["genVariants"]), 2)
        self.assertEqual(sum(1 for v in solar["genVariants"] if v), 1)
        self.assertEqual(solar["intelligenceIndex"], 48.5)
        # The shared slugs are carried by both corpora: non-empty variants.
        fixture = by_slug["fixture-model"]
        self.assertEqual(len(fixture["genVariants"]), 2)
        self.assertTrue(all(fixture["genVariants"]))

    def test_the_presence_flip_corpus_is_order_independent(self):
        # Canonical order is ascending generation_key, and a presence
        # disagreement is two different slug sets, so the keys differ and
        # the corpus does not depend on which look a run read first.
        page1, page2 = self.presence_flip_pages()
        one, _, _ = self.capture_two_looks(
            [page1, page2], intelligenceIndexCostPerTask=None)
        two, _, _ = self.capture_two_looks(
            [page2, page1], intelligenceIndexCostPerTask=None)

        self.assertEqual(json.dumps(one.models), json.dumps(two.models))

    def test_a_dispute_off_the_detail_slugs_widens_both_generations(self):
        # The both-matches cell, which IS reachable: the looks disagree
        # only on a slug the detail route never carries (its own host), so
        # same_generation passes for both and each generation's corpus
        # takes the fill. The fill is gap-only either way -- merge_captures
        # precedence keeps each look's own values -- so this pins honest
        # behavior, it does not invent it.
        captured, _sleeps, _stub = self.capture_two_looks(
            [flight_html(host_priced_payload(30, "$undefined", 51)),
             flight_html(host_priced_payload(31, 1.25, 51))])

        self.assertTrue(captured.disputed)
        self.assertEqual(captured.generations, 2)
        by_slug = {m["slug"]: m for m in captured.models}
        # The host dispute itself: two published ii values on the slug the
        # detail route omits, and exactly one generation priced it.
        host_variants = by_slug["detail-host-model"]["genVariants"]
        self.assertEqual(sorted(v["ii"] for v in host_variants), [30, 31])
        self.assertEqual(sorted(v["cost"] for v in host_variants
                                if "cost" in v), [1.25])
        # Both corpora were widened by the same detail snapshot, so both
        # fixture-model variants carry its recovered gdpvalCost.
        fixture_variants = by_slug["fixture-model"]["genVariants"]
        self.assertEqual(len(fixture_variants), 2)
        for variant in fixture_variants:
            self.assertAlmostEqual(variant["gdpvalCost"], 3.0)


class GenVariantsSeamTests(unittest.TestCase):
    """The producer→consumer seam of issue #208's dispute layer, pinned on
    real function output: cross_generation_merge's disputed corpus feeds
    build_rows (which must carry it as `gv`), and the one key the disputed
    corpus adds over the quiet corpus is exactly the key diff_aa's Disputes
    class files. The minimal `_look` fixture above is the whole corpus --
    this is a seam pin, not a behavior re-test."""

    def test_a_disputed_merge_feeds_build_rows_as_gv(self):
        disputed = fetch_aa.cross_generation_merge(
            [[_look("a", ii=41.0)], [_look("a", ii=40.5)]])

        rows = build.build_rows(disputed)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            sorted(v["ii"] for v in rows[0]["gv"]), [40.5, 41.0])
        # Canonical-first: the row's plain values are the first variant's.
        self.assertEqual(rows[0]["ii"], rows[0]["gv"][0]["ii"])

    def test_diff_aa_files_exactly_the_key_the_producer_writes(self):
        quiet = fetch_aa.cross_generation_merge([[_look("a")], [_look("a")]])
        disputed = fetch_aa.cross_generation_merge(
            [[_look("a", ii=41.0)], [_look("a", ii=40.5)]])

        added = {k for record in disputed for k in record} \
            - {k for record in quiet for k in record}

        self.assertEqual(added, {diff_aa.DISPUTES_KEY})

    def test_the_gv_field_order_matches_variant_fields_emission_order(self):
        # The shared-literal seam (issue #226): build.py's GV_FIELD_ORDER
        # restates variant_fields' emission order so a disputed row's gv
        # maps cannot depend on the capture's raw key layout. The
        # correspondence lives in two modules, so the pin spans both: a
        # record carrying every dispute-capable field, through the
        # producer, comes out in exactly the consumer's declared order --
        # and the row build.py emits carries its gv in the same order.
        record = priced_look("a", 1.0, 0.1)

        variant = fetch_aa.variant_fields(record)

        self.assertEqual(list(variant), list(build.GV_FIELD_ORDER))
        rows = build.build_rows([dict(record, genVariants=[variant])])
        self.assertEqual(list(rows[0]["gv"][0]), list(build.GV_FIELD_ORDER))


class CrossRunPresenceMergeTests(unittest.TestCase):
    """Issue #211's cross-run half (Overseer ruling, 2026-10-06, on the
    reopened issue): a model present in the previous committed capture and
    absent from this run's own fetch -- or the reverse -- is MERGED and
    marked disputed, never quietly dropped or re-added, so the published
    set does not flip hour to hour. The layer is presence-only:
    hour-to-hour value movement is ordinary data, so the previous corpus
    participates only through the diff slugs -- a shared model raises no
    cross-run value dispute and takes no previous-generation slot."""

    def merge(self, current, prev, run_corpora=None):
        return fetch_aa.cross_run_presence_merge(
            current, prev,
            run_corpora if run_corpora is not None else [current])

    def test_matching_slug_sets_change_nothing(self):
        # The quiet hour: the slug sets agree, the corpus is byte-what the
        # caller passed and no synthetic key exists anywhere.
        current = [_look("a"), _look("b")]
        out, cross_run = self.merge(current, [_look("b"), _look("a")])

        self.assertEqual((cross_run.dropped, cross_run.readded), ([], []))
        self.assertEqual(json.dumps(out), json.dumps(current))
        self.assertTrue(all("genVariants" not in m for m in out))
        self.assertTrue(all(fetch_aa.CROSS_RUN_KEY not in m for m in out))

    def test_a_dropped_model_is_merged_and_marked(self):
        # AA stopped serving b: the union keeps it, the record is the
        # previous generation's own values, `crossRunMerged` marks it as
        # dispute state rather than serving evidence, and exactly one
        # variant slot is the empty map (the run's own generation). Shared
        # models are untouched -- no genVariants anywhere else.
        current = [_look("a")]
        out, cross_run = self.merge(current, [_look("a"), _look("b", ii=48.5)])

        self.assertEqual(cross_run.dropped, ["b"])
        self.assertEqual(cross_run.readded, [])
        self.assertEqual([m["slug"] for m in out], ["a", "b"])
        b = out[1]
        self.assertIs(b[fetch_aa.CROSS_RUN_KEY], True)
        self.assertEqual(b["intelligenceIndex"], 48.5)
        self.assertEqual(len(b["genVariants"]), 2)
        self.assertEqual(sum(1 for v in b["genVariants"] if not v), 1)
        carried = next(v for v in b["genVariants"] if v)
        self.assertEqual(carried, fetch_aa.variant_fields(_look("b", ii=48.5)))
        self.assertNotIn("genVariants", out[0])

    def test_a_returned_model_is_disputed_by_presence(self):
        # AA started serving b again: the model is kept (it IS this run's
        # own fetch), the empty map marks the generation that does not
        # carry it, and the record carries no marker -- it is serving
        # evidence the moment this run's fetch returned it.
        prev = [_look("a")]
        current = [_look("a"), _look("b", ii=48.5)]
        out, cross_run = self.merge(current, prev)

        self.assertEqual(cross_run.dropped, [])
        self.assertEqual(cross_run.readded, ["b"])
        b = next(m for m in out if m["slug"] == "b")
        self.assertNotIn(fetch_aa.CROSS_RUN_KEY, b)
        self.assertEqual(b["intelligenceIndex"], 48.5)
        self.assertEqual(len(b["genVariants"]), 2)
        self.assertEqual(sum(1 for v in b["genVariants"] if not v), 1)
        carried = next(v for v in b["genVariants"] if v)
        self.assertEqual(carried, fetch_aa.variant_fields(_look("b", ii=48.5)))
        self.assertNotIn("genVariants", out[0])

    def test_slots_are_ordered_by_generation_key(self):
        # Canonical order is ascending generation_key over the joint field
        # universe, the same rule the in-run padding follows, so the
        # previous generation's slot lands where its corpus key ranks.
        current = [_look("a")]
        out, _ = self.merge(current, [_look("b", ii=48.5)])

        b = out[1]
        corpora = [[_look("b", ii=48.5)], [_look("a")]]
        universe = fetch_aa.leaderboard_universe(corpora)
        ranked = sorted(range(2), key=lambda i: fetch_aa.generation_key(
            corpora[i], universe))
        prev_at = ranked.index(0)

        carried_at = next(i for i, v in enumerate(b["genVariants"]) if v)
        self.assertEqual(carried_at, prev_at)
        self.assertEqual(b["genVariants"][1 - prev_at], {})

    def test_canonical_bytes_do_not_depend_on_input_order(self):
        # The previous capture's record order must not move the corpus
        # bytes: generation_key ranking positions the slot, never the
        # order the look-back happened to read.
        current = [_look("a")]
        x = self.merge(current, [_look("a"), _look("b", ii=48.5)])
        y = self.merge(current, [_look("b", ii=48.5), _look("a")])

        self.assertEqual(json.dumps(x[0]), json.dumps(y[0]))

    def test_a_settling_model_leaves_cleanly(self):
        # b was merged and marked last hour and AA still does not serve it:
        # a marked record is dispute state, not serving evidence, so it
        # neither merges nor disputes again -- the model settles out and
        # every record is clean. THIS is what keeps a stable retirement
        # from being pinned disputed forever.
        prev = [_look("a"), dict(_look("b", ii=48.5),
                                 **{fetch_aa.CROSS_RUN_KEY: True})]
        out, cross_run = self.merge([_look("a")], prev)

        self.assertEqual((cross_run.dropped, cross_run.readded), ([], []))
        self.assertEqual([m["slug"] for m in out], ["a"])
        self.assertTrue(all("genVariants" not in m for m in out))

    def test_a_returned_model_is_clean_once_both_runs_serve_it(self):
        # The hour after a re-add: b is firm in both (this run's fetch
        # served it, so it is firm in the next look-back), the dispute is
        # resolved by AA's own return, and the record carries no variant.
        prev = [_look("a"), _look("b")]
        current = [_look("a"), _look("b", ii=41.0)]
        out, cross_run = self.merge(current, prev)

        self.assertEqual((cross_run.dropped, cross_run.readded), ([], []))
        self.assertTrue(all("genVariants" not in m for m in out))
        b = next(m for m in out if m["slug"] == "b")
        self.assertEqual(b["intelligenceIndex"], 41.0)

    def test_a_dropped_model_spans_both_looks(self):
        # The dropped branch under a two-generation in-run run: the
        # previous generation's carried slot lands at its own rank among
        # BOTH look slots, each an empty map.
        c1 = [_look("a", ii=40.5)]
        c2 = [_look("a", ii=41.0)]
        models = fetch_aa.cross_generation_merge([c1, c2])

        out, cross_run = self.merge(models, [_look("a"), _look("b", ii=48.5)],
                                    run_corpora=[c1, c2])

        self.assertEqual(cross_run.dropped, ["b"])
        b = next(m for m in out if m["slug"] == "b")
        self.assertIs(b[fetch_aa.CROSS_RUN_KEY], True)
        self.assertEqual(len(b["genVariants"]), 3)
        self.assertEqual(sum(1 for v in b["genVariants"] if not v), 2)
        carried = next(v for v in b["genVariants"] if v)
        self.assertEqual(carried, fetch_aa.variant_fields(_look("b", ii=48.5)))

    def test_canonical_bytes_do_not_depend_on_look_order(self):
        # Reversing the run's corpora -- the order the looks were read --
        # must not move the corpus bytes: prev_position counts
        # strictly-smaller generation keys, never positions.
        current = [_look("a", ii=40.5)]
        other = [_look("a", ii=41.0)]
        models = fetch_aa.cross_generation_merge([current, other])
        prev = [_look("b", ii=48.5)]

        x = self.merge(models, prev, run_corpora=[current, other])
        y = self.merge(models, prev, run_corpora=[other, current])

        self.assertEqual(json.dumps(x[0]), json.dumps(y[0]))

    def test_a_returned_marked_model_is_disputed_once_then_clean(self):
        # The oscillating-AA seam: b was merged and marked last hour and
        # AA serves it again. The hour of the return is one red readd
        # (no marker -- the fresh fetch is serving evidence), and the
        # hour after is clean.
        marked = dict(_look("b", ii=48.5),
                      **{fetch_aa.CROSS_RUN_KEY: True})
        current = [_look("a"), _look("b", ii=48.5)]

        out, cross_run = self.merge(current, [_look("a"), marked])

        self.assertEqual(cross_run.readded, ["b"])
        b = next(m for m in out if m["slug"] == "b")
        self.assertNotIn(fetch_aa.CROSS_RUN_KEY, b)
        self.assertEqual(sum(1 for v in b["genVariants"] if not v), 1)
        out2, cross_run2 = self.merge(current, out)
        self.assertEqual((cross_run2.dropped, cross_run2.readded), ([], []))
        self.assertTrue(all("genVariants" not in m for m in out2))

    def test_a_slugless_previous_capture_holds_no_evidence(self):
        # A parseable previous capture whose records all lack a usable
        # slug cannot be keyed: it holds no presence evidence, so the
        # layer stays silent rather than reading every slug as a readd.
        out, cross_run = self.merge([_look("a"), _look("b")], [{"x": 1}])

        self.assertEqual((cross_run.dropped, cross_run.readded), ([], []))
        self.assertEqual(json.dumps(out),
                         json.dumps([_look("a"), _look("b")]))

    def test_a_disputed_previous_capture_is_read_canonically(self):
        # The previous run disputed b's own value (two in-run variants);
        # the look-back reads the record's CANONICAL view -- the plain
        # fields, which are the first carrying variant's -- and merges
        # that, never the variant list.
        prev_b = dict(_look("b", ii=41.0))
        prev_b["genVariants"] = [
            fetch_aa.variant_fields(_look("b", ii=41.0)),
            fetch_aa.variant_fields(_look("b", ii=40.5)),
        ]
        out, cross_run = self.merge([_look("a")], [dict(_look("a")), prev_b])

        self.assertEqual(cross_run.dropped, ["b"])
        b = out[1]
        self.assertEqual(b["intelligenceIndex"], 41.0)
        carried = next(v for v in b["genVariants"] if v)
        self.assertEqual(carried, fetch_aa.variant_fields(_look("b", ii=41.0)))

    def test_an_in_run_dispute_and_a_cross_run_dispute_coexist(self):
        # The looks disagreed on a's ii AND b was re-added this hour: b's
        # variant list spans all three generations -- the two look slots
        # preserved in order, the previous generation's empty map inserted
        # at its own rank -- while `a`, disputed in-run but firm in both
        # runs, keeps exactly its two look slots.
        c1 = [_look("a", ii=40.5), _look("b", ii=48.5)]
        c2 = [_look("a", ii=41.0), _look("b", ii=48.5)]
        models = fetch_aa.cross_generation_merge([c1, c2])

        out, cross_run = self.merge(models, [_look("a")], run_corpora=[c1, c2])

        self.assertEqual(cross_run.readded, ["b"])
        by_slug = {m["slug"]: m for m in out}
        b_gv = by_slug["b"]["genVariants"]
        self.assertEqual(len(b_gv), 3)
        self.assertEqual(sum(1 for v in b_gv if not v), 1)
        self.assertEqual(sorted(v["ii"] for v in b_gv if v),
                         [48.5, 48.5])
        self.assertEqual(len(by_slug["a"]["genVariants"]), 2)

    def test_the_layer_adds_exactly_two_synthetic_keys(self):
        # The producer/differ seam, extended: the in-run layer adds exactly
        # genVariants over a quiet corpus (pinned above); the cross-run
        # layer adds exactly one more, and the differ files it under the
        # disputes class so it sections instead of printing a per-model
        # field line for every merged record.
        quiet = [_look("a"), _look("b")]
        marked = self.merge([_look("a")], quiet)[0]

        added = {k for record in marked for k in record} \
            - {k for record in quiet for k in record}

        self.assertEqual(added,
                         {diff_aa.DISPUTES_KEY, fetch_aa.CROSS_RUN_KEY})
        self.assertEqual(diff_aa.classify(fetch_aa.CROSS_RUN_KEY),
                         diff_aa.DISPUTES_CLASS)

    def test_the_marker_never_reaches_the_page_rows(self):
        # build_rows reads named fields; the dispute marker is capture-side
        # state. The page row carries the gv pair but never the marker, so
        # the published payload asserts no serving state of its own.
        out, _ = self.merge([_look("a")], [_look("a"), _look("b", ii=48.5)])
        b = next(m for m in out if m["slug"] == "b")

        row = build.build_rows([b])[0]

        self.assertNotIn(fetch_aa.CROSS_RUN_KEY, row)
        self.assertEqual(len(row["gv"]), 2)


class CrossRunCaptureTests(unittest.TestCase):
    """capture() threading the previous capture through to the cross-run
    merge: a run whose looks agree holds ONE generation in-run, so the
    slug-set flip the live page suffered (46c4e24 re-adding solar-pro-2
    with both looks agreeing) is invisible to the in-run layer and must be
    caught against the previous capture. Same stubbed-urlopen boundary as
    MultiLookCaptureTests; no test touches the network."""

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")

    def capture_with_prev(self, leaderboard_pages, prev_records,
                          **detail_overrides):
        stub = LoudUrlopenStub({
            fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(methodology_html()),
            fetch_aa.URL: flaky(*leaderboard_pages),
            self.DETAIL_URL: lambda: _FakeResponse(
                flight_html(detail_payload(**detail_overrides))),
        })
        sleeps: list = []
        with unittest.mock.patch.object(urllib.request, "urlopen", stub), \
                unittest.mock.patch.object(fetch_aa, "_sleep",
                                           side_effect=sleeps.append,
                                           create=True):
            return fetch_aa.capture(None, None, None, prev_records)

    def flip_pages(self):
        """The reopened issue's live shape: BOTH looks serve solar-pro-2
        (agreeing -- the in-run layer cannot see it) while the previous
        capture's corpus lacks it. Same churned-value shape as
        MultiLookCaptureTests.presence_flip_pages."""
        def page(records):
            return flight_html(json.dumps(
                {"intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
                 "models": records}, separators=(",", ":")))

        host = {"slug": "detail-host-model",
                "intelligenceIndexCostPerTask": "$undefined"}
        solar = {"slug": "solar-pro-2", "name": "Solar Pro 2",
                 "intelligenceIndex": 48.5,
                 "intelligenceIndexCostPerTask": None,
                 "contextWindowTokens": 200000}
        look = [host,
                leaderboard_record(intelligenceIndex=51,
                                   intelligenceIndexCostPerTask=None,
                                   medianOutputTokensPerSecond=120.0),
                solar]
        return page(look), page(look)

    def test_a_quiet_hour_with_a_matching_previous_capture_is_unchanged(self):
        # Threading a matching previous capture through a quiet hour must
        # be byte-invisible: the corpus is exactly the no-lookback
        # capture's and the layer raises nothing.
        pages = [flight_html(look_payload(51))]
        prev = build.merge_captures(
            [{"slug": "detail-host-model",
              "intelligenceIndexCostPerTask": "$undefined"},
             leaderboard_record()],
            [detail_record()])

        without = self.capture_with_prev(pages, None)
        with_prev = self.capture_with_prev(pages, prev)

        self.assertEqual(json.dumps(with_prev.models),
                         json.dumps(without.models))
        self.assertFalse(with_prev.disputed)
        self.assertEqual((with_prev.cross_run.dropped,
                          with_prev.cross_run.readded), ([], []))

    def test_the_live_flip_is_caught_against_the_previous_capture(self):
        prev = [{"slug": "detail-host-model",
                 "intelligenceIndexCostPerTask": "$undefined"},
                leaderboard_record(intelligenceIndex=51,
                                   intelligenceIndexCostPerTask=None,
                                   medianOutputTokensPerSecond=120.0)]
        captured = self.capture_with_prev(self.flip_pages(), prev)

        self.assertTrue(captured.disputed)
        self.assertEqual((captured.cross_run.dropped,
                          captured.cross_run.readded),
                         ([], ["solar-pro-2"]))
        by_slug = {m["slug"]: m for m in captured.models}
        solar = by_slug["solar-pro-2"]
        self.assertEqual(len(solar["genVariants"]), 2)
        self.assertEqual(sum(1 for v in solar["genVariants"] if not v), 1)
        self.assertEqual(solar["intelligenceIndex"], 48.5)
        # The shared models take no previous-generation slot: no
        # genVariants key exists on them at all.
        self.assertNotIn("genVariants", by_slug["fixture-model"])
        self.assertNotIn("genVariants", by_slug["detail-host-model"])


class CrossRunLookbackFlagTests(unittest.TestCase):
    """--cross-run-lookback scopes the layer to the context where the
    working copy of data/aa-raw-models.json IS the previous committed
    capture -- the hourly refresh's checkout of main. Without the flag a
    presence diff is not a dispute; with it the previous capture is read
    before the fetch writes, a missing file is no look-back, and a
    malformed one refuses: it is our own committed artifact, and a parse
    failure is repo damage, not an AA event."""

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")

    def run_main(self, argv, prev_text=None):
        """fetch_aa.main() over a stubbed urlopen, with an optional
        previous capture staged at OUT. -> (stdout, OUT text after the
        run, the SystemExit or None)."""
        agents = flight_html(agent_payload(
            [agent_row(f"Agent - Model {i}") for i in range(5)]))
        stub = LoudUrlopenStub({
            fetch_aa.METHODOLOGY_URL: lambda: _FakeResponse(methodology_html()),
            fetch_aa.URL: lambda: _FakeResponse(
                flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(
                flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(agents),
        })
        old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
               fetch_aa.STAMP)
        argv_saved = sys.argv
        try:
            with tempfile.TemporaryDirectory(prefix=".issue-211b-") as tmp:
                root = pathlib.Path(tmp)
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                if prev_text is not None:
                    fetch_aa.OUT.write_text(prev_text, encoding="utf-8")
                sys.argv = argv
                with unittest.mock.patch.object(
                        urllib.request, "urlopen", stub), \
                        unittest.mock.patch.object(
                            fetch_aa, "_sleep",
                            side_effect=lambda s: None):
                    buffer = io.StringIO()
                    exit_exc = None
                    with contextlib.redirect_stdout(buffer):
                        try:
                            fetch_aa.main()
                        except SystemExit as exc:
                            exit_exc = exc
                    return (buffer.getvalue(),
                            fetch_aa.OUT.read_text(encoding="utf-8"),
                            exit_exc)
        finally:
            sys.argv = argv_saved
            (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
             fetch_aa.STAMP) = old

    def prev_without_fixture(self):
        host = {"slug": "detail-host-model",
                "intelligenceIndexCostPerTask": "$undefined"}
        return json.dumps([host], indent=1)

    def test_without_the_flag_a_presence_diff_is_not_a_dispute(self):
        # The scoping pin: the previous capture sits on disk missing
        # fixture-model, the fresh fetch serves it, and -- with no flag --
        # the corpus stays byte-clean. Drift checks and manual runs must
        # not start disputing against a stale tree.
        stdout, out_text, _exit = self.run_main(
            ["fetch_aa.py"], prev_text=self.prev_without_fixture())
        models = json.loads(out_text)

        self.assertNotIn("cross-run presence", stdout)
        self.assertTrue(all("genVariants" not in m for m in models))

    def test_the_flag_holds_a_presence_diff_as_a_cross_run_dispute(self):
        # Same staged previous capture, flag passed: fixture-model is
        # kept, disputed by presence (two slots, one empty), and the log
        # names it as the layer's own line.
        stdout, out_text, _exit = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"],
            prev_text=self.prev_without_fixture())
        models = json.loads(out_text)

        self.assertIn("cross-run presence", stdout)
        self.assertIn("fixture-model", stdout)
        self.assertEqual(len(models), 2)
        fixture = next(m for m in models
                       if m["slug"] == "fixture-model")
        self.assertEqual(len(fixture["genVariants"]), 2)
        self.assertEqual(sum(1 for v in fixture["genVariants"] if not v), 1)

    def test_a_missing_previous_capture_is_no_lookback(self):
        stdout, out_text, _exit = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"])
        models = json.loads(out_text)

        self.assertNotIn("cross-run presence", stdout)
        self.assertTrue(all("genVariants" not in m for m in models))

    def test_a_malformed_previous_capture_refuses(self):
        # The loader exits guarded BEFORE any fetch writes: the staged
        # malformed text is still the file's content after the run.
        malformed = '{"not": "an array"'
        _stdout, out_text, exit_exc = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"], prev_text=malformed)

        self.assertIsInstance(exit_exc, SystemExit)
        self.assertIn("does not read back as JSON", str(exit_exc))
        self.assertEqual(out_text, malformed)

    def test_a_non_array_previous_capture_refuses(self):
        # Valid JSON that is not the capture's array shape is the same
        # repo-damage class as unparseable JSON: refuse before any fetch
        # writes, leaving the staged file unmodified.
        staged = '{"not": "an array"}'
        _stdout, out_text, exit_exc = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"], prev_text=staged)

        self.assertIsInstance(exit_exc, SystemExit)
        self.assertIn("not a JSON array", str(exit_exc))
        self.assertEqual(out_text, staged)

    def test_a_matching_previous_capture_is_silent(self):
        prev = build.merge_captures(
            [{"slug": "detail-host-model",
              "intelligenceIndexCostPerTask": "$undefined"},
             leaderboard_record()],
            [detail_record()])

        stdout, out_text, exit_exc = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"],
            prev_text=json.dumps(prev, indent=1))
        models = json.loads(out_text)

        self.assertIsNone(exit_exc)
        self.assertNotIn("cross-run presence", stdout)
        self.assertTrue(all("genVariants" not in m for m in models))


if __name__ == "__main__":
    unittest.main()
