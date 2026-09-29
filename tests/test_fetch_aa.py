import contextlib
import datetime
import email.message
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

    def run_capture(self, leaderboard: str, detail: str, agents: str) -> str:
        """Drive fetch_aa.main() over cached pages; -> the captured stdout."""
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
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    fetch_aa.main()
                return buffer.getvalue()
            finally:
                sys.argv = argv
                (fetch_aa.ROOT, fetch_aa.OUT, fetch_aa.AGENTS_OUT,
                 fetch_aa.STAMP) = old

    def test_a_cross_route_divergence_refuses_the_real_capture_before_the_merge(self):
        # One delta from the healthy capture: the detail route's copy of
        # intelligenceIndex moves. The refusal must name the model, the field
        # and both values -- the agreement check's own message, not a
        # downstream schema guard's.
        with self.assertRaises(SystemExit) as caught:
            self.run_capture(
                leaderboard_payload(),
                detail_payload(intelligenceIndex=52),
                agent_payload([agent_row(f"Agent - Model {i}") for i in range(5)]))

        message = str(caught.exception)
        self.assertIn("shared value(s) disagree", message)
        self.assertIn(
            "fixture-model: intelligenceIndex: leaderboard 51, detail 52",
            message)

    def test_a_capture_whose_routes_agree_runs_the_check_and_writes_through(self):
        # The healthy control: the fixture capture is valid end to end, the
        # check passes over it, and the capture log carries the compared
        # count -- the observable that shows the call ran. 24 = the 21 filler
        # fields the routes share, slug, intelligenceIndex, and the
        # leaderboard's flattened 0.75 against the detail object's
        # cost.total.
        stdout = self.run_capture(
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
                        urllib.request, "urlopen", stub):
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
        # naming the URL and carrying the underlying reason.
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

    def test_the_guarded_refusal_is_the_whole_of_stderr_at_exit_one(self):
        # End to end: a subprocess whose urlopen is stubbed before fetch_aa
        # loads. The observable is the process's -- exit 1, stderr exactly
        # the actionable line, and no traceback anywhere.
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
                "fetch_aa.main()\n",
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(runner)],
                capture_output=True, text=True, timeout=120, check=False)

        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1,
                         proc.stderr)
        self.assertIn("fetch failed", proc.stderr)
        self.assertIn("Connection refused", proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
