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


class FetchHtmlTests(unittest.TestCase):
    def test_cached_file_is_read_instead_of_the_network(self):
        # --html is how you re-extract without hitting AA again.
        path = pathlib.Path(__file__).resolve().parent / "_cached.html"
        path.write_text("<html>cached</html>", encoding="utf-8")
        try:
            self.assertEqual(fetch_aa.fetch_html(str(path)), "<html>cached</html>")
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
