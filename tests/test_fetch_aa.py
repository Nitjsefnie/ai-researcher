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


def agent_row(label: str, score: float | None = 0.64,
              cost: float | None = 1.5) -> dict:
    row = {"id": label, "displayLabel": label, "agentName": label.split(" - ")[0]}
    if score is not None:
        row["indexScore"] = score
    row["mean"] = {} if cost is None else {"costUsd": cost}
    return row


def agent_payload(rows: list[dict]) -> str:
    """The coding-agents flight payload interleaves RSC marker strings with the
    row objects, exactly as the extractor must tolerate."""
    # Next.js emits the payload compact; the extractor anchors on that shape.
    body = json.dumps(rows, separators=(",", ":"))[1:-1]
    return '{"rows":[' + body + ',"$L1c"]}'


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

    def test_the_full_table_wins_over_the_highlight_subset(self):
        # The page embeds the ten highlighted rows AND the full table; taking
        # the first array found would silently publish a tenth of the data.
        highlights = agent_payload([agent_row(f"H - {i}") for i in range(10)])
        full = agent_payload([agent_row(f"F - {i}") for i in range(58)])

        got = fetch_aa.coding_agent_rows(highlights + full)

        self.assertEqual(len(got), 58)
        self.assertTrue(all(r["id"].startswith("F - ") for r in got))

    def test_rows_without_a_cost_do_not_count_toward_the_floor(self):
        rows = [agent_row(f"A - {i}", cost=None) for i in range(58)]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertIn("schema changed", str(caught.exception))

    def test_a_collapsed_table_exits_rather_than_publishing_a_stub(self):
        rows = [agent_row(f"A - {i}") for i in range(5)]

        with self.assertRaises(SystemExit) as caught:
            fetch_aa.coding_agent_rows(agent_payload(rows))

        self.assertIn("only 5 rows", str(caught.exception))


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
