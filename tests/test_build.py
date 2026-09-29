import contextlib
import datetime
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


def route_pair() -> tuple[dict, dict]:
    """(leaderboard, detail) records for one model, shaped as AA's two routes
    split one record: the leaderboard kept shortName, context and a FLATTENED
    cost total, while the detail page carries name, licence, the parameter
    count and the full cost object with its per-evaluation breakdown. Shared
    values agree exactly; contextWindowTokens is "$undefined" on the
    leaderboard route -- AA's encoding of an absent field -- where the detail
    route has measured it. intelligenceIndexEvaluations is a shared LIST: the
    real corpus ships it empty on both routes (678/679 records in the merged
    capture), so the fixture carries elements to pin the walk's list limb."""
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

                self.assertIn("captured 2026-09-29", html)
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


if __name__ == "__main__":
    unittest.main()
