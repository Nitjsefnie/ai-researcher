import contextlib
import datetime
import html
import io
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import unittest
from html.parser import HTMLParser
import build
import page_format


def _build_in_temp_dir() -> str:
    """Run build.main() with OUT redirected into a temp dir and return the
    page text, leaving the real out/frontier-models.html untouched (#114).

    The temp dir lives under build.ROOT because build.main() prints
    OUT.relative_to(ROOT) and would raise on a page outside it -- the same
    convention the stamp and escaping tests use for their capture paths.
    """
    with tempfile.TemporaryDirectory(
            prefix=".issue-114-build-", dir=build.ROOT) as tmp:
        page = pathlib.Path(tmp) / "frontier-models.html"
        saved = build.OUT
        build.OUT = page
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                build.main()
        finally:
            build.OUT = saved
        return page.read_text(encoding="utf-8")


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


def route_pair() -> tuple[dict, dict]:
    """(leaderboard, detail) records for one model, shaped as AA's two routes
    split one record: the leaderboard kept shortName, context and a FLATTENED
    cost total, while the detail page carries name, licence, the parameter
    count and the full cost object with its per-evaluation breakdown. Shared
    values agree exactly; contextWindowTokens is "$undefined" on the
    leaderboard route -- AA's encoding of an absent field -- where the detail
    route has measured it. intelligenceIndexEvaluations is a shared LIST: the
    real corpus ships the key on 678/679 records, 502 empty arrays and 176
    populated in this branch's base capture (177 populated at main HEAD), so
    the walk's list limb runs on every live capture -- the fixture still
    carries elements rather than empty arrays because elements pin the limb
    deterministically, where an empty list walks nothing and proves nothing."""
    return (
        {
            "slug": "fixture-model",
            "shortName": "Fixture Model (high)",
            "isOpenWeights": False,
            "intelligenceIndex": 51,
            "intelligenceIndexCostPerTask": 0.75,
            "contextWindowTokens": "$undefined",
            "intelligenceIndexEvaluations": ["gdpval-aa", "scicode"],
        },
        {
            "slug": "fixture-model",
            "name": "Fixture Model (high)",
            "isOpenWeights": False,
            "intelligenceIndex": 51,
            "intelligenceIndexCostPerTask": {
                "cost": {"total": 0.75},
                "evaluations": [
                    {"slug": "gdpval-aa", "weightedCostPerTask": 0.30},
                    {"slug": "scicode", "weightedCostPerTask": 0.45},
                ],
            },
            "contextWindowTokens": 400000,
            "intelligenceIndexEvaluations": ["gdpval-aa", "scicode"],
        },
    )


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

    def test_a_bare_numeric_cost_is_the_total(self):
        # The leaderboard's flattened shape, which the one model the detail
        # route cannot describe is left with.
        model = model_fixture()
        model["intelligenceIndexCostPerTask"] = 0.75

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
        html = _build_in_temp_dir()
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
        # Template markers deliberately stay OUT of these strings: since #97
        # the captured strings also render into the STATIC table bodies,
        # where a marker would be spliced by a later substitution -- so a
        # build carrying one now refuses outright
        # (test_a_template_marker_in_a_captured_string_refuses_the_build),
        # and a marker here would die before the payload assertions this
        # test exists for ever ran.
        lower = "</script><script>document.documentElement.dataset.auditLower=1</script>"
        mixed = "</ScRiPt><ScRiPt>document.documentElement.dataset.auditMixed=1</sCrIpT>"
        upper = "</SCRIPT><SCRIPT>document.documentElement.dataset.auditUpper=1</SCRIPT>"
        ordinary = "".join([
            "ordinary <tag> & 'quotes' \"slashes",
            "\\",
            "\" \n",
            "\u2028",
            "\u2029",
        ])
        exact = "2026-09-30"
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


class StaticTableRenderTests(unittest.TestCase):
    """Issue #97: build.py renders both table bodies into the page.

    The static rows must be the page's own default-state render -- the same
    cells the JS `fillTable`/`fillFrontiers` produce, from the same
    formatters -- so the browser drift test holds them equal cell-for-cell
    at load time. These unit tests pin the pieces exactly: escaping,
    em-dashes, tags, V8-exact rounding, the default sort and the marker
    guard that refuses to splice a captured string into the template.
    """

    def test_a_full_row_renders_the_exact_cells_the_page_renders(self):
        rows = build.build_rows([model_fixture()])
        frontier, main = build.render_static_tbodies(rows)

        self.assertEqual(frontier, (
            '<tr><td>Intelligence Index</td><td class="name">'
            'Fixture Model (high)</td><td>Fixture Lab</td>'
            '<td class="n">51.0</td><td class="n">$0.750</td>'
            '<td class="n">$0.0147</td>'
            '<td><span class="tag">proprietary</span></td></tr>'
            '<tr><td>GDPval-AA v2</td><td class="name">Fixture Model (high)</td>'
            '<td>Fixture Lab</td><td class="n">47.0</td><td class="n">$8.00</td>'
            '<td class="n">$0.1702</td>'
            '<td><span class="tag">proprietary</span></td></tr>'
        ))
        self.assertEqual(main, (
            '<tr><td class="name">Fixture Model (high) </td><td>Fixture Lab</td>'
            '<td class="n">—</td><td class="n">—</td>'
            '<td class="n">51.0 <span class="tag f">frontier</span></td>'
            '<td class="n">$0.750</td>'
            '<td class="n">27B <span class="tag f">parameter frontier</span></td>'
            '<td class="n">47.0 <span class="tag f">frontier</span></td>'
            '<td class="n">$8.00</td>'
            '<td class="n">—</td><td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td><td>—</td><td>proprietary</td></tr>'
        ))

    def test_an_agent_row_renders_em_dashes_for_the_model_only_columns(self):
        rows = build.build_agent_rows([agent_fixture()], [model_fixture()])
        frontier, main = build.render_static_tbodies(rows)

        self.assertEqual(frontier, (
            '<tr><td>Coding Agent Index</td><td class="name">'
            'Fixture Agent - Fixture Model (high)</td><td>Fixture Lab</td>'
            '<td class="n">64.0</td><td class="n">$2.50</td>'
            '<td class="n">$0.0391</td>'
            '<td><span class="tag">proprietary</span></td></tr>'
        ))
        self.assertEqual(main, (
            '<tr><td class="name">Fixture Agent - Fixture Model (high) </td>'
            '<td>Fixture Lab</td>'
            '<td class="n">64.0 <span class="tag f">frontier</span></td>'
            '<td class="n">$2.50</td>'
            '<td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td>'
            '<td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td><td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td><td>—</td><td>proprietary</td></tr>'
        ))

    def test_missing_values_render_as_the_em_dash(self):
        # A model with no parameters, prices, speed, context or release date:
        # every absent column renders the page's em dash -- never blank, and
        # the parameters cell is fmtParams(params) regardless of the
        # intelligence pair, so only a truly absent count renders the dash.
        model = model_fixture(intelligence=None, gdpval=0.9, parameters=None)
        rows = build.build_rows([model])
        _, main = build.render_static_tbodies(rows)

        self.assertEqual(main, (
            '<tr><td class="name">Fixture Model (high) </td><td>Fixture Lab</td>'
            '<td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td>'
            '<td class="n">90.0 <span class="tag f">frontier</span></td>'
            '<td class="n">$8.00</td>'
            '<td class="n">—</td><td class="n">—</td><td class="n">—</td>'
            '<td class="n">—</td><td>—</td><td>proprietary</td></tr>'
        ))

    def test_to_fixed_matches_v8_on_exact_ties(self):
        # toFixed rounds the number's exact binary value, and an exact tie
        # picks the LARGER candidate -- 2.25 and 0.25 are exact binary values
        # whose tie goes up, while 2.675 is really 2.67499999... and rounds
        # down. Decimal(float) reproduces the exact binary expansion.
        self.assertEqual(page_format.js_to_fixed(2.25, 1), "2.3")
        self.assertEqual(page_format.js_to_fixed(0.25, 1), "0.3")
        self.assertEqual(page_format.js_to_fixed(2.675, 2), "2.67")
        self.assertEqual(page_format.js_to_fixed(51, 1), "51.0")
        self.assertEqual(page_format.js_to_fixed(0.75, 3), "0.750")
        self.assertEqual(page_format.js_to_fixed(8.0, 2), "8.00")

    def test_the_number_and_context_formatters_cover_their_small_value_branches(self):
        # js_number's exponent branch, fmt_params' sub-billion branch and
        # fmt_ctx's sub-thousand branch: the shapes the committed corpus
        # happens not to carry, pinned so the branches stay V8-exact.
        self.assertEqual(page_format.js_number(1.5e-05), "0.000015")
        self.assertEqual(page_format.fmt_params(0.5), "500M")
        self.assertEqual(page_format.fmt_ctx(500), "500")
        self.assertEqual(page_format.fmt_ctx(1_500_000), "1.5M")

    def test_js_number_matches_v8_up_to_its_documented_boundaries(self):
        # String(number) parity is contractual only inside 1e-6 <= |v| < 1e21,
        # the range the page's prices, speeds and parameter counts can reach.
        # AT both edges the two spellings still agree; outside them they
        # diverge on purpose -- Python reaches for e-notation at 1e-4 where
        # V8 holds out until 1e-6, and V8 goes exponential at 1e21 while
        # js_number keeps spelling digits -- and js_number's docstring
        # carries the rationale. These pins turn any change to that contract
        # into a deliberate diff rather than a silent spelling drift.
        self.assertEqual(page_format.js_number(1e-06), "0.000001")
        self.assertEqual(page_format.js_number(1e-07), "0.0000001")  # V8: "1e-7"
        self.assertEqual(page_format.js_number(1e20), "100000000000000000000")
        self.assertEqual(
            page_format.js_number(1e21), "1000000000000000000000")  # V8: "1e+21"

    def test_a_vendor_retired_model_carries_its_tag_in_the_static_row(self):
        model = model_fixture()
        model["deprecated"] = True
        rows = build.build_rows([model])
        _, main = build.render_static_tbodies(rows)

        self.assertIn(
            '<td class="name">Fixture Model (high) '
            '<span class="tag">vendor-retired</span></td>', main)

    def test_a_hostile_name_reaches_the_static_row_escaped(self):
        model = model_fixture()
        hostile = 'P|ipe <script>x</script> & "q"'
        model["name"] = hostile
        rows = build.build_rows([model])
        _, main = build.render_static_tbodies(rows)

        self.assertIn("&lt;script&gt;", main)
        self.assertNotIn("<script>", main)
        self.assertIn("&amp;", main)
        self.assertNotIn(hostile, main)

    def test_the_default_sort_is_intelligence_descending_missing_last(self):
        top = model_fixture(intelligence=70, slug="top")
        top["name"] = "Top Model (high)"
        twin = model_fixture(intelligence=70, slug="twin")
        twin["name"] = "Twin Model (high)"
        mid = model_fixture(intelligence=50, slug="mid")
        mid["name"] = "Mid Model (high)"
        gap = model_fixture(intelligence=None, gdpval=0.9, slug="gap")
        gap["name"] = "Gap Model"
        rows = build.build_rows([top, twin, mid, gap])
        rows.reverse()  # tie order now CONTRADICTS the name order
        rows = [build.build_agent_rows([agent_fixture()], [])[0]] + rows
        _, main = build.render_static_tbodies(rows)

        names = re.findall(r'<td class="name">(.*?)</td>', main)
        self.assertEqual(names, [
            "Twin Model (high) ", "Top Model (high) ",  # the preserved tie
            "Mid Model (high) ",                        # 50 below 70
            "Fixture Agent - Fixture Model (high) ",    # no ii: union order
            "Gap Model ",                               # ...payload order
        ])

    def test_a_template_marker_in_a_captured_string_refuses_the_build(self):
        # A captured string carrying a template marker would be spliced by
        # the payload substitution that runs after the tbody replacement --
        # the build must fail red rather than splice it into the page.
        model = model_fixture()
        model["name"] = "Marker __DATA__ Model (high)"
        with tempfile.TemporaryDirectory(prefix=".issue-97-build-",
                                         dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw, agents_raw = root / "models.json", root / "coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps([model]), encoding="utf-8")
            # the coding axis needs a row of its own, or the empty-axis
            # guard fires before the marker guard ever runs
            agents_raw.write_text(json.dumps([{
                "id": "marker-agent", "displayLabel": "Marker Agent (high)",
                "agentName": "Marker Agent",
                "hostModelSlug": "vendor_fixture-model",
                "display": {"creator": {"agent": "Marker Agents",
                                        "model": "Fixture Lab"}},
                "indexScore": 0.64,
                "mean": {"costUsd": 2.5, "agentWallTimeSec": 900.0},
            }]), encoding="utf-8")
            old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
                with self.assertRaises(SystemExit) as raised:
                    with contextlib.redirect_stdout(io.StringIO()):
                        build.main()
                self.assertIn("__DATA__", str(raised.exception))
                self.assertFalse(output.exists())
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out


class CaptureStampTests(unittest.TestCase):
    """Issue #40: the capture stamp reaches the page unescaped.

    build.py reads data/captured-at.txt and splices the value into four
    template sinks -- the header, the method grid, and the copy-as-Markdown
    and copy-as-JSON clips -- besides the inline payload's stats, all
    downstream of the single read at the top of main(). One guard at that
    read accepts exactly what scripts/fetch_aa.py writes -- a single ISO
    date -- and refuses everything else: a stamp-less capture (issue #64)
    and undecodable bytes included, with the today-fallback surviving only
    for a data directory that holds no capture at all.
    """

    def build_with_stamp(self, stamp_text: str | bytes | None) -> str:
        """Build a hermetic capture whose stamp file holds `stamp_text`.

        None leaves the stamp file absent -- a capture that lost its stamp
        (issue #64). Bytes are written raw, so a non-UTF-8 stamp is
        expressible. Returns the rendered HTML; a stamp the guard refuses
        raises SystemExit out of build.main() for the refusal tests to
        assert on.
        """
        with tempfile.TemporaryDirectory(prefix=".issue-40-build-", dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw = root / "aa-raw-models.json"
            agents_raw = root / "aa-raw-coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps([model_fixture()]), encoding="utf-8")
            agents_raw.write_text(json.dumps([agent_fixture()]), encoding="utf-8")
            stamp = root / "captured-at.txt"
            if isinstance(stamp_text, bytes):
                stamp.write_bytes(stamp_text)
            elif stamp_text is not None:
                stamp.write_text(stamp_text, encoding="utf-8")
            old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                return output.read_text(encoding="utf-8")
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out

    def test_a_stamp_in_the_written_format_builds_and_reaches_the_page_unmodified(self):
        # scripts/fetch_aa.py writes exactly date.today().isoformat() + "\n";
        # the guard must accept that shape untouched, and the page must carry
        # the stamp through every sink it feeds. Whitespace padding around the
        # date is the reader's strip() tolerance, held open because the
        # accepted charset (digits and hyphens) cannot carry an attack.
        for stamp_text in ("2026-09-29\n", "  2026-09-29  "):
            with self.subTest(stamp_text=stamp_text):
                html = self.build_with_stamp(stamp_text)

                self.assertIn("captured 2026-09-29</div>", html)
                self.assertIn('<div class="v">2026-09-29</div>', html)
                self.assertIn('"captured":"2026-09-29"', html)
                # The copy clips carry the same value into their JS string and
                # Markdown contexts -- the two sinks the first pin missed.
                self.assertIn('source:"artificialanalysis.ai",captured:"2026-09-29"', html)
                self.assertIn("captured 2026-09-29.", html)

    def test_a_markup_stamp_is_refused_naming_file_format_and_content(self):
        # The stamp lands in HTML text nodes and JS string literals; markup in
        # it would execute when the page opens.
        with self.assertRaises(SystemExit) as raised:
            self.build_with_stamp("2026-09-29<script>alert(1)</script>\n")

        message = str(raised.exception)
        self.assertIn("captured-at.txt", message)
        self.assertIn("YYYY-MM-DD", message)
        self.assertIn("<script>alert(1)</script>", message)

    def test_a_payload_placeholder_stamp_is_refused_naming_file_format_and_content(self):
        # __DATA__ in the stamp would be replaced by the JSON payload itself,
        # splicing the payload (quotes included) out of its template slot.
        with self.assertRaises(SystemExit) as raised:
            self.build_with_stamp("__DATA__")

        message = str(raised.exception)
        self.assertIn("captured-at.txt", message)
        self.assertIn("YYYY-MM-DD", message)
        self.assertIn("__DATA__", message)

    def test_an_empty_stamp_file_is_refused(self):
        # fetch_aa.py never writes an empty stamp, and the missing-file
        # fallback must not swallow a present-but-empty one: refusing states
        # the capture is broken instead of relabelling the page with a guess.
        with self.assertRaises(SystemExit) as raised:
            self.build_with_stamp("")

        message = str(raised.exception)
        self.assertIn("captured-at.txt", message)
        self.assertIn("YYYY-MM-DD", message)
        self.assertIn("found ''", message)

    def test_near_miss_date_shapes_are_refused(self):
        # The writer emits a zero-padded ISO date only; every near-miss means
        # the file was not written by fetch_aa.py and must fall.
        for stamp_text, why in (
            ("2026-9-29", "unpadded month"),
            ("20260929", "compact ISO"),
            ("29/09/2026", "reordered with slashes"),
            ("2026-W39-4", "ISO week date"),
            ("2026-13-99", "date-shaped but not a calendar date"),
            ("2026-09-29\n2026-09-29", "two stamp lines"),
            ("  \n", "whitespace-only, strips to empty"),
        ):
            with self.subTest(stamp_text=stamp_text, why=why):
                with self.assertRaises(SystemExit) as raised:
                    self.build_with_stamp(stamp_text)

                self.assertIn("YYYY-MM-DD", str(raised.exception))

    def test_a_capture_without_its_stamp_is_refused_not_relabelled_with_today(self):
        # Issue #64: fetch_aa.py writes the stamp beside the capture on every
        # capture, so capture data without a stamp is a capture that lost it,
        # not a pre-stamp checkout -- falling back to today would relabel the
        # page with the build date, silently.
        with self.assertRaises(SystemExit) as raised:
            self.build_with_stamp(None)

        message = str(raised.exception)
        self.assertIn("captured-at.txt", message)
        self.assertIn("aa-raw-models.json", message)
        self.assertIn("fetch_aa.py", message)

    def test_a_data_directory_without_capture_data_still_falls_back_to_today(self):
        # The surviving fallback arm, pinned: with no capture input beside the
        # stamp there is no capture to relabel, so a genuinely empty
        # (pre-stamp) data directory builds with today's date. Unreachable
        # through main(), which reads the capture inputs before the stamp --
        # which is exactly why the old fallback could only ever mask a lost
        # stamp (issue #64).
        with tempfile.TemporaryDirectory(prefix=".issue-64-build-", dir=build.ROOT) as tmp:
            stamp = pathlib.Path(tmp) / "captured-at.txt"

            self.assertEqual(
                build.read_capture_stamp(stamp), datetime.date.today().isoformat()
            )

    def test_non_utf8_stamp_bytes_get_the_designed_refusal(self):
        # read_text(encoding="utf-8") would raise UnicodeDecodeError ahead of
        # the guard's message -- still fail-closed, but a traceback instead of
        # the designed refusal naming file, format, and offending content.
        with self.assertRaises(SystemExit) as raised:
            self.build_with_stamp(b"2026-09-29 \xff\xfe<\x00script\x00>")

        message = str(raised.exception)
        self.assertIn("captured-at.txt", message)
        self.assertIn("YYYY-MM-DD", message)
        self.assertIn("\\xff", message)


class EmptyAxisGuardTests(unittest.TestCase):
    """Issues #54 + #60: the guard refusing a capture that leaves a rendered
    axis with nothing on it.

    The page renders FOUR axes -- coding, intelligence and agentic against
    their measured cost per task, plus parameters against the Intelligence
    Index -- and an emptied scatter reads as "nothing qualifies" rather than
    "the pipeline broke" (the guard's own comment in build.py). One pin per
    axis: a capture whose rows carry no pair for that axis is refused naming
    it, and the refusal leaves no page behind to publish. The parameters pin
    uses the pre-rename capture shape (`totalParameters`, which AA renamed to
    `parameters`) as its empty input: a stale capture must fail red and force
    a re-capture, never be resuscitated by a reader fallback (the rename is
    fetch_aa.py's gap-fill job).
    """

    # The stamp fetch_aa.py writes, so a refusal below can only come from the
    # axis guard and not from the stamp guard that runs ahead of it.
    STAMP = "2026-09-29\n"

    @contextlib.contextmanager
    def capture(self, models, agents):
        """A hermetic capture of the given model/agent records.

        Yields the output path inside the live temp directory (so a refusal
        test can assert nothing was written to it) and restores the module
        paths in `finally`, the same redirection convention the stamp and
        escaping tests use.
        """
        with tempfile.TemporaryDirectory(prefix=".issue-54-build-", dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            raw = root / "aa-raw-models.json"
            agents_raw = root / "aa-raw-coding-agents.json"
            output = root / "frontier-models.html"
            raw.write_text(json.dumps(models), encoding="utf-8")
            agents_raw.write_text(json.dumps(agents), encoding="utf-8")
            (root / "captured-at.txt").write_text(self.STAMP, encoding="utf-8")
            old_raw, old_agents, old_out = build.RAW, build.AGENTS_RAW, build.OUT
            try:
                build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, output
                yield output
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = old_raw, old_agents, old_out

    @staticmethod
    def run_build():
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()

    @staticmethod
    def payload_of(output: pathlib.Path) -> dict:
        html = output.read_text(encoding="utf-8")
        marker = "const DATA = "
        start = html.index(marker) + len(marker)
        end = html.index(";\n(function(){", start)
        return json.loads(html[start:end])

    def test_a_capture_with_no_coding_pair_is_refused_naming_coding(self):
        # The agent record lost its cost half: `indexScore` without
        # `mean.costUsd` is dropped by the extractor, so no row renders on the
        # coding chart. The three metric axes are enumerated from the model
        # side too, but coding comes only from agent rows.
        with self.capture([model_fixture()], [agent_fixture(cost=None)]) as output:
            with self.assertRaises(SystemExit) as raised:
                self.run_build()

            self.assertIn("no rows carry a score/cost pair for: coding", str(raised.exception))
            self.assertFalse(output.exists(), "refusal still wrote the page")

    def test_a_capture_with_no_intelligence_pair_is_refused_naming_intelligence(self):
        # A model record with no intelligenceIndex. The refusal also names
        # parameters once the guard enumerates all four axes -- the parameters
        # chart plots the Intelligence Index, so an intelligence-less capture
        # empties that axis too -- but the pin holds the guard only to naming
        # THIS axis, the behavior that predates the four-axis enumeration.
        with self.capture([model_fixture(intelligence=None)], [agent_fixture()]) as output:
            with self.assertRaises(SystemExit) as raised:
                self.run_build()

            message = str(raised.exception)
            self.assertIn("no rows carry a score/cost pair for: intelligence", message)
            self.assertFalse(output.exists(), "refusal still wrote the page")

    def test_a_capture_with_no_agentic_pair_is_refused_naming_agentic(self):
        # A model record with no GDPval measurement. Intelligence and the
        # parameter count survive, so agentic is the only axis named.
        with self.capture([model_fixture(gdpval=None)], [agent_fixture()]) as output:
            with self.assertRaises(SystemExit) as raised:
                self.run_build()

            self.assertIn("no rows carry a score/cost pair for: agentic", str(raised.exception))
            self.assertFalse(output.exists(), "refusal still wrote the page")

    def test_a_capture_with_no_parameters_is_refused_naming_parameters(self):
        # Issue #60, in the exact shape it was reproduced: a stale capture in
        # AA's pre-rename shape, where the parameter count rode `totalParameters`.
        # The row is otherwise fully measured, so the three metric axes stay
        # alive and parameters is the only axis named -- the refusal must come
        # from the guard, not from a reader quietly falling back to the old
        # field, which would publish a chart that looks fine and is empty.
        stale = model_fixture()
        del stale["parameters"]
        stale["totalParameters"] = 27
        with self.capture([stale], [agent_fixture()]) as output:
            with self.assertRaises(SystemExit) as raised:
                self.run_build()

            self.assertIn("no rows carry a score/cost pair for: parameters", str(raised.exception))
            self.assertFalse(output.exists(), "refusal still wrote the page")

    def test_a_fully_measured_capture_builds_and_names_all_four_axes_nonzero(self):
        # The healthy control: the guard enumerates the same stats the page
        # renders, so a fully measured capture must build -- and its payload
        # must show every rendered axis nonzero, the exact numbers the guard
        # reads. (One model row carrying intelligence + gdpval + parameters,
        # one agent row carrying the coding pair.)
        with self.capture([model_fixture()], [agent_fixture()]) as output:
            self.run_build()

            stats = self.payload_of(output)["stats"]
            self.assertEqual(
                stats["metricCounts"], {"coding": 1, "intelligence": 1, "agentic": 1})
            self.assertEqual(stats["parameterCount"], 1)


class RouteAgreementTests(unittest.TestCase):
    """Issue #44: the page's cross-route agreement claim, enforced at capture.

    The page footer states the leaderboard route and the model detail route
    "agree exactly on every value they share"; the gap-fill merge
    (scripts/fetch_aa.py merge_captures) keeps the leaderboard's copy of any
    shared value, so only a check run BEFORE the merge can see a divergence.
    build.check_route_agreement is that check -- scripts/fetch_aa.py calls it
    between loading the two routes and the merge -- and these pins hold it to:
    exact recursive value equality over the parsed structures, every
    divergence collected and raised in one message naming model slug, field
    path and both values, "$undefined" read as absent (a field absent on one
    route is not shared), the leaderboard's flattened cost scalar compared
    against the detail object's cost.total -- the reshape the merge itself
    applies, symmetrically in whichever direction the shapes sit -- and
    shared lists walked element-wise with length mismatches refused at the
    field.
    """

    def test_agreeing_routes_pass_and_the_comparison_ran_non_vacuously(self):
        # The healthy control. The comparison's own count of compared values
        # is the liveness oracle: 6 means it descended the shared record --
        # slug, isOpenWeights, intelligenceIndex, the flattened 0.75 against
        # the detail object's cost.total, and both elements of the shared
        # list -- and skipped only what one route does not carry:
        # contextWindowTokens ($undefined is absent, not a disagreeing
        # value), the detail-only evaluations and name/licence/parameter
        # fields, and the two single-route models (the detail host, which has
        # no row on its own page, and a detail-only record, which the merge
        # would drop).
        leaderboard, detail_route = route_pair()
        leaderboard = [
            leaderboard, {"slug": "detail-host-model", "shortName": "Host Model"}]
        detail_route = [detail_route, {"slug": "detail-only-model", "name": "Detail Only"}]

        compared = build.check_route_agreement(leaderboard, detail_route)

        self.assertEqual(compared, 6)

    def test_a_leaderboard_value_that_diverges_fails_naming_model_field_and_both_values(self):
        # One delta from the healthy pair: the leaderboard's copy moves.
        leaderboard, detail_route = route_pair()
        leaderboard["intelligenceIndex"] = 52

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("1 shared value", message)
        self.assertIn(
            "fixture-model: intelligenceIndex: leaderboard 52, detail 51",
            message)

    def test_the_detail_value_being_the_odd_one_fails_identically(self):
        # The same one delta, carried by the other route: symmetric in which
        # side is wrong.
        leaderboard, detail_route = route_pair()
        detail_route["intelligenceIndex"] = 52

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("1 shared value", message)
        self.assertIn(
            "fixture-model: intelligenceIndex: leaderboard 51, detail 52",
            message)

    def test_a_divergence_behind_the_flattened_cost_scalar_fails_at_its_field(self):
        # One delta, nested: the detail route's cost.total moves while the
        # leaderboard's flattened scalar stays. The canonicalized comparison
        # (scalar against cost.total) must catch it, and the divergence line
        # names the logical field path with the two compared values.
        leaderboard, detail_route = route_pair()
        detail_route["intelligenceIndexCostPerTask"]["cost"]["total"] = 0.99

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("1 shared value", message)
        self.assertIn(
            "fixture-model: intelligenceIndexCostPerTask.cost.total: "
            "leaderboard 0.75, detail 0.99", message)

    def test_a_divergent_element_of_a_shared_list_fails_at_its_indexed_path(self):
        # One delta: element [1] of the shared list moves on the detail side.
        # The walk must compare lists element-wise and name the divergence at
        # its indexed path -- not as one whole-list blob.
        leaderboard, detail_route = route_pair()
        detail_route["intelligenceIndexEvaluations"][1] = "terminal-bench-v4-0"

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("1 shared value", message)
        self.assertIn(
            "fixture-model: intelligenceIndexEvaluations[1]: "
            "leaderboard 'scicode', detail 'terminal-bench-v4-0'", message)

    def test_shared_lists_of_different_lengths_are_refused_at_the_field(self):
        # One delta: the detail route's copy of the shared list loses an
        # element. A shorter list is not a prefix -- element-wise comparison
        # would silently skip the tail -- so the length mismatch is the
        # divergence, named at the field itself.
        leaderboard, detail_route = route_pair()
        detail_route["intelligenceIndexEvaluations"] = ["gdpval-aa"]

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("1 shared value", message)
        self.assertIn(
            "fixture-model: intelligenceIndexEvaluations: "
            "leaderboard ['gdpval-aa', 'scicode'], detail ['gdpval-aa']",
            message)

    def test_the_cost_scalar_on_the_detail_side_is_canonicalized_symmetrically(self):
        # The mirror of the flattened-scalar pin: the LEADERBOARD carries the
        # cost object (total 0.80) while the detail route carries the bare
        # scalar. The canonicalization is shape-driven, not side-driven --
        # the same reshape applies with the routes swapped. The mirror-healthy
        # pair (equal totals, shapes swapped) passes with the same compared
        # count as the healthy control; the delta below moves exactly one
        # value from it.
        leaderboard, detail_route = route_pair()
        detail_route["intelligenceIndexCostPerTask"] = 0.80
        leaderboard["intelligenceIndexCostPerTask"] = {
            "cost": {"total": 0.80},
            "evaluations": [
                {"slug": "gdpval-aa", "weightedCostPerTask": 0.30},
                {"slug": "scicode", "weightedCostPerTask": 0.50},
            ],
        }

        self.assertEqual(
            build.check_route_agreement([leaderboard], [detail_route]), 6)

        detail_route["intelligenceIndexCostPerTask"] = 0.75

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("1 shared value", message)
        self.assertIn(
            "fixture-model: intelligenceIndexCostPerTask.cost.total: "
            "leaderboard 0.8, detail 0.75", message)

    def test_every_divergence_is_collected_before_the_raise(self):
        # Two shared fields diverge: one raise, both listed, in a stable
        # (sorted) order.
        leaderboard, detail_route = route_pair()
        leaderboard["intelligenceIndex"] = 52
        leaderboard["isOpenWeights"] = True

        with self.assertRaises(SystemExit) as raised:
            build.check_route_agreement([leaderboard], [detail_route])

        message = str(raised.exception)
        self.assertIn("2 shared value", message)
        score_line = "fixture-model: intelligenceIndex: leaderboard 52, detail 51"
        weights_line = "fixture-model: isOpenWeights: leaderboard True, detail False"
        self.assertIn(score_line, message)
        self.assertIn(weights_line, message)
        self.assertLess(message.index(score_line), message.index(weights_line))


class SplitEffortTests(unittest.TestCase):
    """Issue #47: what `split_effort` may strip, pinned before speeding it up.

    AA encodes the effort knob in the model name and there is no field for it
    (AGENTS.md "Effort levels"), so the strip is load-bearing: only the effort
    component may go -- `(Adaptive Reasoning, Max Effort)` keeps its config
    list -- while `(Reasoning)`, `(Non-reasoning)` and date snapshots like
    `(Jan '25)` identify genuinely different models and must survive. Every
    expected pair below was read off the pre-fix implementation, so these
    pins pass on main and must keep passing after it is replaced.
    """

    def test_only_the_effort_component_is_stripped_from_a_config_list(self):
        # The AGENTS.md example verbatim: the effort clause goes, the rest of
        # the parenthetical stays.
        self.assertEqual(
            build.split_effort("Model (Adaptive Reasoning, Max Effort)"),
            ("Model (Adaptive Reasoning)", "max"))

    def test_reasoning_marks_survive(self):
        # A reasoning marker names a different model, not a setting of one.
        for suffix, why in ((" (Reasoning)", "reasoning"),
                            (" (Non-reasoning)", "non-reasoning")):
            with self.subTest(why=why):
                self.assertEqual(
                    build.split_effort("Model" + suffix), ("Model" + suffix, None))

    def test_a_date_snapshot_survives(self):
        self.assertEqual(
            build.split_effort("Model (Jan '25)"), ("Model (Jan '25)", None))

    def test_every_bare_effort_level_is_stripped_as_the_label(self):
        for level in ("minimal", "low", "medium", "high", "xhigh", "max"):
            for written in (level, level + " effort", level.upper(),
                            level.capitalize() + " EFFORT"):
                with self.subTest(level=level, written=written):
                    self.assertEqual(
                        build.split_effort(f"Model ({written})"),
                        ("Model", level))

    def test_an_all_effort_group_disappears_whole(self):
        # Every part of the parenthetical is an effort word, so nothing is
        # kept and the group goes with them; the label is the first effort
        # found, which is what the page's effort filter reads.
        self.assertEqual(build.split_effort("Model (high, low)"), ("Model", "high"))

    def test_effort_is_pulled_out_of_a_mixed_group_from_either_end(self):
        self.assertEqual(
            build.split_effort("Model (Reasoning, high)"), ("Model (Reasoning)", "high"))
        self.assertEqual(
            build.split_effort("Model (high, Reasoning)"), ("Model (Reasoning)", "high"))

    def test_the_first_effort_across_groups_names_the_label(self):
        self.assertEqual(
            build.split_effort("Model (low) (Reasoning)"), ("Model (Reasoning)", "low"))
        self.assertEqual(
            build.split_effort("Model (medium) (Jan '25)"), ("Model (Jan '25)", "medium"))
        self.assertEqual(
            build.split_effort("M (a, low, b, xhigh)"), ("M (a, b)", "low"))

    def test_a_dict_repr_effort_group_is_effort(self):
        # #85: AA's own displayLabel carries a dict-repr effort group on some
        # agent runs -- "Codex - GPT-6 Luna (max) ({'reasoning_effort':
        # 'max'})". The dict is the same effort knob in AA's encoding, so it
        # strips like the bare-word group before it instead of riding into
        # the base name and eating 28 of the chart label's 34 characters.
        self.assertEqual(
            build.split_effort(
                "Codex - GPT-6 Luna (max) ({'reasoning_effort': 'max'})"),
            ("Codex - GPT-6 Luna", "max"))

    def test_a_dict_group_that_is_not_an_effort_dict_is_kept(self):
        # A typo'd key or a non-effort value is not the knob: the group stays
        # verbatim and no effort label is read off it.
        self.assertEqual(
            build.split_effort(
                "Opencode - GLM-5.3 ({'reasoning_gpt_effort': 'max'})"),
            ("Opencode - GLM-5.3 ({'reasoning_gpt_effort': 'max'})", None))
        self.assertEqual(
            build.split_effort(
                "Model ({'reasoning_effort': 'widescreen'})"),
            ("Model ({'reasoning_effort': 'widescreen'})", None))

    def test_an_empty_group_is_kept_untouched(self):
        # Nothing is stripped from "()" -- it carries no effort word, and the
        # regex-shaped reader it replaces also kept it.
        self.assertEqual(build.split_effort("Model ()"), ("Model ()", None))

    def test_unclosed_parens_are_kept_verbatim(self):
        # The input class behind issue #47's slow case: a "(" with no ")"
        # after it can never form a group, so the name must come back exactly
        # as it went in.
        self.assertEqual(build.split_effort("a ( b ( c"), ("a ( b ( c", None))

    def test_surrounding_whitespace_normalizes_to_one_space(self):
        # Whatever the reader between the name and a kept group, one space is
        # what lands in the base name -- and a stripped all-effort group takes
        # its preceding whitespace with it.
        self.assertEqual(
            build.split_effort("Model   (high)  (Reasoning)"),
            ("Model (Reasoning)", "high"))
        self.assertEqual(build.split_effort("Model\t(minimal)"), ("Model", "minimal"))


class DisplayLabelTests(unittest.TestCase):
    """Issue #85: the compact chart label `display_label` builds.

    Chart labels truncate at 34 characters, and the effort knob -- the one
    word that distinguishes variants of one model -- sat at the END of long
    names: four Claude Opus 5.5 effort variants shared a 33-char prefix, so
    the intelligence chart rendered all four identically. `display_label`
    re-attaches the first effort word immediately after the model name,
    BEFORE any kept groups, so the distinguishing word survives the cap;
    everything that is not effort keeps its place.
    """

    def test_the_effort_word_moves_before_the_kept_groups(self):
        # The live capture's long shape: the effort word lands well inside
        # the 34-char cap and the config list keeps its place after it.
        self.assertEqual(
            build.display_label(
                "Claude Opus 5.5 (Adaptive Reasoning, Max Effort, "
                "Default Fallback)"),
            "Claude Opus 5.5 (max) (Adaptive Reasoning, Default Fallback)")

    def test_a_dict_repr_effort_group_compacts_to_the_bare_word(self):
        self.assertEqual(
            build.display_label(
                "Codex - GPT-6 Luna (max) ({'reasoning_effort': 'max'})"),
            "Codex - GPT-6 Luna (max)")

    def test_the_effort_word_moves_in_front_of_a_kept_group(self):
        self.assertEqual(
            build.display_label("Model (Reasoning, high)"),
            "Model (high) (Reasoning)")

    def test_names_without_a_moving_effort_knob_are_unchanged(self):
        # A date snapshot, a reasoning marker, a bare name and an already
        # bare-effort name all round-trip exactly.
        for name in ("Model (Jan '25)", "Model (Reasoning)", "Model",
                     "Model (max)"):
            with self.subTest(name=name):
                self.assertEqual(build.display_label(name), name)

    def test_the_first_effort_across_groups_names_the_compact_label(self):
        self.assertEqual(
            build.display_label("M (a, low, b, xhigh)"), "M (low) (a, b)")

    def test_both_row_builders_carry_the_compact_label(self):
        # The page's chart labels render from r.label (assignLabels, #85),
        # so the field must reach the payload from BOTH row universes and
        # equal display_label of the row's own name.
        model = model_fixture()
        model["name"] = (
            "Fixture Model (Adaptive Reasoning, Max Effort, Default Fallback)")
        agent = agent_fixture(
            label="Fixture Agent - Model (max) "
                  "({'reasoning_effort': 'max'})")
        rows = build.build_rows([model])
        rows += build.build_agent_rows([agent], [model])
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["label"], build.display_label(row["name"]))


class DisplayNameTests(unittest.TestCase):
    """Issue #88: the reader-facing FULL name, with AA's dict form decoded.

    #85 cleaned only the short chart labels (`display_label`); the full name
    still carried "({'reasoning_effort': 'max'})" to every reader. Per group,
    per comma-part, `display_name` keeps a plain effort part verbatim, DROPS a
    dict-form effort part whose effort word already appears as a plain effort
    part anywhere in the name, REWRITES such a part to the bare effort word
    otherwise, and keeps everything else verbatim. The drop reads only the
    raw name's plain parts, so it is order-independent by design.
    """

    def test_a_dict_echo_after_the_plain_effort_drops(self):
        self.assertEqual(
            build.display_name("X (max) ({'reasoning_effort': 'max'})"),
            "X (max)")

    def test_a_dict_without_a_plain_twin_rewrites_to_the_bare_word(self):
        self.assertEqual(
            build.display_name("X ({'reasoning_effort': 'max'})"), "X (max)")

    def test_a_dict_whose_effort_differs_from_the_plain_one_rewrites(self):
        # A different effort word is not an echo of the plain part: it
        # decodes in place and the plain part stays verbatim.
        self.assertEqual(
            build.display_name("X (high) ({'reasoning_effort': 'low'})"),
            "X (high) (low)")

    def test_a_dict_part_inside_a_mixed_group_rewrites_in_place(self):
        # No plain effort part anywhere, so the dict decodes where it sits
        # and the kept group re-renders around it.
        self.assertEqual(
            build.display_name(
                "X (Adaptive Reasoning, {'reasoning_effort': 'max'})"),
            "X (Adaptive Reasoning, max)")

    def test_the_drop_decision_is_order_independent(self):
        # The dict group cleans the same on either side of its plain twin.
        self.assertEqual(
            build.display_name("X ({'reasoning_effort': 'max'}) (max)"),
            "X (max)")
        self.assertEqual(
            build.display_name("X (max) ({'reasoning_effort': 'max'})"),
            "X (max)")

    def test_the_drop_and_the_key_are_case_insensitive(self):
        # EFFORT/EFFORT_DICT match case-insensitively: an XHIGH dict value
        # drops against a plain (xhigh), and an uppercased key is still the
        # knob. The rewritten word itself stays as captured -- the verbatim
        # rule every kept part follows.
        self.assertEqual(
            build.display_name("X (xhigh) ({'reasoning_effort': 'XHIGH'})"),
            "X (xhigh)")
        self.assertEqual(
            build.display_name("X ({'REASONING_EFFORT': 'max'})"), "X (max)")
        self.assertEqual(
            build.display_name("X ({'reasoning_effort': 'XHIGH'})"),
            "X (XHIGH)")

    def test_a_dict_that_is_not_an_effort_dict_survives_verbatim(self):
        self.assertEqual(
            build.display_name("X ({'temperature': 'high'})"),
            "X ({'temperature': 'high'})")

    def test_kept_groups_and_parens_free_names_are_unchanged(self):
        for name in ("X (Adaptive Reasoning)", "X (Reasoning)", "X (Jan '25)",
                     "X", "X (high)"):
            with self.subTest(name=name):
                self.assertEqual(build.display_name(name), name)

    def test_multiple_dict_groups_decode_independently(self):
        # Two dicts, no plain effort anywhere: each decodes to its own word.
        self.assertEqual(
            build.display_name(
                "X ({'reasoning_effort': 'low'}) (Reasoning) "
                "({'reasoning_effort': 'high'})"),
            "X (low) (Reasoning) (high)")

    def test_an_effort_phrase_counts_as_the_word_for_the_drop(self):
        # split_effort reads "(Max Effort)" and "(max)" as the same knob, so
        # the dict echo of either drops against the other; the kept phrase
        # stays verbatim.
        self.assertEqual(
            build.display_name("X (Max Effort) ({'reasoning_effort': 'max'})"),
            "X (Max Effort)")

    def test_whitespace_renders_like_the_effort_scan(self):
        # A kept group renders with a one-space lead; an emptied group takes
        # its whitespace with it -- the same rules _effort_scan renders by.
        self.assertEqual(
            build.display_name("X   (max)   ({'reasoning_effort': 'max'})"),
            "X (max)")
        self.assertEqual(
            build.display_name(
                "X (max)   ({'reasoning_effort': 'max'})   (Reasoning)"),
            "X (max) (Reasoning)")

    def test_unclosed_parens_are_kept_verbatim(self):
        # The #47 input class: a "(" with no ")" after it opens no group, so
        # the scan stops there and dict text inside it is not decoded.
        raw = "X (max) ({'reasoning_effort': 'max'"
        self.assertEqual(build.display_name(raw), raw)


class DisplayNameRowTests(unittest.TestCase):
    """Issue #88 at the row builders: `"name"` is the cleaned display name.

    Every reader-facing sink -- the JS tooltip, popup, table cells,
    aria-labels, search, the copy-as-Markdown / copy-as-JSON exports -- reads
    the payload's `name`, so cleaning it at the two builders cleans them all.
    Nothing else about a row may move: `base`, `eff` and `label` keep their
    exact current semantics, computed from the RAW label, because the
    Dump-effort collapse keys on `base`.
    """

    # The live capture's dict rows (issue #88), with the plain form each
    # cleans to. The first rewrites (no plain effort part to echo); the other
    # two drop the dict echo of the plain part in front of them.
    REAL_DICT_LABELS = (
        ("Opencode - GLM-5.3 ({'reasoning_effort': 'max'})",
         "Opencode - GLM-5.3 (max)"),
        ("Codex - GPT-6 Luna (max) ({'reasoning_effort': 'max'})",
         "Codex - GPT-6 Luna (max)"),
        ("Codex - GPT-5.6 Sol (max) ({'reasoning_effort': 'max'})",
         "Codex - GPT-5.6 Sol (max)"),
    )

    @staticmethod
    def without_name(row):
        return {k: v for k, v in row.items() if k != "name"}

    def test_model_rows_carry_the_cleaned_name_and_nothing_else_moves(self):
        dict_model = model_fixture()
        dict_model["name"] = "Fixture Model (high) ({'reasoning_effort': 'high'})"
        clean_model = model_fixture()
        clean_model["name"] = "Fixture Model (high)"

        dict_rows = build.build_rows([dict_model])
        clean_rows = build.build_rows([clean_model])

        self.assertEqual(dict_rows[0]["name"], "Fixture Model (high)")
        self.assertEqual(
            self.without_name(dict_rows[0]), self.without_name(clean_rows[0]))

    def test_agent_rows_carry_the_cleaned_name_and_nothing_else_moves(self):
        dict_agent = agent_fixture(
            label="Fixture Agent - Fixture Model (high) "
                  "({'reasoning_effort': 'high'})")
        clean_agent = agent_fixture(
            label="Fixture Agent - Fixture Model (high)")

        dict_rows = build.build_agent_rows([dict_agent], [model_fixture()])
        clean_rows = build.build_agent_rows([clean_agent], [model_fixture()])

        self.assertEqual(
            dict_rows[0]["name"], "Fixture Agent - Fixture Model (high)")
        self.assertEqual(
            self.without_name(dict_rows[0]), self.without_name(clean_rows[0]))

    def test_no_emitted_row_name_carries_the_dict_text(self):
        models = [model_fixture(slug="m1"), model_fixture(slug="m2")]
        models[0]["name"] = "Fixture Model ({'reasoning_effort': 'low'})"
        agents = [
            agent_fixture(
                label="Agent One - Model ({'reasoning_effort': 'xhigh'})"),
            agent_fixture(
                label="Agent Two - Model (high) "
                      "({'reasoning_effort': 'high'})"),
        ]

        rows = build.build_rows(models) + build.build_agent_rows(agents, models)

        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn("reasoning_effort", row["name"])

    def test_sort_order_is_unchanged_by_the_cleaning(self):
        # The name is the rows' final sort tiebreaker, so rows built from
        # dict-form names must order exactly as rows built from hand-cleaned
        # names do -- here two rows tie on (II, cost) and separate on the
        # name alone.
        def pair(names):
            models = []
            for i, name in enumerate(names):
                m = model_fixture(slug=f"m{i}", intelligence=51)
                m["name"] = name
                models.append(m)
            return [r["name"] for r in build.build_rows(models)]

        self.assertEqual(
            pair(("Zeta ({'reasoning_effort': 'high'})", "Alpha (high)")),
            pair(("Zeta (high)", "Alpha (high)")))

    def test_the_real_capture_rows_clean_to_their_plain_form(self):
        for raw, cleaned in self.REAL_DICT_LABELS:
            with self.subTest(raw=raw):
                rows = build.build_agent_rows(
                    [agent_fixture(label=raw)], [model_fixture()])

                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["name"], cleaned)

    def test_the_built_page_carries_no_dict_effort_text_anywhere(self):
        # The issue's own pin, page-wide: the embedded payload feeds the
        # tooltip, popup, table, aria-labels, search and both copy exports,
        # so one occurrence anywhere means a reader can see the dict.
        html = _build_in_temp_dir()

        self.assertNotIn("reasoning_effort", html)


class SplitEffortScalingTests(unittest.TestCase):
    """Issue #47: a pathological name must degrade to fast processing.

    The pre-fix implementation drove the EFFORT regex over the whole name,
    and a "(" with no ")" to its right makes `[^)]*\\)` scan to the end of
    the string and backtrack -- O(parens x remaining length), measured
    ~62x CPU for 8x the groups at the sizes below (18 s for one 20,000-group
    name). A crafted capture carrying such a name passes every schema check
    and lands in `split_effort` through `build_rows`, so the hourly refresh
    runs it ~680 times and times out.

    The pin is a growth ratio, not a wall-clock number: CPU time (immune to
    other processes on the box) for a pathological name at N and 8N, with a
    40x ceiling. A linear scan ratios ~8-12x here; the quadratic it replaces
    ratios ~47-70x across repeated runs. The absolute ceiling on the large
    block is a belt-and-suspenders gross-regression trip, not the mechanism.

    The measurement is CALIBRATED against the host's clock (fix round 2):
    each size is timed as k repeats inside one block, with k doubled until
    the smaller size's total clears CLOCK_FLOOR -- well above the coarsest
    tick in the CI fleet (Windows process_time ~15.6 ms), whose hosts read a
    bare microsecond-scale sample as 0.0 and turned the ratio into a
    ZeroDivisionError. Both sizes run the SAME k, so the totals' ratio is
    the per-operation ratio and the ceiling comparison is unchanged. A
    clock that cannot resolve even the calibrated smaller block fails
    loudly naming the clock -- never a division by zero -- and that path
    is pinned with an injected zero-returning clock.
    """

    SIZES = (2500, 20000)
    RATIO_CEILING = 40
    # Well above the coarsest host clock tick in the CI fleet (Windows
    # process_time ~15.6 ms): every accepted measurement clears this.
    CLOCK_FLOOR = 0.05
    LARGE_TOTAL_CPU_CEILING = 5.0

    @staticmethod
    def pathological(groups: int) -> str:
        # Unclosed parens: the shape that drove the quadratic backtracking.
        return "Model (" * groups

    @classmethod
    def block_total(cls, groups: int, k: int, clock) -> float:
        """CPU seconds to split the pathological name k times."""
        name = cls.pathological(groups)
        start = clock()
        for _ in range(k):
            build.split_effort(name)
        return clock() - start

    @classmethod
    def calibrated_totals(cls, clock=time.process_time,
                          k_limit: int = 2 ** 22) -> tuple[float, float, int]:
        """-> (small, large, k): CPU totals for the two sizes at the SAME
        repeat count k, calibrated on the smaller size until its total
        clears CLOCK_FLOOR.

        Raises AssertionError naming the clock when it cannot resolve even
        the calibrated smaller block: a ratio over such a reading would be
        a ZeroDivisionError, not a measurement.
        """
        clock_name = getattr(clock, "__qualname__", None) or repr(clock)
        k = 1
        small = cls.block_total(cls.SIZES[0], k, clock)
        while small <= cls.CLOCK_FLOOR:
            if k >= k_limit:
                raise AssertionError(
                    f"the clock ({clock_name}) cannot resolve the smaller "
                    f"scaling sample ({cls.SIZES[0]}-group name at k={k} "
                    f"repeats reads {small:.4f}s) -- its tick is too coarse "
                    "for the work and the growth ratio would divide by zero")
            k *= 2
            small = cls.block_total(cls.SIZES[0], k, clock)
        large = cls.block_total(cls.SIZES[1], k, clock)
        return small, large, k

    def test_pathological_names_scale_sub_quadratically(self):
        small, large, k = self.calibrated_totals()

        ratio = large / small
        self.assertLess(
            ratio, self.RATIO_CEILING,
            f"split_effort grew {ratio:.1f}x for 8x the groups "
            f"(same k={k} repeats per size, small block {small:.3f}s cpu, "
            f"large block {large:.3f}s cpu) -- super-linear; a crafted "
            "capture can stall the hourly refresh (issue #47)")
        self.assertLess(
            large, self.LARGE_TOTAL_CPU_CEILING,
            f"the large-size block took {large:.3f}s cpu for k={k} repeats "
            "-- split_effort is too slow on a pathological input")

    def test_a_clock_that_cannot_resolve_the_work_fails_loudly(self):
        # The ZeroDivisionError that broke CI on coarse-clock hosts, pinned
        # shut: a clock that never advances must trip the loud refusal
        # naming the clock -- never reach the division.
        class ZeroClock:
            """Every measurement reads 0.0: the coarse-tick failure at its
            limit."""

            def __call__(self):
                return 0.0

        with self.assertRaises(AssertionError) as caught:
            self.calibrated_totals(clock=ZeroClock(), k_limit=8)

        message = str(caught.exception)
        self.assertIn("ZeroClock", message)
        self.assertIn("too coarse", message)
        self.assertNotIsInstance(caught.exception, ZeroDivisionError)


class BuildArgvTests(unittest.TestCase):
    """Issue #55: `python3 build.py --help` must print usage, not rebuild.

    build.py handled argv not at all -- a `--help` ran the whole build and
    rewrote out/frontier-models.html. The parser lives in the __main__ guard
    (main() keeps its no-argument signature, which the direct callers in this
    suite depend on), so these pins drive the real command line as a
    subprocess and judge it by process observables: exit status, stdout, and
    the output page's mtime -- the side effect the issue is about.
    """

    PAGE = build.ROOT / "out" / "frontier-models.html"

    def page_mtime(self):
        return self.PAGE.stat().st_mtime_ns if self.PAGE.exists() else None

    def run_build(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(build.ROOT / "build.py"), *argv],
            cwd=build.ROOT, capture_output=True, text=True, timeout=120,
            check=False)

    def test_help_prints_usage_and_performs_no_build(self):
        before = self.page_mtime()

        proc = self.run_build("--help")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage:", proc.stdout.lower())
        self.assertIn("frontier-models.html", proc.stdout)
        self.assertEqual(
            self.page_mtime(), before,
            "--help rebuilt out/frontier-models.html")

    def test_an_unknown_flag_is_refused_without_building(self):
        # The negative control for the parser being attached at all: today an
        # unrecognized argument silently built the page, which is how --help
        # got to ship a rebuild. argparse's own refusal (exit 2, usage on
        # stderr) must replace that, still with no page written.
        before = self.page_mtime()

        proc = self.run_build("--definitely-not-a-flag")

        self.assertEqual(proc.returncode, 2)
        self.assertIn("unrecognized arguments", proc.stderr)
        self.assertEqual(
            self.page_mtime(), before,
            "a refused argument still rebuilt out/frontier-models.html")


class CorruptCaptureTests(unittest.TestCase):
    """Issue #66: a truncated capture must fail red naming the reason.

    A capture written by a crashed runner can end mid-file; parsed anyway,
    build.py died with a raw JSONDecodeError traceback that named no file.
    These pins drive the REAL command line -- build.py copied into a
    throwaway tree beside a data/ directory holding the truncated capture,
    exactly the layout the hourly refresh runs -- and judge the process
    observables: nonzero exit, stderr naming the capture and the designed
    re-capture instruction, and no Python traceback. Nothing outside the
    temp tree is touched; the copy resolves its own ROOT there and fails
    before any output could be written.
    """

    CAPTURES = ("aa-raw-models.json", "aa-raw-coding-agents.json")

    def run_build_with_capture(self, truncate: str) -> tuple[subprocess.CompletedProcess, pathlib.Path]:
        """Run build.py from a temp copy of the tree, with every capture
        present and the named one cut mid-file. -> (process, tree root)."""
        with tempfile.TemporaryDirectory(prefix=".issue-66-build-", dir=build.ROOT) as tmp:
            root = pathlib.Path(tmp)
            (root / "data").mkdir()
            # The builder is build.py plus the module it imports, so the
            # temp tree carries both, the way the checkout lays them out.
            for module in ("build.py", "page_format.py"):
                (root / module).write_text(
                    (build.ROOT / module).read_text(encoding="utf-8"),
                    encoding="utf-8")
            for name in self.CAPTURES:
                raw = (build.ROOT / "data" / name).read_bytes()
                if name == truncate:
                    raw = raw[: len(raw) // 2]  # valid capture JSON, cut mid-file
                (root / "data" / name).write_bytes(raw)
            proc = subprocess.run(
                [sys.executable, str(root / "build.py")],
                capture_output=True, text=True, timeout=120, check=False)
            return proc, root

    def test_a_truncated_model_capture_fails_naming_the_file_not_a_traceback(self):
        proc, root = self.run_build_with_capture("aa-raw-models.json")

        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr,
                         "the corrupt capture surfaced as a raw traceback")
        self.assertIn("aa-raw-models.json", proc.stderr)
        self.assertIn("corrupt capture", proc.stderr)
        self.assertIn("fetch_aa.py", proc.stderr,
                      "the refusal does not say what to do about it")
        self.assertFalse(
            (root / "out" / "frontier-models.html").exists(),
            "a corrupt capture still produced a page")

    def test_a_truncated_agents_capture_is_named_by_its_own_file(self):
        # The agents capture is read second; its guard must name IT, not the
        # model capture that parsed fine.
        proc, _ = self.run_build_with_capture("aa-raw-coding-agents.json")

        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("aa-raw-coding-agents.json", proc.stderr)
        self.assertNotIn("aa-raw-models.json", proc.stderr.splitlines()[-1])


if __name__ == "__main__":
    unittest.main()


# --- disputed build (issue #118) ------------------------------------------------

def _disputed_route_records(slug: str = "fixture-model", *, ii_lb: float = 51,
                            ii_dt: float = 52,
                            name: str = "Fixture Model (high)",
                            lic_lb: str | None = None,
                            lic_dt: str | None = None):
    """(leaderboard, detail) records for one slug, disagreeing on
    intelligenceIndex and agreeing on every other shared value: the
    leaderboard carries its flattened cost scalar and an undefined context,
    the detail route the full cost object and a measured context."""
    shared = {
        "slug": slug,
        "modelCreatorName": "Fixture Lab",
        "isOpenWeights": False,
        "gdpvalNormalized": 0.47,
        "parameters": 27,
        "medianOutputTokensPerSecond": 100.0,
    }
    if lic_lb is not None:
        shared["licenseName"] = lic_lb
    leaderboard = {
        **shared, "shortName": name, "intelligenceIndex": ii_lb,
        "intelligenceIndexCostPerTask": 0.75,
        "contextWindowTokens": "$undefined",
    }
    if lic_dt is not None:
        shared["licenseName"] = lic_dt
    detail = {
        **shared, "name": name, "intelligenceIndex": ii_dt,
        "intelligenceIndexCostPerTask": {
            "cost": {"total": 0.75},
            "evaluations": [
                {"slug": "gdpval-aa", "weightedCostPerTask": 0.30},
                {"slug": "scicode", "weightedCostPerTask": 0.45}],
        },
        "contextWindowTokens": 400000,
    }
    return leaderboard, detail


def disputed_snapshot_fixture(**kwargs) -> dict:
    """The snapshot fetch_aa.py's refusal writes, built the same way: the two
    raw route payloads plus the disagreement map straight out of
    check_route_agreement -- mutated payloads against each other, never an
    edited data/ file. Pass lic_lb/lic_dt to add a shared-string dispute
    (the licence) beside the intelligence-index one."""
    lb, dt = _disputed_route_records(**kwargs)
    lb_b, dt_b = _disputed_route_records(
        "fixture-model-b", ii_lb=40, ii_dt=40,
        name="Fixture Model B (high)")
    try:
        build.check_route_agreement([lb, lb_b], [dt, dt_b])
        raise AssertionError("the fixture payloads must disagree")
    except build.RouteDisagreement as exc:
        divergences = exc.divergences
    return {
        "schema": 1,
        "capturedAt": "2026-10-04T03:30:00Z",
        "windowStartEpoch": 1791084000,
        "leaderboardGeneratedAt": 1791084000,
        "detailGeneratedAt": 1791084300,
        "indexVersion": build.INDEX_VERSION,
        "detailHost": "fixture-model-b",
        "leaderboard": [lb, lb_b],
        "detail": [dt, dt_b],
        "disagreements": [
            {"slug": slug, "path": path, "lb": lb_value, "dt": dt_value}
            for slug, path, lb_value, dt_value in divergences
        ],
    }


class DisputedBuildTests(unittest.TestCase):
    """Issue #118: a disagreement snapshot beside the capture turns the build
    into a disputed rendering -- banner, both values in disputed cells, and
    disputed models sitting out the frontiers -- while the file's ABSENCE is
    the normal build, byte-for-byte as before."""

    @contextlib.contextmanager
    def disputed_page(self, snapshot: dict | None = None):
        """build.main() over a temp data dir carrying the snapshot (when
        given), the last-good agents capture, and the stamp."""
        with tempfile.TemporaryDirectory(
                prefix=".issue-118-disputed-", dir=build.ROOT) as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            if snapshot is None:
                snapshot = disputed_snapshot_fixture()
            (data / build.DISPUTED_SNAPSHOT_NAME).write_text(
                json.dumps(snapshot, indent=1), encoding="utf-8")
            (data / "aa-raw-coding-agents.json").write_text(
                json.dumps([agent_fixture()]), encoding="utf-8")
            (data / "captured-at.txt").write_text("2026-10-04\n",
                                                  encoding="utf-8")
            saved = build.RAW, build.AGENTS_RAW, build.OUT
            build.RAW = data / "aa-raw-models.json"
            build.AGENTS_RAW = data / "aa-raw-coding-agents.json"
            build.OUT = pathlib.Path(tmp) / "frontier-models.html"
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                yield build.OUT.read_text(encoding="utf-8"), snapshot
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = saved

    def payload_of(self, page: str) -> dict:
        marker = "const DATA = "
        start = page.index(marker) + len(marker)
        payload, _ = json.JSONDecoder().raw_decode(page[start:].lstrip())
        return payload

    def test_the_banner_renders_with_the_window_and_counts(self):
        with self.disputed_page() as (page, _snapshot):
            self.assertIn('id="disputed" role="status"', page)
            self.assertIn("Disputed capture", page)
            self.assertIn("2026-10-04T03:20:00Z", page)
            self.assertIn("1 model(s) carry 1 conflicting value(s)", page)

    def test_the_disputed_row_carries_both_values_in_the_static_table(self):
        with self.disputed_page() as (page, _snapshot):
            payload = self.payload_of(page)
            disputed = [r for r in payload["rows"] if r.get("disp")]
            self.assertEqual([r["base"] for r in disputed],
                             ["Fixture Model"])
            entry = disputed[0]["disp"]["intelligenceIndex"]
            self.assertEqual((entry["lb"], entry["dt"]), (51, 52))
            # The STATIC body is the accessible twin: the disputed cell shows
            # both routes' values and the disputed pill, in the no-JS render.
            self.assertIn("51.0 / 52.0", page)
            self.assertIn(">disputed</span>", page)

    def test_a_non_disputed_row_renders_its_base_value_unchanged(self):
        with self.disputed_page() as (page, _snapshot):
            payload = self.payload_of(page)
            clean = [r for r in payload["rows"]
                     if r["base"] == "Fixture Model B"]
            self.assertEqual(len(clean), 1)
            self.assertNotIn("disp", clean[0])
            self.assertNotIn("40.0 /", page)

    def test_disputed_rows_sit_out_the_frontier_in_both_directions(self):
        # The disputed model is smarter at the same cost, so were it eligible
        # it would dominate Fixture Model B outright. Sitting out BOTH roles,
        # B keeps its frontier seat and the disputed model has none.
        with self.disputed_page() as (page, _snapshot):
            payload = self.payload_of(page)
            self.assertEqual(payload["stats"]["metricFrontiers"],
                             {"coding": 1, "intelligence": 1, "agentic": 1})
            rows = {r["base"]: r for r in payload["rows"]}
            self.assertIn(rows["Fixture Model B"],
                          build.undominated(payload["rows"], "intelligence"))
            self.assertNotIn(rows["Fixture Model"],
                             build.undominated(payload["rows"], "intelligence"))
            # And the no-JS frontier table carries B, never the disputed model.
            front = page.index("id=\"fTable\"")
            self.assertIn('<td class="name">Fixture Model B (high)</td>',
                          page[front:])
            self.assertNotIn('<td class="name">Fixture Model (high)</td>',
                             page[front:])

    def test_the_footer_and_legend_name_the_dispute_only_in_disputed_mode(self):
        with self.disputed_page() as (page, _snapshot):
            self.assertIn("currently disagree", page)
            self.assertIn('class="swatch disp"', page)
            self.assertEqual(page.count('class="swatch disp"'), 4)
        # ...and the page built WITHOUT a snapshot is exactly the old one:
        with tempfile.TemporaryDirectory(
                prefix=".issue-118-normal-", dir=build.ROOT) as tmp:
            data = pathlib.Path(tmp) / "data"
            data.mkdir()
            (data / "aa-raw-models.json").write_text(
                json.dumps([model_fixture()]), encoding="utf-8")
            (data / "aa-raw-coding-agents.json").write_text(
                json.dumps([agent_fixture()]), encoding="utf-8")
            (data / "captured-at.txt").write_text("2026-10-04\n",
                                                  encoding="utf-8")
            saved = build.RAW, build.AGENTS_RAW, build.OUT
            build.RAW = data / "aa-raw-models.json"
            build.AGENTS_RAW = data / "aa-raw-coding-agents.json"
            build.OUT = pathlib.Path(tmp) / "frontier-models.html"
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                page = build.OUT.read_text(encoding="utf-8")
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = saved
        self.assertIn("agree exactly on every value they share", page)
        self.assertNotIn('id="disputed"', page)
        self.assertNotIn("swatch disp", page)
        self.assertNotIn("__DISPUTED_BANNER__", page)
        self.assertNotIn("__ROUTE_AGREEMENT_CLAUSE__", page)
        self.assertNotIn("__DISPUTED_LEGEND__", page)
        payload = self.payload_of(page)
        self.assertNotIn("disputed", payload["stats"])

    def test_a_corrupt_snapshot_refuses_like_a_corrupt_capture(self):
        for why, mutate in (
                ("schema bump", lambda s: s.update({"schema": 2})),
                ("routes missing", lambda s: s.pop("detail")),
                ("bad disagreement entry",
                 lambda s: s["disagreements"].append({"slug": "x"})),
                ("window start not an epoch",
                 lambda s: s.update({"windowStartEpoch": "soon"})),
        ):
            with self.subTest(why=why):
                snapshot = disputed_snapshot_fixture()
                mutate(snapshot)
                with self.assertRaises(SystemExit) as caught:
                    with self.disputed_page(snapshot):
                        pass
                self.assertIn("aa-disagreement-snapshot.json",
                              str(caught.exception))

    def test_the_js_dispute_map_spans_the_mirror_paths(self):
        # One map per language, and the drift between them is silent: the
        # JS DISPUTE_KINDS (the tooltip's labels and kinds) must carry every
        # path the static mirror renders, and the cost path's two spellings
        # -- the nested shape and the reshape spelling -- must both resolve.
        # Extracted from TEMPLATE so the assertion spans the two modules'
        # literals, not a copy of either.
        match = re.search(
            r'const DISPUTE_KINDS = \{(.*?)\};', build.TEMPLATE, re.S)
        assert match is not None, "DISPUTE_KINDS vanished from the template"
        js_keys = set(re.findall(r'"([^"]+)":', match.group(1)))
        mirror_paths = {"intelligenceIndex", "gdpvalNormalized", "parameters",
                        "intelligenceIndexCostPerTask",
                        "intelligenceIndexCostPerTask.cost.total"}
        self.assertTrue(mirror_paths <= js_keys,
                        f"the JS map lost a mirror path: "
                        f"{sorted(mirror_paths - js_keys)}")

    def test_the_provenance_names_the_snapshot_as_an_input(self):
        with self.disputed_page() as (page, _snapshot):
            self.assertIn("sha256 over data/aa-disagreement-snapshot.json then "
                          "data/aa-raw-coding-agents.json", page)


class FrontierZeroScoreTests(unittest.TestCase):
    """Issue #146: zero is a legal AA-published score -- the current capture
    carries gdpvalNormalized: 0 on 75 models -- and a score-0 row lands on an
    axis's efficient frontier exactly when it is the strictly cheapest row
    there (any cheaper row would dominate it). The hourly refresh at
    2026-10-03T01:09Z hit the one division over a capture-sourced denominator
    unprepared for it: the frontier table's $/point. The build now renders
    that cell as the em dash -- a $/point at zero capability is not a number
    -- instead of crashing, and the JS mirror must render the same cell or
    the browser drift test fails.
    """

    def _rows(self):
        """Two hand-built rows; the cheap one scores 0.0 on agentic, making
        it the strictly cheapest row on that axis and therefore frontier-
        eligible. Coding and intelligence pairs stay positive on both."""
        return [
            {
                "name": "Cheap Zero", "creator": "Zero Lab", "open": False,
                "lic": None, "disp": None,
                "metrics": {
                    "coding": {"score": 40.0, "cost": 0.5},
                    "intelligence": {"score": 30.0, "cost": 1.0},
                    "agentic": {"score": 0.0, "cost": 0.3},
                },
            },
            {
                "name": "Costly Smart", "creator": "Other Lab", "open": True,
                "lic": "mit", "disp": None,
                "metrics": {
                    "coding": {"score": 60.0, "cost": 2.0},
                    "intelligence": {"score": 51.0, "cost": 1.5},
                    "agentic": {"score": 50.0, "cost": 2.0},
                },
            },
        ]

    def test_the_frontier_table_renders_zero_score_rows(self):
        # The agentic row: score 0.0, cost $0.300, and the $/point cell is
        # the em dash -- not a crash, not "$Infinity".
        tbody = build.render_frontier_tbody(self._rows())
        self.assertIn(
            '<tr><td>GDPval-AA v2</td><td class="name">Cheap Zero</td>'
            "<td>Zero Lab</td>"
            '<td class="n">0.0</td><td class="n">$0.300</td>'
            '<td class="n">—</td>'
            '<td><span class="tag">proprietary</span></td></tr>',
            tbody)
        # A positive-score sibling still renders its $/point: 2.0/50.
        self.assertIn('<td class="n">$0.0400</td>', tbody)

    def test_zero_score_capture_builds_through_main(self):
        # The real capture with one model turned into the hourly's crash:
        # gdpvalNormalized zeroed and its gdpval eval cost set strictly
        # cheapest, so it lands on the agentic frontier with a zero score.
        models = json.loads(
            (build.ROOT / "data" / "aa-raw-models.json").read_bytes())
        floor = None
        target = None
        for m in models:
            weighted = gdpval_weighted_cost(m)
            if (weighted is not None and weighted > 0
                    and (floor is None or weighted < floor)):
                floor = weighted
            if target is None and weighted is not None and weighted > 0 and "(" not in (
                    m.get("shortName") or m.get("name") or ""):
                target = m
        self.assertIsNotNone(target)
        target["gdpvalNormalized"] = 0
        for e in target["intelligenceIndexCostPerTask"]["evaluations"]:
            if e.get("slug") == "gdpval-aa":
                e["weightedCostPerTask"] = floor / 2
        # The rendered row name is build's own cleaning over name-first,
        # shortName-fallback -- "(Reasoning)" survives the cleaning, so the
        # assertion derives it through the same function rather than guessing.
        name = build.display_name(target.get("name") or target.get("shortName"))

        with tempfile.TemporaryDirectory(
                prefix=".issue-146-build-", dir=build.ROOT) as tmp:
            raw = pathlib.Path(tmp) / "models.json"
            agents_raw = pathlib.Path(tmp) / "coding-agents.json"
            page_path = pathlib.Path(tmp) / "frontier-models.html"
            raw.write_bytes(
                json.dumps(models, indent=1).encode("utf-8"))
            agents_raw.write_bytes(
                (build.ROOT / "data" / "aa-raw-coding-agents.json").read_bytes())
            saved = (build.RAW, build.AGENTS_RAW, build.OUT)
            build.RAW, build.AGENTS_RAW, build.OUT = raw, agents_raw, page_path
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    build.main()
            finally:
                build.RAW, build.AGENTS_RAW, build.OUT = saved
            page = page_path.read_text(encoding="utf-8")

        ftable = page[page.index('id="fTable"'):page.index("</table>", page.index('id="fTable"'))]
        row_re = re.compile(
            r'<tr><td>GDPval-AA v2</td><td class="name">'
            + re.escape(html.escape(name)) + r"</td>(.*?)</tr>")
        match = row_re.search(ftable)
        self.assertIsNotNone(
            match, f"no agentic frontier row for the mutated model {name}")
        self.assertIn('<td class="n">0.0</td>', match.group(1))
        self.assertIn('<td class="n">—</td>', match.group(1))


def gdpval_weighted_cost(m):
    """The model's gdpval-aa weightedCostPerTask, or None when it has no
    parseable one. Test-side mirror of build.evaluation_cost_per_task's
    value sourcing."""
    outer = m.get("intelligenceIndexCostPerTask")
    evals = outer.get("evaluations") if isinstance(outer, dict) else None
    if not isinstance(evals, list):
        return None
    for e in evals:
        if (isinstance(e, dict) and e.get("slug") == "gdpval-aa"
                and isinstance(e.get("weightedCostPerTask"), (int, float))
                and not isinstance(e.get("weightedCostPerTask"), bool)):
            return e["weightedCostPerTask"]
    return None
