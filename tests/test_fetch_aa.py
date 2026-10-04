import contextlib
import datetime
import email.message
import email.utils
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

    def test_a_flattened_scalar_does_not_shadow_the_structured_breakdown(self):
        # AA flattened the leaderboard's intelligenceIndexCostPerTask to its
        # bare total. Same key, scalar shape; the detail route kept the
        # object. "Present, so keep it" left every model without a breakdown
        # and stopped the pipeline for a day. The object must win.
        base = [{"slug": "a", "intelligenceIndexCostPerTask": 1.5}]
        detail = [{"slug": "a", "intelligenceIndexCostPerTask": {
            "cost": {"total": 1.5},
            "evaluations": [{"slug": "gdpval-aa", "weightedCostPerTask": 0.4}]}}]

        got = fetch_aa.merge_captures(base, detail)

        self.assertEqual(got[0]["intelligenceIndexCostPerTask"]["cost"]["total"], 1.5)
        self.assertEqual(len(got[0]["intelligenceIndexCostPerTask"]["evaluations"]), 1)

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
        # --html is how you re-extract without hitting AA again; a file has
        # no headers, so the generation time is the pair's None half (issue
        # #100).
        path = pathlib.Path(__file__).resolve().parent / "_cached.html"
        path.write_text("<html>cached</html>", encoding="utf-8")
        try:
            self.assertEqual(fetch_aa.fetch_html(str(path)),
                             ("<html>cached</html>", None))
            # The second capture reads its own cache through the same helper.
            self.assertEqual(
                fetch_aa.fetch_html(str(path), fetch_aa.AGENTS_URL),
                ("<html>cached</html>", None))
        finally:
            path.unlink()


class GeneratedAtTests(unittest.TestCase):
    """Issue #100: each route reports when its cached copy was generated.

    Vercel's Date header equals the entry's generation time on every probed
    shape, and it is the only observable that says how old a disagreeing
    snapshot is -- so fetch_html returns it beside the text. It is a
    diagnostic ONLY: nothing downstream may gate on it, which these pins
    enforce by construction (the helpers under test can only format, never
    decide).
    """

    EPOCH = 1791084000

    def fetch(self, headers: email.message.Message) -> int | None:
        """fetch_html through the urlopen boundary, headers modeled."""
        stub = LoudUrlopenStub({fetch_aa.URL: lambda: _FakeResponse(
            "<html>leaderboard</html>", headers)})
        with unittest.mock.patch.object(urllib.request, "urlopen", stub):
            text, generated = fetch_aa.fetch_html(None, fetch_aa.URL)
        self.assertEqual(stub.calls, [fetch_aa.URL])
        self.assertEqual(text, "<html>leaderboard</html>")
        return generated

    def test_the_date_header_parses_to_an_epoch(self):
        headers = email.message.Message()
        headers["Date"] = email.utils.formatdate(self.EPOCH, usegmt=True)

        self.assertEqual(self.fetch(headers), self.EPOCH)

    def test_a_naive_gmt_date_still_parses_as_utc(self):
        # "-0000" is the one Date spelling email parses to a NAIVE datetime;
        # HTTP dates are GMT by definition, so it must read as UTC rather
        # than land in the runner's local zone.
        headers = email.message.Message()
        headers["Date"] = "Wed, 30 Sep 2026 13:59:17 -0000"
        expected = int(datetime.datetime(
            2026, 9, 30, 13, 59, 17,
            tzinfo=datetime.timezone.utc).timestamp())

        self.assertEqual(self.fetch(headers), expected)

    def test_a_missing_or_unparseable_date_header_yields_none(self):
        absent = email.message.Message()
        garbage = email.message.Message()
        garbage["Date"] = "not a date"
        for why, headers in (("absent", absent), ("garbage", garbage)):
            with self.subTest(why=why):
                self.assertIsNone(self.fetch(headers))

    def test_the_disagreement_exit_code_is_three(self):
        # The number the refresh workflow matches on (rc -eq 3); a drift on
        # either side of that contract is caught here or in the workflow's
        # own static pins.
        self.assertEqual(fetch_aa.DISAGREEMENT_EXIT_CODE, 3)


def leaderboard_record(**overrides: object) -> dict:
    """fixture-model as the leaderboard route carries it: the flattened cost
    total plus the filler fields AA still ships there. The filler is
    identical on both routes -- only a deliberate delta may make a shared
    field disagree."""
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


def leaderboard_payload(host_slug: str = "detail-host-model") -> str:
    """A leaderboard flight payload: the pinned index version and the model
    array, one unpriced detail host (named `host_slug`) plus the shared
    model. Compact JSON -- the extractor anchors on that shape."""
    host = {"slug": host_slug,
            "intelligenceIndexCostPerTask": "$undefined"}
    return json.dumps({
        "intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
        "models": [host, leaderboard_record()],
    }, separators=(",", ":"))


def detail_payload(**record_overrides: object) -> str:
    return json.dumps({"models": [detail_record(**record_overrides)]},
                      separators=(",", ":"))


class CaptureAgreementWiringTests(unittest.TestCase):
    """Issue #44: the pre-merge agreement check is wired into the capture.

    build.check_route_agreement protects the page's claim only while
    scripts/fetch_aa.py actually calls it between loading the two routes and
    merge_captures -- a call site no unit test observes, which is exactly the
    gap a refactor could delete silently. These pins drive fetch_aa.main()
    over three cached pages: a divergent capture is refused by the real
    entry path before the merge, and a healthy one runs through to its
    writes with the compared count in the capture log. All three caches are
    always passed, whatever a test asserts: no test here may reach the
    network.
    """

    last_output: tuple[str, str] = ("", "")

    def run_capture(self, leaderboard: str, detail: str,
                    agents: str) -> tuple[str, str]:
        """Drive fetch_aa.main() over cached pages; -> (stdout, stderr). The
        pair is also kept on `self.last_output`, because a refusing main()
        never returns it."""
        self.last_output = ("", "")
        with tempfile.TemporaryDirectory(prefix=".issue-44-capture-") as tmp:
            root = pathlib.Path(tmp)
            pages = [root / name for name in
                     ("leaderboard.html", "detail.html", "agents.html")]
            for path, payload in zip(pages, (leaderboard, detail, agents)):
                path.write_text(flight_html(payload), encoding="utf-8")
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
                            "--agents-html", str(pages[2])]
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), \
                        contextlib.redirect_stderr(err):
                    try:
                        fetch_aa.main()
                    finally:
                        self.last_output = (out.getvalue(), err.getvalue())
                return self.last_output
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def test_a_cross_route_divergence_refuses_the_real_capture_before_the_merge(self):
        # One delta from the healthy capture: the detail route's copy of
        # intelligenceIndex moves. The refusal is exit 3 (issue #100), with
        # the agreement check's own message -- not a downstream schema
        # guard's -- on stderr, and the cached pages have no headers, so the
        # generation times read as unknown.
        with self.assertRaises(SystemExit) as caught:
            self.run_capture(
                leaderboard_payload(),
                detail_payload(intelligenceIndex=52),
                agent_payload([agent_row(f"Agent - Model {i}") for i in range(5)]))

        self.assertEqual(caught.exception.code, fetch_aa.DISAGREEMENT_EXIT_CODE)
        stderr = self.last_output[1]
        self.assertIn("shared value(s) disagree", stderr)
        self.assertIn(
            "fixture-model: intelligenceIndex: leaderboard 51, detail 52",
            stderr)
        self.assertIn("leaderboard generated (generation time unknown), "
                      "detail generated (generation time unknown)",
                      stderr)

    def test_a_capture_whose_routes_agree_runs_the_check_and_writes_through(self):
        # The healthy control: the fixture capture is valid end to end, the
        # check passes over it, and the capture log carries the compared
        # count -- the observable that shows the call ran. 24 = the 21 filler
        # fields the routes share, slug, intelligenceIndex, and the
        # leaderboard's flattened 0.75 against the detail object's
        # cost.total.
        stdout, _stderr = self.run_capture(
            leaderboard_payload(), detail_payload(),
            agent_payload([agent_row(f"Agent - Model {i}") for i in range(5)]))

        self.assertIn("24 shared values cross-checked", stdout)
        self.assertIn("wrote aa-raw-models.json", stdout)
        self.assertIn("wrote aa-raw-coding-agents.json", stdout)


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
                     ("leaderboard.html", "detail.html", "agents.html")]
            payloads = (leaderboard_payload(), detail_payload(),
                        agent_payload([agent_row(f"Agent - Model {i}")
                                       for i in range(5)]))
            for path, payload in zip(pages, payloads):
                path.write_text(flight_html(payload), encoding="utf-8")
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
                            "--agents-html", str(pages[2])]
                if patcher is not None:
                    patcher.start()

                def run() -> str:
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
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
    """The urlopen context-manager result, for a modeled healthy page.

    A real response carries headers; the default models a Date-less one, so
    tests that do not care about generation times keep exercising the None
    path for free (issue #100).
    """

    def __init__(self, body: str, headers: email.message.Message | None = None):
        self._body = body
        self.headers = (headers if headers is not None
                        else email.message.Message())

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
            fetch_aa.URL: lambda: _FakeResponse(flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(agents),
        }

    def test_a_healthy_fetch_still_succeeds_through_the_boundary(self):
        # The control: the wrap must catch transport failures only, and the
        # healthy capture runs all three modeled pages through the real
        # urlopen call shape (leaderboard, detail, agents) to its writes.
        stub, stdout = self.run_capture_through_boundary(self.healthy_routes())

        self.assertEqual(stub.calls, [fetch_aa.URL, self.DETAIL_URL,
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

                with self.assertRaises(SystemExit) as caught:
                    self.run_capture_through_boundary({fetch_aa.URL: raiser})

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


def serving(*pages: str):
    """A urlopen route handler serving each page in turn, the last repeating.

    This is what AA midway through an update looks like to the stub: the
    same route answers a different snapshot on each read, then settles."""
    remaining = list(pages)

    def handler() -> _FakeResponse:
        page = remaining.pop(0) if remaining else pages[-1]
        return _FakeResponse(page)

    return handler


def dated_response(page: str, epoch: int) -> _FakeResponse:
    """A response carrying a Date header naming when its cache entry was
    generated -- what Vercel serves and what issue #100's diagnostics
    quote."""
    headers = email.message.Message()
    headers["Date"] = email.utils.formatdate(epoch, usegmt=True)
    return _FakeResponse(page, headers)


def serving_dated(*entries: tuple[int, str]):
    """serving(), where each page also carries its generation epoch in a
    Date header."""
    remaining = list(entries)

    def handler() -> _FakeResponse:
        epoch, page = remaining.pop(0) if remaining else entries[-1]
        return dated_response(page, epoch)

    return handler


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
    really sleeps. The nesting is pinned end to end: this retry lives
    INSIDE the issue #89 pair-level disagreement loop, and a refusal here
    still ends the capture -- the short-circuit that keeps a hard-down
    site failing fast inside the combined worst case documented beside
    fetch_aa's bounds.
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
                             [fetch_aa.URL, fetch_aa.URL, self.DETAIL_URL,
                              fetch_aa.AGENTS_URL])
            self.assertEqual(sleeps, [fetch_aa.PAGE_BACKOFF_SECONDS])
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

        routes = {fetch_aa.URL: unavailable}
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
            self.assertEqual(stub.calls,
                             [fetch_aa.URL] * fetch_aa.PAGE_ATTEMPTS)
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

        routes = {fetch_aa.URL: not_found}
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
            self.assertEqual(stub.calls, [fetch_aa.URL], "the 404 was retried")
            self.assertNotIn("retrying", captured["stderr"])
            self.assertNotIn("wrote", captured["stdout"])
            self.assertEqual((root / "aa-raw-models.json").read_bytes(),
                             b"SENTINEL MODELS CAPTURE")

    def test_the_page_retry_sits_inside_the_disagreement_loop(self):
        # The nesting pin: attempt 1's detail fetch eats one transient 500
        # (page retry, 5s backoff) and then answers a snapshot the
        # leaderboard disagrees with (pair retry, 120s wait); attempt 2's
        # pair agrees and the capture lands. Both retry levels visible in
        # one run, each with its own seam record.
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(self.LEADERBOARD),
            self.DETAIL_URL: flaky(
                urllib.error.HTTPError(self.DETAIL_URL, 500,
                                       "Internal Server Error",
                                       email.message.Message(), None),
                flight_html(detail_payload(intelligenceIndex=52)),
                flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_boundary(routes) as (_root, stub, sleeps, run,
                                                    _captured):
            stdout, stderr = run()

            self.assertEqual(
                stub.calls,
                [fetch_aa.URL, self.DETAIL_URL, self.DETAIL_URL,
                 fetch_aa.URL, self.DETAIL_URL, fetch_aa.AGENTS_URL])
            self.assertEqual(sleeps,
                             [fetch_aa.PAGE_BACKOFF_SECONDS,
                              fetch_aa.WAIT_SECONDS])
            self.assertIn(
                f"retrying in {fetch_aa.PAGE_BACKOFF_SECONDS}s", stderr)
            self.assertIn("re-reading both routes", stderr)
            self.assertIn("wrote aa-raw-models.json", stdout)


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


class RouteDisagreementRetryTests(unittest.TestCase):
    """Issue #89: a cross-route disagreement that clears within a bounded
    wait must not fail the hourly refresh. fetch_aa waits, re-reads BOTH
    routes, and compares a complete fresh pair each time -- proceeding once
    they agree, refusing with the unchanged diagnostic only past the bound
    (which, since issue #100, exits DISAGREEMENT_EXIT_CODE with the
    generation times on stderr, not the schema-change red).

    Every page comes through LoudUrlopenStub (unmodeled URLs raise rather
    than touch the network) and the sleep seam is a recorder, so no test
    really sleeps. The written captures are the observable for "never mix
    attempts": attempts can carry distinct sentinels, and the written bytes
    must be the SUCCESSFUL attempt's data alone.
    """

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")
    AGENTS = flight_html(agent_payload(
        [agent_row(f"Agent - Model {i}") for i in range(5)]))
    # A straddled pair from the measured stagger window: the two routes'
    # cached entries generated five minutes apart. The ISO strings the
    # stderr pins expect are 2026-10-04T03:20:00Z and 2026-10-04T03:25:00Z.
    WINDOW_BASE = 1791084000
    WINDOW_DETAIL = 1791084300

    @contextlib.contextmanager
    def capture_over_routes(self, routes: dict, *, seed: bool = False):
        """fetch_aa.main() over the stubbed urlopen with the sleep seam
        recorded. Yields (root, stub, sleeps, run, captured); call run()
        inside the block -- it returns (stdout, stderr) on success, and
        `captured` holds both buffers even when it raises. The written
        captures are readable under root while the block is open."""
        stub = LoudUrlopenStub(routes)
        sleeps: list = []
        with tempfile.TemporaryDirectory(prefix=".issue-89-retry-") as tmp:
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
                # create=True: the seam patch must also WORK against a tree
                # that predates the seam, so the red-on-main run of these
                # pins shows main's real behavior -- refusing on the first
                # disagreement -- rather than a missing-attribute error.
                with unittest.mock.patch.object(urllib.request, "urlopen", stub), \
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

    def test_an_agreeing_pair_captures_once_and_never_waits(self):
        # The quiet path is today's behavior, unchanged: one fetch of each
        # route, no wait, no stderr noise, and the capture lands.
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_routes(routes) as (root, stub, sleeps, run,
                                                  _captured):
            stdout, stderr = run()

            self.assertEqual(stub.calls,
                             [fetch_aa.URL, self.DETAIL_URL,
                              fetch_aa.AGENTS_URL])
            self.assertEqual(sleeps, [], "the quiet path slept")
            self.assertEqual(stderr, "", "the quiet path logged a retry")
            self.assertIn("wrote aa-raw-models.json", stdout)
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                datetime.date.today().isoformat() + "\n")

    def test_a_disagreement_that_clears_is_retried_and_captures_the_fresh_pair(self):
        # Attempt 1 straddles AA's update: the detail route's intelligenceIndex
        # is 52 against the leaderboard's 51 (the 2026-09-29 17:41Z window).
        # Attempt 2 reads a settled pair. The pin is the whole shape: BOTH
        # routes re-read (5 calls, not 3), exactly one wait at exactly the
        # constant, the retry announced once on stderr, and the capture that
        # lands is the fresh pair's.
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(flight_html(leaderboard_payload())),
            self.DETAIL_URL: serving(flight_html(detail_payload(intelligenceIndex=52)),
                                     flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_routes(routes, seed=True) as (root, stub, sleeps,
                                                             run, _captured):
            stdout, stderr = run()

            self.assertEqual(
                stub.calls,
                [fetch_aa.URL, self.DETAIL_URL,
                 fetch_aa.URL, self.DETAIL_URL,
                 fetch_aa.AGENTS_URL],
                "the injected fault did not visibly fire")
            self.assertEqual(sleeps, [fetch_aa.WAIT_SECONDS])
            self.assertEqual(stderr.count("re-reading"), 1, stderr)
            self.assertIn("attempt 1 of", stderr)
            self.assertIn("wrote aa-raw-models.json", stdout)
            models = json.loads(
                (root / "aa-raw-models.json").read_text(encoding="utf-8"))
            self.assertEqual([m["slug"] for m in models],
                             ["detail-host-model", "fixture-model"])
            self.assertEqual(
                len(json.loads(
                    (root / "aa-raw-coding-agents.json").read_text(encoding="utf-8"))),
                5)
            self.assertEqual(
                (root / "captured-at.txt").read_text(encoding="utf-8"),
                datetime.date.today().isoformat() + "\n")

    def test_the_retry_line_names_how_old_each_disagreeing_copy_was(self):
        # The intermediate-attempt stderr line appends the two generation
        # times in parens when the routes reported them (issue #100) -- the
        # observation the refresh's skip decision and the stamp's red alarm
        # are later argued from. Attempt 1 straddles with dated entries;
        # attempt 2 settles and the capture lands normally.
        routes = {
            fetch_aa.URL: lambda: dated_response(
                flight_html(leaderboard_payload()), self.WINDOW_BASE),
            self.DETAIL_URL: serving_dated(
                (self.WINDOW_DETAIL, flight_html(detail_payload(intelligenceIndex=52))),
                (self.WINDOW_DETAIL + 60, flight_html(detail_payload()))),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_routes(routes) as (_root, _stub, sleeps, run,
                                                  _captured):
            stdout, stderr = run()

            self.assertEqual(sleeps, [fetch_aa.WAIT_SECONDS])
            self.assertEqual(stderr.count("re-reading"), 1, stderr)
            self.assertIn(
                "re-reading both routes in 120s "
                "(leaderboard generated 2026-10-04T03:20:00Z, "
                "detail generated 2026-10-04T03:25:00Z)", stderr)
            self.assertIn("wrote aa-raw-models.json", stdout)

    def test_a_disagreement_past_the_bound_refuses_with_the_unchanged_diagnostic(self):
        # Every attempt straddles the update. The refusal is exit 3 (issue
        # #100) -- not the schema-change red -- with the unchanged divergence
        # text on stderr plus one appended line naming how old each copy was,
        # and the previous capture on disk untouched, because a refused run
        # writes nothing. Both header shapes are pinned: dated responses
        # carry the real ISO times, Date-less ones the explicit marker.
        for why, dated in (("no Date header", False), ("dated headers", True)):
            with self.subTest(why=why):
                if dated:
                    routes = {
                        fetch_aa.URL: lambda: dated_response(
                            flight_html(leaderboard_payload()), self.WINDOW_BASE),
                        self.DETAIL_URL: lambda: dated_response(
                            flight_html(detail_payload(intelligenceIndex=52)),
                            self.WINDOW_DETAIL),
                    }
                else:
                    routes = {
                        fetch_aa.URL: lambda: _FakeResponse(
                            flight_html(leaderboard_payload())),
                        self.DETAIL_URL: lambda: _FakeResponse(
                            flight_html(detail_payload(intelligenceIndex=52))),
                    }
                with self.capture_over_routes(routes, seed=True) as (
                        root, stub, sleeps, run, captured):
                    with self.assertRaises(SystemExit) as caught:
                        run()

                    self.assertEqual(caught.exception.code,
                                     fetch_aa.DISAGREEMENT_EXIT_CODE)
                    stderr = captured["stderr"]
                    self.assertIn("shared value(s) disagree", stderr)
                    self.assertIn(
                        "fixture-model: intelligenceIndex: leaderboard 51, detail 52",
                        stderr)
                    self.assertEqual(
                        stderr.count("re-reading"),
                        fetch_aa.ATTEMPTS - 1, stderr)
                    self.assertEqual(
                        sleeps,
                        [fetch_aa.WAIT_SECONDS] * (fetch_aa.ATTEMPTS - 1))
                    self.assertEqual(
                        stub.calls,
                        [fetch_aa.URL, self.DETAIL_URL] * fetch_aa.ATTEMPTS)
                    if dated:
                        self.assertIn(
                            "leaderboard generated 2026-10-04T03:20:00Z, "
                            "detail generated 2026-10-04T03:25:00Z — "
                            "Vercel serves the two routes from independent caches",
                            stderr)
                        # The intermediate lines carry the same observation in
                        # their parenthetical.
                        self.assertIn(
                            "(leaderboard generated 2026-10-04T03:20:00Z, "
                            "detail generated 2026-10-04T03:25:00Z)", stderr)
                    else:
                        self.assertIn(
                            "leaderboard generated (generation time unknown), "
                            "detail generated (generation time unknown)",
                            stderr)
                    self.assertEqual(
                        (root / "aa-raw-models.json").read_bytes(),
                        b"SENTINEL MODELS CAPTURE")
                    self.assertEqual(
                        (root / "aa-raw-coding-agents.json").read_bytes(),
                        b"SENTINEL AGENTS CAPTURE")
                    self.assertEqual(
                        (root / "captured-at.txt").read_text(encoding="utf-8"),
                        "2020-01-01\n",
                        "the stamp moved even though the capture did not land")

    def test_none_against_a_value_still_counts_as_disagreement(self):
        # The leaderboard measured 51 while the detail route's copy arrived
        # as null. A comparison loosened into "absent means agree" would
        # accept this pair outright (3 calls, no waits); the pin is that the
        # retry ENGAGES, then captures the settled pair.
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(flight_html(leaderboard_payload())),
            self.DETAIL_URL: serving(flight_html(
                detail_payload(intelligenceIndex=None)),
                                     flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_routes(routes) as (_root, stub, sleeps, run,
                                                  _captured):
            stdout, _ = run()

            self.assertGreaterEqual(
                len(sleeps), 1,
                "None-vs-value was accepted without a re-read")
            self.assertGreater(len(stub.calls), 3)
            self.assertEqual(sleeps, [fetch_aa.WAIT_SECONDS])
            self.assertEqual(stub.calls,
                             [fetch_aa.URL, self.DETAIL_URL,
                              fetch_aa.URL, self.DETAIL_URL,
                              fetch_aa.AGENTS_URL])
            self.assertIn("wrote aa-raw-models.json", stdout)

    def test_the_capture_keeps_only_the_successful_attempt_data(self):
        # Each attempt's detail route carries a distinct sentinel in a
        # detail-only field (`parameters` is absent from the leaderboard
        # record, so it never enters check_route_agreement's comparison and
        # survives the merge). The written capture must be attempt 2's --
        # exact, whole, and with no trace of attempt 1's sentinel.
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(flight_html(leaderboard_payload())),
            self.DETAIL_URL: serving(
                flight_html(detail_payload(intelligenceIndex=52,
                                           parameters=888001)),
                flight_html(detail_payload(parameters=888002))),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_routes(routes) as (root, _stub, sleeps, run,
                                                  _captured):
            _ = run()

            self.assertEqual(sleeps, [fetch_aa.WAIT_SECONDS])
            written = json.loads(
                (root / "aa-raw-models.json").read_text(encoding="utf-8"))
            expected = fetch_aa.merge_captures(
                json.loads(leaderboard_payload())["models"],
                json.loads(detail_payload(parameters=888002))["models"])
            self.assertEqual(written, expected)
            self.assertEqual(written[1]["parameters"], 888002)
            self.assertNotIn("888001",
                             (root / "aa-raw-models.json").read_text(encoding="utf-8"))

    def test_each_attempt_rereads_the_host_its_own_leaderboard_names(self):
        # detail_host_slug is recomputed per attempt: the detail page is
        # chosen for what its page EXCLUDES, so a retry must never pair
        # attempt 2's leaderboard with attempt 1's host -- the obvious
        # regression is reusing the stale host, or pairing fresh leaderboard
        # with stale page.
        detail1 = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")
        detail2 = fetch_aa.MODEL_DETAIL_URL.format(slug="second-host-model")
        routes = {
            fetch_aa.URL: serving(flight_html(leaderboard_payload()),
                                  flight_html(leaderboard_payload(
                                      host_slug="second-host-model"))),
            detail1: lambda: _FakeResponse(
                flight_html(detail_payload(intelligenceIndex=52))),
            detail2: lambda: _FakeResponse(flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(self.AGENTS),
        }
        with self.capture_over_routes(routes) as (_root, stub, sleeps, run,
                                                  _captured):
            stdout, _ = run()

            self.assertEqual(sleeps, [fetch_aa.WAIT_SECONDS])
            self.assertEqual(
                stub.calls,
                [fetch_aa.URL, detail1, fetch_aa.URL, detail2,
                 fetch_aa.AGENTS_URL])
            self.assertEqual(stub.calls[3], detail2,
                             "attempt 2 reused attempt 1's detail host")
            self.assertIn("wrote aa-raw-models", stdout)
            self.assertIn("/models/second-host-model", stdout)

    def test_a_fully_cached_capture_refuses_without_waiting_or_rereading(self):
        # --html/--detail-html pin the bytes: re-reading a file would return
        # the identical snapshot, so the bounded wait could never clear a
        # disagreement between two cached pages. One attempt, no seam call,
        # and the unchanged refusal -- which is also what keeps the #44
        # cached-page wiring pins instant instead of six minutes of sleep.
        with tempfile.TemporaryDirectory(prefix=".issue-89-cached-") as tmp:
            root = pathlib.Path(tmp)
            pages = [root / name for name in
                     ("leaderboard.html", "detail.html", "agents.html")]
            payloads = (leaderboard_payload(),
                        detail_payload(intelligenceIndex=52),
                        agent_payload([agent_row(f"Agent - Model {i}")
                                       for i in range(5)]))
            for path, payload in zip(pages, payloads):
                path.write_text(flight_html(payload), encoding="utf-8")
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            sleeps: list = []
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                fetch_aa.OUT.write_bytes(b"SENTINEL MODELS CAPTURE")
                fetch_aa.AGENTS_OUT.write_bytes(b"SENTINEL AGENTS CAPTURE")
                fetch_aa.STAMP.write_text("2020-01-01\n", encoding="utf-8")
                sys.argv = ["fetch_aa.py", "--html", str(pages[0]),
                            "--detail-html", str(pages[1]),
                            "--agents-html", str(pages[2])]
                err = io.StringIO()
                with unittest.mock.patch.object(fetch_aa, "_sleep",
                                                side_effect=sleeps.append):
                    with self.assertRaises(SystemExit) as caught:
                        with contextlib.redirect_stdout(io.StringIO()), \
                                contextlib.redirect_stderr(err):
                            fetch_aa.main()

                # Same exit-3 conversion as the network path (issue #100):
                # the diagnostic and the generation-time line land on stderr,
                # and cached pages have no headers, so both read as unknown.
                self.assertEqual(caught.exception.code,
                                 fetch_aa.DISAGREEMENT_EXIT_CODE)
                self.assertIn("shared value(s) disagree", err.getvalue())
                self.assertIn(
                    "fixture-model: intelligenceIndex: leaderboard 51, detail 52",
                    err.getvalue())
                self.assertIn(
                    "leaderboard generated (generation time unknown), "
                    "detail generated (generation time unknown)",
                    err.getvalue())
                self.assertEqual(sleeps, [],
                                 "a cached capture waited on the seam")
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def test_the_retry_catches_only_the_tagged_disagreement_exit(self):
        # A schema refusal is not the tagged disagreement exit, so the retry
        # loop must not catch it: refused inside the FIRST attempt (here by
        # the index-version pin), it propagates uncaught carrying the
        # version-bump message, with no wait, no re-read, no agents fetch,
        # and the previous capture on disk untouched. The seam itself is
        # left REAL: time.sleep is the observation point (as in the
        # seam-delegation pin), so "the seam was never called" is provable
        # -- and a mutant that widens the retry's except to bare SystemExit
        # fails here instead of really sleeping through its retries.
        bad_version = leaderboard_payload().replace(
            f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
            "Intelligence Index v9.9")
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(flight_html(bad_version)),
        }
        stub = LoudUrlopenStub(routes)
        with tempfile.TemporaryDirectory(prefix=".issue-89-schema-") as tmp:
            root = pathlib.Path(tmp)
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                # The previous capture, as a refused run must leave it.
                fetch_aa.OUT.write_bytes(b"SENTINEL MODELS CAPTURE")
                fetch_aa.AGENTS_OUT.write_bytes(b"SENTINEL AGENTS CAPTURE")
                fetch_aa.STAMP.write_text("2020-01-01\n", encoding="utf-8")
                sys.argv = ["fetch_aa.py"]
                with unittest.mock.patch.object(urllib.request, "urlopen", stub), \
                        unittest.mock.patch.object(fetch_aa.time, "sleep") as slept:
                    err = io.StringIO()
                    with self.assertRaises(SystemExit) as caught:
                        with contextlib.redirect_stdout(io.StringIO()), \
                                contextlib.redirect_stderr(err):
                            fetch_aa.main()

                message = str(caught.exception)
                self.assertIn("Intelligence Index v9.9", message)
                self.assertIn(f"v{fetch_aa.INDEX_VERSION}", message)
                self.assertIn("methodology", message)
                self.assertFalse(slept.called, "a schema refusal slept")
                self.assertEqual(
                    stub.calls, [fetch_aa.URL],
                    "a schema refusal was re-read, or the agents route "
                    "was fetched")
                self.assertNotIn("re-reading", err.getvalue())
                self.assertEqual((root / "aa-raw-models.json").read_bytes(),
                                 b"SENTINEL MODELS CAPTURE")
                self.assertEqual(
                    (root / "aa-raw-coding-agents.json").read_bytes(),
                    b"SENTINEL AGENTS CAPTURE")
                self.assertEqual(
                    (root / "captured-at.txt").read_text(encoding="utf-8"),
                    "2020-01-01\n",
                    "the stamp moved even though the capture did not land")
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old


class RetryBoundArithmeticTests(unittest.TestCase):
    """Issue #89: the retry bound must fit inside refresh.yml's 30-minute
    job timeout WITHOUT editing the workflow, so the fit is pinned as an
    assertion rather than narrated. A future constant bump that would crowd
    out the heal-run remainder (checkout, pip + Chromium, the browser suite,
    build, publish -- ~7 min measured) fails here instead of timing out a
    real run."""

    def test_worst_case_stays_within_the_capture_budget(self):
        # The comment in fetch_aa.py commits to exactly this arithmetic: the
        # disagreement waits, the pair fetches at the PAGE fetch bound --
        # each page fetch itself a bounded retry since issue #154 -- and
        # the one agents fetch after a pair agrees. 1200 s is the capture
        # budget that leaves the ~7-min heal remainder room in the job's
        # 1800 s, with slack.
        page_bound = (fetch_aa.PAGE_ATTEMPTS * fetch_aa.FETCH_TIMEOUT_SECONDS
                      + sum(k * fetch_aa.PAGE_BACKOFF_SECONDS
                            for k in range(1, fetch_aa.PAGE_ATTEMPTS)))
        worst_case = ((fetch_aa.ATTEMPTS - 1) * fetch_aa.WAIT_SECONDS
                      + fetch_aa.ATTEMPTS * 2 * page_bound
                      + page_bound)

        self.assertLessEqual(worst_case, 1200)

    def test_a_hard_down_site_fails_inside_the_first_page_bound(self):
        # Issue #154's fail-fast half: transport exhaustion short-circuits
        # the capture, so a dead AA is refused inside ONE page bound --
        # never the disagreement loop's full product -- and the hour's run
        # goes red fast instead of hanging toward the job timeout. Bound
        # at WAIT_SECONDS so the invariant is relational: one page bound
        # never outlasts one pair-retry wait (page bound 90 s, wait 120 s).
        page_bound = (fetch_aa.PAGE_ATTEMPTS * fetch_aa.FETCH_TIMEOUT_SECONDS
                      + sum(k * fetch_aa.PAGE_BACKOFF_SECONDS
                            for k in range(1, fetch_aa.PAGE_ATTEMPTS)))

        self.assertLessEqual(page_bound, fetch_aa.WAIT_SECONDS)

    def test_the_sleep_seam_actually_sleeps(self):
        # The seam exists so no TEST ever really sleeps -- and so the wait
        # is real in production. Patching time.sleep itself proves the seam
        # delegates rather than no-ops. (The seam itself is the unit under
        # test here, hence the protected-access.)
        with unittest.mock.patch.object(fetch_aa.time, "sleep") as fake:
            fetch_aa._sleep(5)  # pylint: disable=protected-access

        fake.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()


# --- the refusal writes a buildable snapshot (issue #118) ------------------------

def snapshot_path_of() -> pathlib.Path:
    """The disagreement snapshot's path beside the module's (test) OUT."""
    return fetch_aa.OUT.with_name("aa-disagreement-snapshot.json")


class DisagreementSnapshotTests(unittest.TestCase):
    """Issue #118: the route-disagreement refusal is buildable. fetch_aa.py
    still exits DISAGREEMENT_EXIT_CODE with the unchanged diagnostic, but the
    refused attempt now also writes data/aa-disagreement-snapshot.json -- both
    routes' raw payloads plus the disagreement map -- so the refresh can build
    and publish the disputed page instead of holding it. The snapshot's pieces
    all come from the refused attempt; the schema guards stay red on the
    disputed merge."""

    DETAIL_URL = fetch_aa.MODEL_DETAIL_URL.format(slug="detail-host-model")

    @contextlib.contextmanager
    def refused_capture(self, routes: dict, *, seed_stamp: str | None = None):
        """fetch_aa.main() over the stubbed urlopen, with the module's
        capture paths redirected into a temp tree. Yields (root, run,
        captured); `captured` holds both buffers when run() raises."""
        stub = LoudUrlopenStub(routes)
        with tempfile.TemporaryDirectory(prefix=".issue-118-snapshot-") as tmp:
            root = pathlib.Path(tmp)
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                if seed_stamp is not None:
                    (root / "data" / "aa-route-disagreement.txt").parent.mkdir(
                        parents=True, exist_ok=True)
                    (root / "data" / "aa-route-disagreement.txt").write_text(
                        seed_stamp, encoding="utf-8")
                sys.argv = ["fetch_aa.py"]
                with unittest.mock.patch.object(urllib.request, "urlopen",
                                                stub), \
                        unittest.mock.patch.object(fetch_aa, "_sleep",
                                                   side_effect=lambda s: None):
                    out, err = io.StringIO(), io.StringIO()

                    def run():
                        with contextlib.redirect_stdout(out), \
                                contextlib.redirect_stderr(err):
                            try:
                                fetch_aa.main()
                            finally:
                                captured["stdout"] = out.getvalue()
                                captured["stderr"] = err.getvalue()
                        return captured["stdout"], captured["stderr"]

                    captured: dict = {"stdout": "", "stderr": ""}
                    yield root, run, captured
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def routes_forever_disagreeing(self, *, dated: bool = False) -> dict:
        detail = flight_html(detail_payload(intelligenceIndex=52))
        if dated:
            return {
                fetch_aa.URL: lambda: dated_response(
                    flight_html(leaderboard_payload()), 1791084000),
                self.DETAIL_URL: lambda: dated_response(detail, 1791084300),
            }
        return {
            fetch_aa.URL: lambda: _FakeResponse(
                flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(detail),
        }

    def test_the_refusal_writes_a_buildable_snapshot(self):
        for why, dated in (("undated", False), ("dated", True)):
            with self.subTest(why=why):
                with self.refused_capture(self.routes_forever_disagreeing(
                        dated=dated)) as (_root, run, captured):
                    with self.assertRaises(SystemExit) as caught:
                        run()

                    self.assertEqual(caught.exception.code,
                                     fetch_aa.DISAGREEMENT_EXIT_CODE)
                    stderr = captured["stderr"]
                    self.assertIn("shared value(s) disagree", stderr)
                    self.assertIn(
                        "fixture-model: intelligenceIndex: leaderboard 51, "
                        "detail 52", stderr)
                    raw = snapshot_path_of().read_text(encoding="utf-8")
                    snapshot = json.loads(raw)
                    self.assertEqual(snapshot["schema"], 1)
                    self.assertEqual(
                        [m["slug"] for m in snapshot["leaderboard"]],
                        ["detail-host-model", "fixture-model"])
                    self.assertEqual(
                        [m["slug"] for m in snapshot["detail"]],
                        ["fixture-model"])
                    self.assertEqual(snapshot["disagreements"],
                                     [{"slug": "fixture-model",
                                       "path": "intelligenceIndex",
                                       "lb": 51, "dt": 52}])
                    if dated:
                        self.assertEqual(snapshot["leaderboardGeneratedAt"],
                                         1791084000)
                        self.assertEqual(snapshot["detailGeneratedAt"],
                                         1791084300)
                    else:
                        self.assertIsNone(snapshot["leaderboardGeneratedAt"])
                        self.assertIsNone(snapshot["detailGeneratedAt"])
                    self.assertIsInstance(snapshot["windowStartEpoch"], int)
                    self.assertRegex(snapshot["capturedAt"],
                                     r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_the_window_start_comes_from_the_stamp_when_one_exists(self):
        # The banner names ONE window across hours: an existing workflow
        # stamp's first line is the window's start, and this fetch must not
        # reset it to now.
        with self.refused_capture(
                self.routes_forever_disagreeing(),
                seed_stamp="1791080000\ncaptured before\n") as (
                        _root, run, _captured):
            with self.assertRaises(SystemExit):
                run()

            snapshot = json.loads(snapshot_path_of().read_text(encoding="utf-8"))
            self.assertEqual(snapshot["windowStartEpoch"], 1791080000)

    def test_the_refusal_still_reds_on_a_broken_detail_schema(self):
        # Only the disagreement stopped being red: a detail payload that has
        # lost what build.py reads fails the schema guard on the disputed
        # merge -- exit 1, NOT the disagreement exit, and NO snapshot is
        # written for a capture that cannot be built.
        detail = flight_html(detail_payload(
            intelligenceIndexCostPerTask={
                "cost": {"total": 1.0},
                "evaluations": [
                    {"slug": "scicode", "weightedCostPerTask": 1.0}]}))
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(
                flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(detail),
        }
        with self.refused_capture(routes) as (_root, run, _captured):
            with self.assertRaises(SystemExit) as caught:
                run()

            # The guard's SystemExit carries its message, not a number: the
            # process exit code would be 1 -- red, and specifically NOT the
            # disagreement exit the refresh would publish from.
            self.assertNotEqual(caught.exception.code,
                                fetch_aa.DISAGREEMENT_EXIT_CODE)
            self.assertIn("gdpval-aa", str(caught.exception))
            self.assertFalse(snapshot_path_of().exists(),
                             "a broken disputed merge wrote a snapshot anyway")

    def test_an_agreeing_capture_drops_a_leftover_snapshot(self):
        # The window closes: the agreeing capture must not leave a stale
        # snapshot behind to put the next build into disputed mode from
        # dead data.
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(
                flight_html(leaderboard_payload())),
            self.DETAIL_URL: lambda: _FakeResponse(flight_html(detail_payload())),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(flight_html(
                agent_payload([agent_row(f"Agent - Model {i}")
                               for i in range(5)]))),
        }
        with self.refused_capture(routes) as (_root, run, _captured):
            snap = snapshot_path_of()
            snap.write_text('{"schema": 1}', encoding="utf-8")
            stdout, _stderr = run()

            self.assertIn("wrote aa-raw-models.json", stdout)
            self.assertFalse(snap.exists(),
                             "an agreeing capture left a stale snapshot")

    def test_the_retry_bound_arithmetic_is_unchanged_by_the_refusal_path(self):
        # The refusal path deliberately does NOT fetch the coding-agents
        # page: adding that fetch to the worst case (3 waits + 8 page-bound
        # fetches + 1 agents fetch) would break the 1200 s capture budget
        # the suite pins. The agents capture a disputed build renders is the
        # last-good one in data/, not a fresh fetch.
        page_bound = (fetch_aa.PAGE_ATTEMPTS * fetch_aa.FETCH_TIMEOUT_SECONDS
                      + sum(k * fetch_aa.PAGE_BACKOFF_SECONDS
                            for k in range(1, fetch_aa.PAGE_ATTEMPTS)))
        worst_case = ((fetch_aa.ATTEMPTS - 1) * fetch_aa.WAIT_SECONDS
                      + fetch_aa.ATTEMPTS * 2 * page_bound
                      + page_bound)
        self.assertLessEqual(worst_case, 1200)


# ---------------------------------------------------------------------------
# Issue #176: the stale-route heal (Overseer ruling (delegated by the
# maintainer), 2026-10-04). When ALL of one route's disputed values equal the
# last committed capture and NONE of the other route's do, the matching route
# is stale: its values are dropped and the fresh route publishes undisputed
# through the normal capture path. The pinned fixture is the 909ca49 window,
# trimmed (tests/fixtures/issue-176/, provenance in its README): all 9 kept
# detail values equal the a0ff4ad baseline, none of the leaderboard's do.
# The suite never writes into data/: every main()-level test redirects
# fetch_aa.OUT / AGENTS_OUT / STAMP into a temp tree and loads the fixture
# baseline read-only.

import build  # noqa: E402  # pylint: disable=wrong-import-position

FIXTURE_176_DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "issue-176"


def issue176_snapshot() -> dict:
    """The trimmed 909ca49 disagreement snapshot."""
    return json.loads(
        (FIXTURE_176_DIR / "disagreement-snapshot.json").read_text(encoding="utf-8"))


def issue176_baseline() -> list:
    """The trimmed a0ff4ad capture -- the last agreeing capture."""
    return json.loads(
        (FIXTURE_176_DIR / "last-capture.json").read_text(encoding="utf-8"))


def issue176_exc() -> fetch_aa._RouteDisagreement:
    """The fixture window as the retry loop's last attempt raises it."""
    snap = issue176_snapshot()
    divergences = [(e["slug"], e["path"], e["lb"], e["dt"])
                   for e in snap["disagreements"]]
    return fetch_aa._RouteDisagreement(  # pylint: disable=protected-access
        f"{len(divergences)} shared value(s) disagree between the leaderboard "
        "route and the model detail route; the gap-fill merge keeps the "
        "leaderboard's copy:\n  (fixture)",
        snap["leaderboardGeneratedAt"], snap["detailGeneratedAt"],
        snap["leaderboard"], snap["detail"], divergences)


def issue176_by_slug(payload: list) -> dict:
    return {m["slug"]: m for m in payload}


def leaderboard_stale_baseline() -> list:
    """The fixture payloads modelled as a window where the LEADERBOARD's
    generation was the last committed one. A committed capture always pairs
    agreeing values, so such a window's baseline carries the leaderboard's
    copy of the shape-split total; the fixture's real window disagrees on
    it, so this re-pairs the baseline object's total with the leaderboard's
    copy before the merge. Everything else is merge_captures of the two
    payloads -- detail-only fields from the detail payload, shared values
    from the leaderboard. See tests/fixtures/issue-176/README.md."""
    snap = issue176_snapshot()
    lb = issue176_by_slug(snap["leaderboard"])
    detail = []
    for m in snap["detail"]:
        lb_rec = lb.get(m.get("slug"))
        outer = m.get("intelligenceIndexCostPerTask")
        lb_total = (lb_rec or {}).get("intelligenceIndexCostPerTask")
        if (isinstance(outer, dict) and isinstance(outer.get("cost"), dict)
                and isinstance(lb_total, (int, float))
                and not isinstance(lb_total, bool)):
            outer = {**outer,
                     "cost": {**outer["cost"], "total": lb_total}}
            detail.append({**m, "intelligenceIndexCostPerTask": outer})
        else:
            detail.append(m)
    return build.merge_captures(snap["leaderboard"], detail)


class StaleRouteHealTests(unittest.TestCase):
    """The provably-stale route's heal, pinned on the 909ca49 fixture."""

    FRESH_TOTAL = 0.47742401619163854   # deepseek, leaderboard (21:05) copy
    STALE_TOTAL = 0.3296953563474809    # deepseek, detail (18:41) == baseline

    def healed(self, baseline):
        exc = issue176_exc()
        verdict = fetch_aa.heal_route_disagreement(exc, baseline)
        return verdict

    def test_the_real_window_heals_with_the_detail_route_stale(self):
        models, note = self.healed(issue176_baseline())
        by_slug = issue176_by_slug(models)
        snap = issue176_snapshot()
        dt = issue176_by_slug(snap["detail"])
        lb = issue176_by_slug(snap["leaderboard"])

        # deepseek: the fresh scalar total replaces the stale object --
        # absent rather than mixed. Every shared scalar takes the fresh
        # leaderboard's copy.
        deepseek = by_slug["deepseek-v4-pro-non-reasoning"]
        self.assertIsInstance(deepseek["intelligenceIndexCostPerTask"], (int, float))
        self.assertEqual(deepseek["intelligenceIndexCostPerTask"], self.FRESH_TOTAL)
        self.assertEqual(deepseek["gdpvalNormalized"],
                         lb["deepseek-v4-pro-non-reasoning"]["gdpvalNormalized"])
        self.assertEqual(deepseek["name"], lb["deepseek-v4-pro-non-reasoning"]["name"])
        self.assertEqual(deepseek["price1mInputTokens"], 1.32)

        # Stale detail-only fields stay at their last capture.
        for field in ("parameters", "licenseName", "releaseDate"):
            self.assertEqual(deepseek[field], dt["deepseek-v4-pro-non-reasoning"][field])

        # GDPval cost: absent for the cost-moved model, rendered for models
        # whose cost did not move.
        self.assertIsNone(build.evaluation_cost_per_task(
            deepseek, build.GDPVAL_SLUG, build.GDPVAL_INDEX_WEIGHT))
        # claude-fable-5: the score moved, the cost did not -- the stale
        # breakdown stays at its last capture and still pairs with its
        # unchanged total, so the GDPval cost renders.
        fable = by_slug["claude-fable-5"]
        self.assertIsNotNone(build.evaluation_cost_per_task(
            fable, build.GDPVAL_SLUG, build.GDPVAL_INDEX_WEIGHT))

        # And it feeds the page: the intelligence pair is fresh, the agentic
        # pair is absent only where the cost moved.
        self.assertEqual(build.cost_per_task(deepseek), self.FRESH_TOTAL)
        self.assertIsNone(build.metric_record(deepseek, "agentic"))
        self.assertIsNotNone(build.metric_record(fable, "agentic"))

        # The repaired capture passes the sum check unchanged.
        self.assertGreater(fetch_aa.check_cost_breakdown(models), 0)

        # The note names the stale route and the absent count.
        self.assertIn("detail route is stale", note)
        self.assertIn("1 GDPval cost", note)

    def test_the_leaderboard_stale_direction_heals(self):
        # The synthetic second direction (#117 ran it for real): the same
        # captured payloads, but the baseline is the merge of those payloads
        # -- a modelling of a window where the leaderboard's generation was
        # already published. See tests/fixtures/issue-176/README.md.
        snap = issue176_snapshot()
        baseline = leaderboard_stale_baseline()
        models, note = self.healed(baseline)
        by_slug = issue176_by_slug(models)
        dt = issue176_by_slug(snap["detail"])

        self.assertIn("leaderboard route is stale", note)

        # Every divergent path takes the detail route's copy -- including the
        # cost total, which the fresh detail object already carried.
        deepseek = by_slug["deepseek-v4-pro-non-reasoning"]
        self.assertEqual(
            deepseek["intelligenceIndexCostPerTask"]["cost"]["total"],
            self.STALE_TOTAL)
        self.assertEqual(
            deepseek["intelligenceIndexCostPerTask"]["cost"]["total"],
            dt["deepseek-v4-pro-non-reasoning"]["intelligenceIndexCostPerTask"]["cost"]["total"])
        self.assertEqual(deepseek["gdpvalNormalized"],
                         dt["deepseek-v4-pro-non-reasoning"]["gdpvalNormalized"])
        self.assertEqual(deepseek["name"], dt["deepseek-v4-pro-non-reasoning"]["name"])

        # The fresh breakdown pairs with the fresh total: GDPval renders, and
        # the sum check passes unchanged.
        self.assertIsNotNone(build.evaluation_cost_per_task(
            deepseek, build.GDPVAL_SLUG, build.GDPVAL_INDEX_WEIGHT))
        self.assertGreater(fetch_aa.check_cost_breakdown(models), 0)

    def test_mixed_matches_fall_back_to_disputed(self):
        baseline = issue176_baseline()
        exc = issue176_exc()
        # One leaderboard value swapped to the baseline's copy: the
        # leaderboard now matches 1 of 9 -- provable staleness is gone.
        slug, path, _lb, dt = exc.divergences[0]
        base = issue176_by_slug(baseline)[slug]
        parts = path.split(".")
        base_value = base
        for part in parts:
            base_value = base_value[part]
        exc.divergences[0] = (slug, path, base_value, dt)
        self.assertIsNone(fetch_aa.heal_route_disagreement(exc, baseline))

    def test_both_routes_differing_falls_back_to_disputed(self):
        baseline = issue176_baseline()
        exc = issue176_exc()
        # Nudge every value away from both the baseline and each other: the
        # routes agree with neither generation.
        exc.divergences = [
            (slug, path, lb + 1000.0, dt + 2000.0)
            if isinstance(lb, (int, float)) and isinstance(dt, (int, float))
            else (slug, path, f"new-{lb}", f"new-{dt}")
            for slug, path, lb, dt in exc.divergences
        ]
        self.assertIsNone(fetch_aa.heal_route_disagreement(exc, baseline))

    def test_a_slug_without_a_baseline_row_falls_back_to_disputed(self):
        baseline = issue176_baseline()
        exc = issue176_exc()
        exc.divergences = [
            ("brand-new-model", "gdpvalNormalized", 0.5, 0.6)]
        exc.base = issue176_snapshot()["leaderboard"]
        self.assertIsNone(fetch_aa.heal_route_disagreement(exc, baseline))

    def test_a_missing_baseline_falls_back_to_disputed(self):
        self.assertIsNone(fetch_aa.heal_route_disagreement(issue176_exc(), None))

    def test_the_mixed_pairing_is_refused_by_the_sum_check(self):
        # The explicit refusal path: a stale breakdown left under a moved
        # total is exactly what check_cost_breakdown refuses -- which is why
        # the heal drops the breakdown instead of pairing it.
        dt = issue176_by_slug(issue176_snapshot()["detail"])[
            "deepseek-v4-pro-non-reasoning"]
        mixed = dict(dt)
        mixed["intelligenceIndexCostPerTask"] = {
            "cost": {"total": self.FRESH_TOTAL},
            "evaluations": dt["intelligenceIndexCostPerTask"]["evaluations"],
        }
        with self.assertRaises(SystemExit) as caught:
            fetch_aa.check_cost_breakdown([mixed])
        self.assertIn("deepseek-v4-pro-non-reasoning", str(caught.exception))

    def test_a_healed_refusal_captures_through_the_normal_path(self):
        snap = issue176_snapshot()
        lb_page = flight_html(json.dumps(
            {"intro": f"Intelligence Index v{fetch_aa.INDEX_VERSION}",
             "models": snap["leaderboard"]}, separators=(",", ":")))
        host = fetch_aa.detail_host_slug(snap["leaderboard"])
        detail_page = flight_html(json.dumps(
            {"models": snap["detail"]}, separators=(",", ":")))
        agents_page = flight_html(agent_payload(
            [agent_row(f"Agent - Model {i}") for i in range(5)]))
        routes = {
            fetch_aa.URL: lambda: _FakeResponse(lb_page),
            fetch_aa.MODEL_DETAIL_URL.format(slug=host): lambda: _FakeResponse(detail_page),
            fetch_aa.AGENTS_URL: lambda: _FakeResponse(agents_page),
        }
        stub = LoudUrlopenStub(routes)
        with tempfile.TemporaryDirectory(prefix=".issue-176-heal-") as tmp:
            root = pathlib.Path(tmp)
            old = (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                   fetch_aa.STAMP)
            argv = sys.argv
            try:
                fetch_aa.ROOT = root
                fetch_aa.OUT = root / "aa-raw-models.json"
                fetch_aa.AGENTS_OUT = root / "aa-raw-coding-agents.json"
                fetch_aa.STAMP = root / "captured-at.txt"
                # The last committed capture: the fixture baseline.
                fetch_aa.OUT.write_text(json.dumps(issue176_baseline()),
                                        encoding="utf-8")
                sys.argv = ["fetch_aa.py"]
                with unittest.mock.patch.object(urllib.request, "urlopen", stub), \
                        unittest.mock.patch.object(fetch_aa, "_sleep",
                                                   side_effect=lambda s: None):
                    out, err = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(out), \
                            contextlib.redirect_stderr(err):
                        fetch_aa.main()   # heals: no SystemExit
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

            stdout, stderr = out.getvalue(), err.getvalue()
            self.assertIn("route disagreement resolved", stderr)
            self.assertIn("detail route is stale", stderr)
            self.assertIn("wrote aa-raw-models.json", stdout)
            healed = json.loads((root / "aa-raw-models.json").read_text(encoding="utf-8"))
            deepseek = issue176_by_slug(healed)["deepseek-v4-pro-non-reasoning"]
            self.assertEqual(deepseek["intelligenceIndexCostPerTask"], self.FRESH_TOTAL)
            self.assertFalse((root / "aa-disagreement-snapshot.json").exists(),
                             "a healed capture wrote the disputed snapshot")
            self.assertTrue((root / "aa-raw-coding-agents.json").exists(),
                            "the heal skipped the coding-agents capture")
            self.assertTrue((root / "captured-at.txt").exists(),
                            "the heal skipped the capture stamp")
