import contextlib
import io
import json
import unittest
from html.parser import HTMLParser
import build


class ArtifactParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.svg_ids = []
        self.headers = []
        self.scroll_tables = []
        self._scroll_divs = []
        self._in_th = False
        self._hidden_depth = 0
        self._text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "svg":
            self.svg_ids.append(attrs.get("id"))
        elif tag == "div":
            self._scroll_divs.append("scroll" in attrs.get("class", "").split())
        elif tag == "table" and any(self._scroll_divs):
            self.scroll_tables.append(attrs.get("id"))
        elif tag == "th":
            self._in_th = True
            self._text = []
        elif self._in_th and attrs.get("aria-hidden") == "true":
            self._hidden_depth += 1

    def handle_data(self, data):
        if self._in_th and not self._hidden_depth:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self._scroll_divs:
            self._scroll_divs.pop()
        if self._in_th and self._hidden_depth and tag == "span":
            self._hidden_depth -= 1
        if tag == "th" and self._in_th:
            self.headers.append(" ".join("".join(self._text).split()))
            self._in_th = False


def model_fixture(
    *, coding=62, intelligence=51, agentic=47, evaluations=None, parameters=27
):
    return {
        "name": "Fixture Model (high)",
        "modelCreatorName": "Fixture Lab",
        "intelligenceIndex": intelligence,
        "codingIndex": coding,
        "agenticIndex": agentic,
        "totalParameters": parameters,
        "intelligenceIndexCostPerTask": {
            "cost": {"total": 0.75},
            "evaluations": evaluations
            if evaluations is not None
            else [
                {"slug": "terminalbench-v2-1", "weightedCostPerTask": 0.32},
                {"slug": "scicode", "weightedCostPerTask": 0.24},
                {"slug": "gdpval-aa", "weightedCostPerTask": 0.80},
                {"slug": "tau3-banking", "weightedCostPerTask": 0.42},
            ],
        },
    }


class CapabilityCostTests(unittest.TestCase):
    def test_reweights_measured_component_costs_for_each_capability(self):
        model = model_fixture()

        self.assertAlmostEqual(build.capability_cost_per_task(model, "coding"), 2.5)
        self.assertAlmostEqual(build.capability_cost_per_task(model, "agentic"), 3.5)
        self.assertAlmostEqual(build.capability_cost_per_task(model, "intelligence"), 0.75)

    def test_missing_component_cost_excludes_only_that_metric(self):
        model = model_fixture(
            evaluations=[
                {"slug": "terminalbench-v2-1", "weightedCostPerTask": 0.32},
                {"slug": "gdpval-aa", "weightedCostPerTask": 0.80},
                {"slug": "tau3-banking", "weightedCostPerTask": 0.42},
            ]
        )

        rows = build.build_rows([model])

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["metrics"]["coding"])
        self.assertEqual(rows[0]["metrics"]["intelligence"], {"score": 51, "cost": 0.75})
        self.assertEqual(rows[0]["metrics"]["agentic"], {"score": 47, "cost": 3.5})

    def test_model_with_only_a_complete_coding_pair_is_retained(self):
        model = model_fixture(intelligence=None, agentic=None)

        rows = build.build_rows([model])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metrics"]["coding"], {"score": 62, "cost": 2.5})
        self.assertIsNone(rows[0]["metrics"]["intelligence"])
        self.assertIsNone(rows[0]["metrics"]["agentic"])

    def test_total_parameter_count_is_carried_for_parameter_efficiency_plot(self):
        rows = build.build_rows([model_fixture(parameters=1.25)])

        self.assertEqual(rows[0]["params"], 1.25)

    def test_nonpositive_parameter_count_is_treated_as_missing(self):
        rows = build.build_rows([model_fixture(parameters=0)])

        self.assertIsNone(rows[0]["params"])


class GeneratedArtifactTests(unittest.TestCase):
    def test_contains_parameter_chart_in_requested_order_and_accessible_columns(self):
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()
        html = build.OUT.read_text(encoding="utf-8")
        parser = ArtifactParser()
        parser.feed(html)

        # The three cost-axis scatters group first and read against each other;
        # the parameter scatter swaps that axis for model size, so it sits last.
        self.assertEqual(
            parser.svg_ids,
            ["svg-coding", "svg-intelligence", "svg-agentic", "svg-parameters"],
        )
        self.assertEqual(parser.scroll_tables, ["fTable", "tbl"])
        for header in (
            "Coding Index",
            "Coding $ / task",
            "Intelligence Index",
            "Intelligence $ / task",
            "Agentic Index",
            "Agentic $ / task",
            "Parameters",
        ):
            self.assertIn(header, parser.headers)

        marker = "const DATA = "
        start = html.index(marker) + len(marker)
        end = html.index(";\n(function(){", start)
        payload = json.loads(html[start:end])
        self.assertEqual(set(payload["stats"]["metricCounts"]), {"coding", "intelligence", "agentic"})
        self.assertTrue(any(row["metrics"]["coding"] for row in payload["rows"]))
        self.assertTrue(any(row["metrics"]["agentic"] for row in payload["rows"]))
        self.assertTrue(any(row["params"] for row in payload["rows"]))
        self.assertEqual(
            payload["stats"]["parameterCount"],
            sum(
                row["params"] is not None and row["metrics"]["intelligence"] is not None
                for row in payload["rows"]
            ),
        )


if __name__ == "__main__":
    unittest.main()
