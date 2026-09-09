import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position


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
    def test_the_pinned_version_passes(self):
        payload = f"blah Intelligence Index v{fetch_aa.INDEX_VERSION} blah"

        self.assertEqual(fetch_aa.check_index_version(payload),
                         fetch_aa.INDEX_VERSION)

    def test_a_bumped_version_exits_naming_both_versions(self):
        # v4.2 rebalanced the weights without changing a single field name --
        # undetectable from the data, which is the whole reason for the pin.
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_index_version("Intelligence Index v9.9")

        message = str(caught.exception)
        self.assertIn("v9.9", message)
        self.assertIn(f"v{fetch_aa.INDEX_VERSION}", message)
        self.assertIn("methodology", message)

    def test_a_payload_with_no_version_at_all_exits(self):
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_index_version("nothing here")

        self.assertIn("page structure changed", str(caught.exception))


class CostBreakdownTests(unittest.TestCase):
    def test_a_consistent_breakdown_passes_and_is_counted(self):
        models = [costed("A"), costed("B"), {"name": "unpriced"}]

        self.assertEqual(fetch_aa.check_cost_breakdown(models), 2)

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
        # The leaderboard kept intelligenceIndexCostPerTask.cost and dropped
        # .evaluations. A key-level merge leaves the stub in place and the
        # GDPval axis silently loses its cost.
        base = [{"slug": "a",
                 "intelligenceIndexCostPerTask": {"cost": {"total": 1.0}}}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
            "cost": {"total": 1.0},
            "evaluations": [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4}]}}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertEqual(
            got[0]["intelligenceIndexCostPerTask"]["evaluations"],
            [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4}])
        self.assertEqual(
            got[0]["intelligenceIndexCostPerTask"]["cost"]["total"], 1.0)

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
        # --html is how you re-extract without hitting AA again.
        path = pathlib.Path(__file__).resolve().parent / "_cached.html"
        path.write_text("<html>cached</html>", encoding="utf-8")
        try:
            self.assertEqual(fetch_aa.fetch_html(str(path)), "<html>cached</html>")
            # The second capture reads its own cache through the same helper.
            self.assertEqual(
                fetch_aa.fetch_html(str(path), fetch_aa.AGENTS_URL),
                "<html>cached</html>")
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
