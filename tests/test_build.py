import contextlib
import io
import json
import pathlib
import tempfile
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
            self._scroll_divs.append("scroll" in (attrs.get("class") or "").split())
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
    *,
    intelligence: float | None = 51,
    gdpval: float | None = 0.47,
    evaluations: list | None = None,
    parameters: float | None = 27,
    slug: str = "fixture-model",
    open_weights: bool = False,
):
    return {
        "name": "Fixture Model (high)",
        "slug": slug,
        "modelCreatorName": "Fixture Lab",
        "isOpenWeights": open_weights,
        "intelligenceIndex": intelligence,
        # AA reports GDPval as a 0-1 fraction; the page shows it out of 100.
        "gdpvalNormalized": gdpval,
        "parameters": parameters,
        "intelligenceIndexCostPerTask": {
            "cost": {"total": 0.75},
            "evaluations": evaluations
            if evaluations is not None
            else [
                {"slug": "gdpval-aa", "weightedCostPerTask": 0.80},
                {"slug": "scicode", "weightedCostPerTask": 0.24},
            ],
        },
    }


def agent_fixture(
    *,
    label: str = "Fixture Agent - Fixture Model (high)",
    score: float | None = 0.64,
    cost: float | None = 2.5,
    host_slug: str | None = "fixturelab_fixture-model",
    wall_time: float | None = 900.0,
):
    return {
        "id": label,
        "displayLabel": label,
        "agentName": label.split(" - ")[0],
        "hostModelSlug": host_slug,
        "display": {"creator": {"agent": "Fixture Agents", "model": "Fixture Lab"}},
        "indexScore": score,
        "mean": {"costUsd": cost, "agentWallTimeSec": wall_time},
    }


def measured_cost(model, metric) -> float:
    """`capability_cost_per_task` returns None when a component is unmeasured.

    Asserting that first turns "the model dropped off this chart" into a clear
    failure instead of a comparison against None, and narrows the type so the
    assertion below type-checks.
    """
    cost = build.capability_cost_per_task(model, metric)
    assert cost is not None, f"no measured {metric} cost for the fixture"
    return cost


class CapabilityCostTests(unittest.TestCase):
    def test_gdpval_cost_divides_out_the_index_weight_aa_applied(self):
        # AA reports each component's task cost with its Intelligence Index
        # weight already multiplied in, and the components sum to cost.total.
        # 0.80 at a 10% weight is $8.00 of actual measured spend per task.
        model = model_fixture()

        self.assertAlmostEqual(measured_cost(model, "agentic"), 8.0)
        self.assertAlmostEqual(measured_cost(model, "intelligence"), 0.75)

    def test_model_rows_carry_no_coding_pair(self):
        # Coding is the Coding Agent Index now; AA publishes no cost for the
        # leaderboard's codingIndex, so a model row must not claim one.
        self.assertIsNone(build.capability_cost_per_task(model_fixture(), "coding"))
        self.assertIsNone(build.capability_score(model_fixture(), "coding"))

    def test_gdpval_score_is_scaled_to_the_shared_hundred_point_axis(self):
        rows = build.build_rows([model_fixture(gdpval=0.4712)])

        self.assertEqual(rows[0]["metrics"]["agentic"], {"score": 47.12, "cost": 8.0})

    def test_a_missing_gdpval_cost_excludes_only_that_metric(self):
        model = model_fixture(
            evaluations=[{"slug": "scicode", "weightedCostPerTask": 0.24}])

        rows = build.build_rows([model])

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["metrics"]["agentic"])
        self.assertEqual(rows[0]["metrics"]["intelligence"], {"score": 51, "cost": 0.75})

    def test_an_unknown_metric_is_a_programming_error_not_a_silent_none(self):
        with self.assertRaises(ValueError):
            build.capability_cost_per_task(model_fixture(), "nonsense")

    def test_parameter_count_is_carried_for_parameter_efficiency_plot(self):
        rows = build.build_rows([model_fixture(parameters=1.25)])

        self.assertEqual(rows[0]["params"], 1.25)

    def test_nonpositive_parameter_count_is_treated_as_missing(self):
        rows = build.build_rows([model_fixture(parameters=0)])

        self.assertIsNone(rows[0]["params"])


class AgentRowTests(unittest.TestCase):
    def test_score_and_cost_are_taken_from_one_record_without_reweighting(self):
        rows = build.build_agent_rows([agent_fixture()], [model_fixture()])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metrics"]["coding"], {"score": 64.0, "cost": 2.5})
        self.assertEqual(rows[0]["kind"], "agent")
        self.assertEqual(rows[0]["agent"], "Fixture Agent")

    def test_agent_rows_carry_no_model_only_axis(self):
        rows = build.build_agent_rows([agent_fixture()], [model_fixture()])

        self.assertIsNone(rows[0]["metrics"]["intelligence"])
        self.assertIsNone(rows[0]["metrics"]["agentic"])
        self.assertIsNone(rows[0]["params"])

    def test_the_lab_is_the_model_maker_not_the_harness_vendor(self):
        # A Claude Code run on GLM-5.2 files under Z.ai; the lab filter groups
        # by who made the model being measured.
        rows = build.build_agent_rows([agent_fixture()], [model_fixture()])

        self.assertEqual(rows[0]["creator"], "Fixture Lab")

    def test_weights_status_is_inherited_from_the_model_by_slug(self):
        models = [model_fixture(slug="fixture-model", open_weights=True)]

        rows = build.build_agent_rows([agent_fixture()], models)

        self.assertIs(rows[0]["open"], True)

    def test_a_two_segment_provider_prefix_still_resolves(self):
        models = [model_fixture(slug="qwen3-7-plus", open_weights=True)]
        agent = agent_fixture(host_slug="alibaba_cloud_qwen3-7-plus")

        self.assertIs(build.build_agent_rows([agent], models)[0]["open"], True)

    def test_a_model_absent_from_the_leaderboard_is_unknown_not_proprietary(self):
        # Unreleased codenames ("spiffy-blimp350") have no leaderboard row.
        # Defaulting them to proprietary would assert something AA never said.
        agent = agent_fixture(host_slug="meta_spiffy-blimp350")

        self.assertIsNone(build.build_agent_rows([agent], [model_fixture()])[0]["open"])

    def test_a_run_without_a_cost_is_dropped_rather_than_plotted_at_zero(self):
        self.assertEqual(
            build.build_agent_rows([agent_fixture(cost=None)], [model_fixture()]), [])
        self.assertEqual(
            build.build_agent_rows([agent_fixture(cost=0)], [model_fixture()]), [])

    def test_effort_is_split_off_the_label_as_for_models(self):
        rows = build.build_agent_rows([agent_fixture()], [model_fixture()])

        self.assertEqual(rows[0]["base"], "Fixture Agent - Fixture Model")
        self.assertEqual(rows[0]["eff"], "high")


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
            "Coding Agent Index",
            "Coding Agent $ / task",
            "Intelligence Index",
            "Intelligence $ / task",
            "GDPval-AA v2",
            "GDPval $ / task",
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

        # The two captures are different universes sharing one table: coding
        # comes only from agent rows, everything else only from model rows.
        kinds = {row["kind"] for row in payload["rows"]}
        self.assertEqual(kinds, {"model", "agent"})
        for row in payload["rows"]:
            if row["kind"] == "agent":
                self.assertIsNone(row["metrics"]["intelligence"])
                self.assertIsNone(row["metrics"]["agentic"])
            else:
                self.assertIsNone(row["metrics"]["coding"])
        self.assertEqual(
            payload["stats"]["parameterCount"],
            sum(
                row["params"] is not None and row["metrics"]["intelligence"] is not None
                for row in payload["rows"]
            ),
        )

    def test_remote_strings_are_inert_in_the_inline_json_script(self):
        lower = "</script><script>document.documentElement.dataset.auditLower=1</script> __CAPTURED__"
        mixed = "</ScRiPt><ScRiPt>document.documentElement.dataset.auditMixed=1</sCrIpT> __DATA__ / __DATA__"
        upper = "</SCRIPT><SCRIPT>document.documentElement.dataset.auditUpper=1</SCRIPT> __CAPTURED____DATA__"
        ordinary = "".join([
            "ordinary <tag> & 'quotes' \"slashes",
            "\\",
            "\" \n",
            "\u2028",
            "\u2029",
            " __DATA____CAPTURED__",
        ])
        exact = "__DATA__"
        model = model_fixture()
        model.update({
            "name": lower,
            "modelCreatorName": mixed,
            "modelCreatorCountry": upper,
            "licenseName": ordinary,
            "releaseDate": exact,
        })

        with tempfile.TemporaryDirectory(prefix=".issue-6-build-", dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw = root / "models.json"
            agents_raw = root / "coding-agents.json"
            output = root / "frontier-models.html"
            # A second model with NO `name` exercises the shortName fallback,
            # which AA's payload trim made a live path rather than a spare one
            # -- and keeps that path under the same escaping check.
            fallback = dict(model)
            fallback.pop("name")
            fallback["shortName"] = upper
            fallback["slug"] = "fixture-model-2"
            raw.write_text(json.dumps([model, fallback]), encoding="utf-8")
            # Hermetic: without its own agent capture this would build against
            # the committed one, so the escaping check would silently stop
            # covering the half of the payload that comes from agent rows.
            agents_raw.write_text(json.dumps([{
                "id": "audit-agent", "displayLabel": lower, "agentName": mixed,
                "hostModelSlug": "vendor_fixture-model",
                "display": {"creator": {"agent": upper, "model": mixed}},
                "indexScore": 0.64,
                "mean": {"costUsd": 2.5, "agentWallTimeSec": 900.0},
            }]), encoding="utf-8")
            old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                html = output.read_text(encoding="utf-8")
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out

        marker = "const DATA = "
        start = html.index(marker) + len(marker)
        end = html.index(";\n(function(){", start)
        embedded = html[start:end]
        self.assertNotRegex(embedded, r"(?i)</script")

        try:
            payload = json.loads(embedded)
        except json.JSONDecodeError as exc:
            self.fail(f"embedded JSON is invalid: {exc}")
        # Keyed by kind as well as name: the agent fixture deliberately reuses
        # the same hostile label, and a name-only key lets one row shadow the
        # other and silently drop half the assertions.
        rows = {(r["kind"], r["name"]): r for r in payload["rows"]}
        row = rows[("model", lower)]
        self.assertEqual(row["creator"], mixed)
        self.assertEqual(row["lic"], ordinary)
        self.assertEqual(row["rel"], exact)
        # The fallback carries its hostile string through the same escaping.
        self.assertIn(("model", upper), rows)


if __name__ == "__main__":
    unittest.main()
