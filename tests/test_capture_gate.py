"""Pins on scripts/capture_gate.py -- the rendered no-change gate.

The script answers exactly one question, on stdout: would the page the fresh
capture in data/ builds differ from the page HEAD's capture builds, once the
build-machine provenance (source stamp, capture date, raw-byte digest) is
normalized out? The hourly refresh commits and publishes on `true` and stays
silent on `false`, so these pins are on the DECISION, not the mechanism:
raw-only churn votes false, a rendered change votes true, provenance never
votes, no capture at HEAD fails open toward publishing, and a capture the
builder cannot parse fails red.
"""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import capture_gate  # noqa: E402  # pylint: disable=wrong-import-position
import diff_aa  # noqa: E402  # pylint: disable=wrong-import-position
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

# The real captures work as fixtures and are fast (a full build measures
# ~0.1 s); the suite already builds from them twice. The FRESH side of the
# gate reads data/ directly, so tests stay hermetic by monkeypatching both
# factored reads -- nothing here writes to the working tree.
REAL_MODELS = (build.ROOT / "data" / "aa-raw-models.json").read_bytes()
REAL_AGENTS = (build.ROOT / "data" / "aa-raw-coding-agents.json").read_bytes()


def run_gate() -> tuple[int, str]:
    """capture_gate.main() with stdout captured; returns (exit, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = capture_gate.main()
    return code, out.getvalue()


def head_serving(*captures: bytes):
    """A capture_gate.read_head_captures patched to hand back these bytes."""
    return mock.patch.object(capture_gate, "read_head_captures",
                             return_value=tuple(captures))


def churn(models: bytes) -> bytes:
    """The same capture, different bytes: every object's keys reordered, so
    nothing parsed changes and nothing rendered can change."""
    return json.dumps(json.loads(models), indent=1, sort_keys=True).encode()


def disputed_capture(models: bytes) -> bytes:
    """The capture with five models carrying the in-run disputed encoding
    (issue #226's fixture): `genVariants` -- one map per generation, the
    empty map the generation that does NOT carry the model (a missing key
    would be a missing marker, a different thing) and the carried map the
    record's own published values, so the plain fields stay the
    canonical-first variant's.

    Four carry the cross-run readded shape refresh run 37682958494 caught
    (three with the pad FIRST, one with it last), and one carries a
    cross-run dropped record (crossRunMerged: true) -- every shape
    genVariants takes. The mutation lives in memory only -- never a data/
    write. Self-contained by this file's convention: no import from the
    build tests.
    """
    parsed = json.loads(models)
    widened = 0
    for m in parsed:
        if widened >= 5:
            break
        ii = m.get("intelligenceIndex")
        outer = m.get("intelligenceIndexCostPerTask")
        total = (outer.get("cost", {}).get("total")
                 if isinstance(outer, dict) else None)
        if not isinstance(ii, (int, float)) or isinstance(ii, bool):
            continue
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            continue
        carried = {"ii": ii, "cost": total}
        for key in ("contextWindowTokens", "price1mInputTokens",
                    "price1mOutputTokens"):
            value = m.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                carried[{"contextWindowTokens": "ctx",
                         "price1mInputTokens": "pin",
                         "price1mOutputTokens": "pout"}[key]] = value
        if widened == 3:
            m["genVariants"] = [carried, {}]
        elif widened == 4:
            m["crossRunMerged"] = True
            m["genVariants"] = [{}, carried]
        else:
            m["genVariants"] = [{}, carried]
        widened += 1
    if widened < 5:
        raise AssertionError("fewer than five renderable models in the "
                             "fixture capture")
    return json.dumps(parsed, indent=1).encode()


def rendered_field_changed(models: bytes) -> bytes:
    """The same capture with one model's rendered number moved: the first
    model whose Intelligence Index the page actually renders (score AND paired
    measured cost) gets it bumped by 1.0, which lands on the page's
    intelligence axis whatever the frontier does around it. Selection goes
    through build.metric_record itself, so the mutated field is rendered by
    construction -- the exact trap the raw gate fell into, in reverse."""
    parsed = json.loads(models)
    for m in parsed:
        if build.metric_record(m, "intelligence") is not None:
            m["intelligenceIndex"] = round(m["intelligenceIndex"] + 1.0, 4)
            return json.dumps(parsed, indent=1).encode()
    raise AssertionError("no rendered intelligence row in the fixture capture")


def with_tps(models: bytes, value: float) -> bytes:
    """The capture with one rendered model's output-tokens/sec set to `value`.

    Pinned to a round 100.0 so the pair tests sit unambiguously on one side
    or the other of the per-cell threshold: 110 is +10% (jitter), 150 is
    +50% (news).
    """
    parsed = json.loads(models)
    for m in parsed:
        if build.metric_record(m, "intelligence") is not None:
            m["medianOutputTokensPerSecond"] = value
            return json.dumps(parsed, indent=1).encode()
    raise AssertionError("no rendered model row in the fixture capture")


class CaptureGateTests(unittest.TestCase):
    def setUp(self):
        # Whatever a test does to build's module globals or the environment,
        # the gate must hand them back exactly as it found them: the suite
        # runs other tests against the real data/ and the real out/.
        self._saved = (build.RAW, build.AGENTS_RAW, build.OUT)

    def tearDown(self):
        self.assertEqual((build.RAW, build.AGENTS_RAW, build.OUT), self._saved)

    def test_identical_captures_are_not_a_change(self):
        with head_serving(REAL_MODELS, REAL_AGENTS):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "false\n"))

    def test_a_rendered_change_is_a_change(self):
        with head_serving(rendered_field_changed(REAL_MODELS), REAL_AGENTS):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_sub_threshold_speed_drift_is_not_a_change(self):
        # The ruling's contract: a sub-25% re-sample of a rendered speed
        # field is jitter, not news -- the gate must agree with diff_aa's
        # --speed-tol or the repo keeps producing commits whose own subject
        # says "nothing the page renders". 100 -> 110 tokens/sec sits inside
        # one ladder rung; the page compares equal.
        head = with_tps(REAL_MODELS, 100.0)
        fresh = with_tps(REAL_MODELS, 110.0)
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(fresh, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "false\n"))

    def test_a_threshold_speed_move_is_a_change(self):
        # 100 -> 150 tokens/sec is a 50% relative move: past the differ's
        # threshold, a different rendered cell, news.
        head = with_tps(REAL_MODELS, 100.0)
        fresh = with_tps(REAL_MODELS, 150.0)
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(fresh, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_a_speed_field_vanishing_commits(self):
        # A structural presence change commits even on a speed field:
        # nothing is reconciled when the cell exists on one side only, so
        # the fresh page renders an em-dash where HEAD renders a number.
        head = with_tps(REAL_MODELS, 100.0)
        parsed = json.loads(with_tps(REAL_MODELS, 110.0))
        for m in parsed:
            if m.get("medianOutputTokensPerSecond") == 110.0:
                del m["medianOutputTokensPerSecond"]
        fresh = json.dumps(parsed, indent=1).encode()
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(fresh, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_raw_only_churn_is_not_a_change(self):
        # The gate this script replaces compared raw bytes and voted true on
        # exactly this fixture -- 23 of 30 refresh commits. Reordering keys
        # changes nothing the page parses, renders or (after masking) prints.
        with head_serving(churn(REAL_MODELS), churn(REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "false\n"))

        # Issue #226: the same churn over a disputed capture, both sides
        # disputed (the fresh side patched the same way the speed tests
        # patch theirs). genVariants rides the rows, and a page that let
        # the capture's key layout into the embedded dispute maps votes
        # true on exactly this fixture -- the vote that turned refresh run
        # 37682958494's hour red.
        disputed = disputed_capture(REAL_MODELS)
        with head_serving(churn(disputed), churn(REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(disputed, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "false\n"))

    def test_the_only_difference_masked_away_is_the_capture_digest(self):
        # On raw-only churn the two built pages genuinely differ -- in the
        # 64-hex digest inside `Capture <code>...</code>` and nowhere else --
        # and the mask removes exactly that, anchored on the prose.
        with head_serving(churn(REAL_MODELS), churn(REAL_AGENTS)):
            old_page, new_page = capture_gate.build_page_pair(
                (churn(REAL_MODELS), churn(REAL_AGENTS)),
                (REAL_MODELS, REAL_AGENTS))

        self.assertNotEqual(old_page, new_page)
        self.assertEqual(capture_gate.mask_digest(old_page),
                         capture_gate.mask_digest(new_page))
        for page in (old_page, new_page):
            self.assertEqual(len(capture_gate.DIGEST_RE.findall(page)), 1)

        # Issue #226: the disputed capture too. genVariants may be the ONLY
        # raw difference (the churned keys inside its maps), so the masked
        # pages must be byte-equal here as well -- the digest stays the one
        # masked difference, and any OTHER rendered change still votes true
        # (test_a_rendered_change_is_a_change, run over the disputed shape
        # below).
        disputed = disputed_capture(REAL_MODELS)
        with head_serving(churn(disputed), churn(REAL_AGENTS)):
            old_page, new_page = capture_gate.build_page_pair(
                (churn(disputed), churn(REAL_AGENTS)),
                (disputed, REAL_AGENTS))

        self.assertNotEqual(old_page, new_page)
        self.assertEqual(capture_gate.mask_digest(old_page),
                         capture_gate.mask_digest(new_page))
        for page in (old_page, new_page):
            self.assertEqual(len(capture_gate.DIGEST_RE.findall(page)), 1)

    def test_a_rendered_change_on_a_disputed_capture_is_a_change(self):
        # The true-vote control on the disputed shape (issue #226): a real
        # rendered move -- one model's Intelligence Index, re-rendered
        # through build.metric_record exactly as the quiet control mutates
        # its field -- must still vote true when the capture carries
        # genVariants, so the dispute handling can never swallow news.
        disputed = disputed_capture(REAL_MODELS)
        with head_serving(rendered_field_changed(disputed), REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(disputed, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_the_mask_never_touches_hex_outside_the_provenance_prose(self):
        # A 64-hex string anywhere else -- a sha in a payload string, a
        # filename -- is data and must survive the mask; the digest matches
        # only after the literal `Capture <code>`.
        page = ('data-Sha256 <code>' + "ab" * 32 + '</code> ok '
                'Capture <code>' + "cd" * 32 + '</code> &mdash; sha256')
        masked = capture_gate.mask_digest(page)

        self.assertIn("ab" * 32, masked)
        self.assertIn("Capture <code>" + "0" * 64 + "</code>", masked)

    def test_no_capture_at_HEAD_fails_open_toward_publishing(self):
        # The first capture ever: HEAD holds no capture to compare against.
        # Fail open (true, exit 0) or the first run would skip forever.
        def first_capture_ever():
            raise capture_gate.HeadCaptureError("no capture at HEAD")

        with mock.patch.object(capture_gate, "read_head_captures",
                               side_effect=first_capture_ever):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_a_date_only_difference_cannot_vote(self):
        # The quiet-fetch tree state: identical captures, but the real
        # captured-at.txt holds today's fetch date while HEAD's holds the
        # day the data last moved. The gate never reads either stamp -- it
        # writes one synthetic date into both temp data dirs -- so the pages
        # it compares are stamped 2000-01-01 and the real dates cannot vote.
        # (The synthetic date is also NOT today's, so a gate that ever leaked
        # the real stamp in would fail this test on the page contents.)
        real_stamp = (build.ROOT / "data" / "captured-at.txt").read_text()
        self.assertNotEqual(real_stamp, capture_gate.SYNTHETIC_STAMP)

        with head_serving(REAL_MODELS, REAL_AGENTS):
            old_page, new_page = capture_gate.build_page_pair(
                (REAL_MODELS, REAL_AGENTS), (REAL_MODELS, REAL_AGENTS))

        for page in (old_page, new_page):
            self.assertIn("2000-01-01", page)
        self.assertEqual(capture_gate.mask_digest(old_page),
                         capture_gate.mask_digest(new_page))
        with head_serving(REAL_MODELS, REAL_AGENTS):
            code, out = run_gate()
        self.assertEqual((code, out), (0, "false\n"))

    def test_a_missing_fresh_capture_is_broken_not_unchanged(self):
        # No fresh capture to compare is a broken run, not a quiet one: the
        # gate refuses with a nonzero exit rather than answering either way.
        # ROOT moves to an empty temp data dir; the HEAD read is patched, so
        # nothing real is touched.
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "data").mkdir()
            with mock.patch.object(capture_gate, "ROOT", pathlib.Path(tmp)), \
                 head_serving(REAL_MODELS, REAL_AGENTS):
                code, out = run_gate()

        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")

    def test_a_build_failure_fails_red_not_changed(self):
        # A capture the builder refuses (corrupt JSON at HEAD here) must turn
        # the run red -- exit nonzero, no true/false on stdout -- because a
        # broken capture is a re-read-the-leaderboard signal, never a quiet
        # "nothing moved".
        with head_serving(b"{not json", REAL_AGENTS):
            code, out = run_gate()

        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")

    def test_the_cli_answers_exactly_one_word(self):
        # The workflow consumes stdout via $(...), which strips trailing
        # newlines, so the contract is the WORD, not the EOL: assert on the
        # stripped answer, which is platform-neutral where the raw bytes
        # carry \n on POSIX and \r\n on Windows text mode.
        proc = subprocess.run(
            [sys.executable, "scripts/capture_gate.py"],
            cwd=str(build.ROOT), capture_output=True, check=False)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(proc.stdout.strip(), (b"true", b"false"))


class ReconcileSpeedTests(unittest.TestCase):
    """The per-cell relative test: threshold sourced from the differ,
    pass-throughs exact, structure never reconciled."""

    def test_threshold_has_a_single_source(self):
        # The gate imports the differ's threshold -- a re-declared constant
        # here would let the two tools drift apart, which is the exact
        # disagreement this gate exists to end.
        self.assertIs(capture_gate.SPEED_TOL, diff_aa.SPEED_TOL)
        self.assertEqual(capture_gate.SPEED_TOL, 0.25)

    def test_non_numbers_and_a_zero_committed_value_pass_through(self):
        for value in (None, 0, 0.0, -3.5, True, False, "fast"):
            self.assertIs(
                capture_gate.within_tolerance(value, 100.0), value)
        # No committed value to compare against: nothing to reconcile, the
        # fresh value stands (and the structural or from-zero move commits).
        for head_value in (None, 0, 0.0, True, "fast"):
            self.assertIs(
                capture_gate.within_tolerance(50.0, head_value), 50.0)

    def test_sub_threshold_moves_carry_the_committed_value(self):
        self.assertEqual(
            capture_gate.within_tolerance(110.0, 100.0), 100.0)
        self.assertEqual(
            capture_gate.within_tolerance(90.0, 100.0), 100.0)

    def test_exactly_at_the_threshold_is_jitter_just_past_is_news(self):
        # |fresh/committed - 1| <= SPEED_TOL, from the formula: 100 * 1.25
        # is exactly at the threshold and reconciles; one hair past it is a
        # real move and stands.
        self.assertEqual(
            capture_gate.within_tolerance(
                100.0 * (1 + capture_gate.SPEED_TOL), 100.0), 100.0)
        self.assertEqual(
            capture_gate.within_tolerance(
                100.0 * (1 + capture_gate.SPEED_TOL) * 1.0001, 100.0),
            100.0 * (1 + capture_gate.SPEED_TOL) * 1.0001)

    def test_the_joint_walk_reaches_nested_values_and_scopes_keys(self):
        head = {"a": [{"medianOutputTokensPerSecond": 100.0}],
                "intelligenceIndexTimePerTask": 40.0,
                "b": {"cost": 1.2}}
        fresh = {"a": [{"medianOutputTokensPerSecond": 110.0}],
                 "intelligenceIndexTimePerTask": 41.0,
                 "b": {"agentWallTimeSec": 901.0, "cost": 1.2}}
        out = capture_gate.reconcile_tree(
            head, fresh, capture_gate.SPEED_KEYS_MODELS)

        # Sub-threshold cells carry HEAD's value, wherever they sit.
        self.assertEqual(out["a"][0]["medianOutputTokensPerSecond"], 100.0)
        self.assertEqual(out["intelligenceIndexTimePerTask"], 40.0)
        self.assertEqual(out["b"]["cost"], 1.2)
        # Key scoping is per capture: the models set does not touch the
        # coding capture's field, so the fresh value stands.
        self.assertEqual(out["b"]["agentWallTimeSec"], 901.0)

    def test_structure_is_never_reconciled(self):
        keys = capture_gate.SPEED_KEYS_MODELS
        # Fresh-only key or subtree: kept verbatim (commits).
        self.assertEqual(
            capture_gate.reconcile_tree({"a": 1}, {"a": 1, "b": 2}, keys),
            {"a": 1, "b": 2})
        # Fresh-only list tail: kept verbatim (commits).
        self.assertEqual(
            capture_gate.reconcile_tree([{"x": 1.0}],
                                        [{"x": 1.1}, {"x": 2.0}], {"x"}),
            [{"x": 1.0}, {"x": 2.0}])
        # A key present in HEAD but missing fresh is simply absent -- the
        # fresh tree is never given values it did not have.
        self.assertEqual(
            capture_gate.reconcile_tree({"medianOutputTokensPerSecond": 9.0},
                                        {}, keys),
            {})
        # Type-mismatched positions: fresh stands (commits).
        self.assertEqual(
            capture_gate.reconcile_tree({"a": {"b": 1}}, {"a": [1]}, keys),
            {"a": [1]})


class OscillationTests(unittest.TestCase):
    """The drift property the per-cell test buys: jitter around one value
    never compounds into a commit, but a sustained crawl does."""

    def test_jitter_around_a_value_stays_silent_across_gates(self):
        # Hour 1: 100 committed, 99 measured. Hour 2: 99 committed, 101
        # measured. Both are sub-threshold relative to their own committed
        # value -- no accumulation, no commit, either hour.
        for head_value, fresh_value in ((100.0, 99.0), (99.0, 101.0)):
            head = with_tps(REAL_MODELS, head_value)
            fresh = with_tps(REAL_MODELS, fresh_value)
            with head_serving(head, REAL_AGENTS), \
                 mock.patch.object(capture_gate, "read_fresh_captures",
                                   return_value=(fresh, REAL_AGENTS)):
                code, out = run_gate()

            self.assertEqual((code, out), (0, "false\n"),
                             f"{head_value} -> {fresh_value}")

    def test_a_sustained_crawl_crosses_the_threshold_and_commits(self):
        # The same jitter, one step further: 101 committed, 127 measured is
        # +25.7% relative to the last COMMITTED value. Each hourly step was
        # sub-threshold, and the drift accumulated into news anyway --
        # exactly what the per-cell comparison guarantees.
        head = with_tps(REAL_MODELS, 101.0)
        fresh = with_tps(REAL_MODELS, 101.0 * 1.27)
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(fresh, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))


# --- issue #146: a zero score is a legal AA publication ----------------------


def zero_score_capture(models: bytes) -> bytes:
    """The capture with one model turned into issue #146's crash shape: its
    gdpvalNormalized zeroed and its gdpval eval cost set strictly cheapest,
    so the model lands on the agentic frontier carrying a zero score. The
    mutation lives in memory only -- never a data/ write. Self-contained by
    this file's convention: no import from the build tests."""
    parsed = json.loads(models)
    floor = None
    target = None
    for m in parsed:
        outer = m.get("intelligenceIndexCostPerTask")
        evals = outer.get("evaluations") if isinstance(outer, dict) else None
        if not isinstance(evals, list):
            continue
        weighted = None
        for e in evals:
            if (isinstance(e, dict) and e.get("slug") == "gdpval-aa"
                    and isinstance(e.get("weightedCostPerTask"), (int, float))
                    and not isinstance(e.get("weightedCostPerTask"), bool)):
                weighted = e["weightedCostPerTask"]
                break
        if weighted is None or weighted <= 0:
            continue
        if floor is None or weighted < floor:
            floor = weighted
        if target is None and "(" not in (
                m.get("shortName") or m.get("name") or ""):
            target = m
    if target is None:
        raise AssertionError("no model with a gdpval eval in the capture")
    assert floor is not None
    target["gdpvalNormalized"] = 0
    for e in target["intelligenceIndexCostPerTask"]["evaluations"]:
        if e.get("slug") == "gdpval-aa":
            e["weightedCostPerTask"] = floor / 2
    return json.dumps(parsed, indent=1).encode("utf-8")


class ZeroScoreCaptureGateTests(unittest.TestCase):
    """Issue #146 through the rendered no-change gate. A capture carrying a
    legal zero score must BUILD -- the gate answers false on identical
    bytes, it does not crash -- and an unexpected build crash now carries
    its traceback on stderr, so the next occurrence is diagnosable from the
    log alone instead of a bare "float division by zero"."""

    def test_a_zero_score_capture_builds_and_answers_false(self):
        models = zero_score_capture(REAL_MODELS)
        with head_serving(models, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(models, REAL_AGENTS)):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "false\n"))

    def test_an_unexpected_build_crash_carries_its_traceback(self):
        # The 2026-10-03T01:09Z hour failed with a bare "float division by
        # zero" that named neither site nor field. An unexpected exception
        # now carries the traceback on stderr.
        err = io.StringIO()
        with head_serving(b"{not json", REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(b"{not json", REAL_AGENTS)), \
             contextlib.redirect_stderr(err):
            code = capture_gate.main()

        self.assertNotEqual(code, 0)
        self.assertIn("Traceback (most recent call last)", err.getvalue())
        self.assertIn("JSONDecodeError", err.getvalue())

    def test_a_named_build_refusal_stays_bare_of_traceback(self):
        # build.py's own refusals are SystemExit -- they already carry their
        # named reason, and no traceback is appended to them.
        err = io.StringIO()
        with head_serving(b"[]", b"[]"), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(b"[]", b"[]")), \
             contextlib.redirect_stderr(err):
            code = capture_gate.main()

        self.assertNotEqual(code, 0)
        self.assertIn("no rows carry", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


# --- issue #227: the window marker on the gate path --------------------------


def window_capture(models: bytes) -> bytes:
    """The capture in the production window shape (issue #217): every model
    that carried a decomposable cost breakdown now carries the bare scalar
    the merge leaves when it drops every breakdown as another generation's.
    The agentic axis empties; intelligence (the scalar IS the measured total,
    build.cost_per_task) and parameters survive -- the two-generation
    window's exact shape. Self-contained by this file's convention: no
    import from the build tests."""
    parsed = json.loads(models)
    for m in parsed:
        if isinstance(m.get("intelligenceIndexCostPerTask"), dict):
            m["intelligenceIndexCostPerTask"] = 0.75
    return json.dumps(parsed, indent=1).encode("utf-8")


def corner_capture(models: bytes) -> bytes:
    """window_capture with every parameter count deleted too: the designed
    three-generation corner -- the detail route fills nothing, so the
    parameters axis empties beside agentic. #223's refusal shape, and run
    37691148949's failure exactly."""
    parsed = json.loads(window_capture(models))
    for m in parsed:
        m.pop("parameters", None)
    return json.dumps(parsed, indent=1).encode("utf-8")


WINDOW_MARKER = ("every cost breakdown dropped as another generation's: "
                 "185 model(s), first apodex-1-1; 3 generation(s) observed "
                 "in-run\n").encode("utf-8")


class WindowMarkerStagingTests(unittest.TestCase):
    """Issue #227: the marker staged into the temp data dirs is what makes
    the #217 exemption and the #223 refusal wording reachable on the GATE
    path -- the gap that let #223's fix ship half-landed, its tests calling
    build.py directly and never the gate. Each side stages its OWN source's
    marker (HEAD's from git, the hour's from data/), because a committed
    window hour must rebuild its published note-page on the old side too."""

    def test_the_corner_refusal_names_the_window_through_the_gate(self):
        # Run 37691148949's failure, pinned at the gate: HEAD healthy, the
        # fresh capture in the three-generation corner, the hour's marker
        # recorded -- the refusal stays nonzero but names the window, and
        # never blames a shape change.
        err = io.StringIO()
        with head_serving(REAL_MODELS, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=None), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(corner_capture(REAL_MODELS),
                                             REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=WINDOW_MARKER), \
             contextlib.redirect_stderr(err):
            code = capture_gate.main()

        self.assertEqual(code, 1)
        self.assertIn("3 generation(s) observed in-run", err.getvalue())
        self.assertNotIn("changed shape", err.getvalue())

    def test_no_marker_staged_the_shape_change_wording_stands(self):
        # The wording split itself: the same corner capture with NO marker
        # recorded is a shape change to build.py, and the gate relays that
        # wording verbatim. The marker's presence is the whole difference.
        err = io.StringIO()
        with head_serving(REAL_MODELS, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=None), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(corner_capture(REAL_MODELS),
                                             REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=None), \
             contextlib.redirect_stderr(err):
            code = capture_gate.main()

        self.assertEqual(code, 1)
        self.assertIn("changed shape", err.getvalue())

    def test_a_two_generation_window_publishes_through_the_gate(self):
        # The #217 exemption, killed on the gate path by the same staging
        # drop: marker staged, fresh in the two-generation shape -- agentic
        # empty, everything else alive -- and the gate answers true (the
        # window hour's note-page differs from HEAD's healthy page).
        with head_serving(REAL_MODELS, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=None), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(window_capture(REAL_MODELS),
                                             REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=WINDOW_MARKER):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_the_window_note_rides_the_gate_built_pages(self):
        # The exemption's page half: the note renders on the fresh side's
        # page and on no other -- through the gate's own build, not a
        # build.py call.
        with head_serving(REAL_MODELS, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=None), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=WINDOW_MARKER):
            old_page, new_page = capture_gate.build_page_pair(
                (REAL_MODELS, REAL_AGENTS),
                (window_capture(REAL_MODELS), REAL_AGENTS))

        self.assertNotIn("Empty during a two-generation window", old_page)
        self.assertIn("Empty during a two-generation window", new_page)

    def test_a_committed_window_hour_rebuilds_from_heads_marker(self):
        # A window hour's commit carries the capture AND its marker, so the
        # NEXT hour's old side rebuilds the published note-page instead of
        # refusing -- and the hour answers on the data's own movement (here:
        # a rendered move past tolerance, so true).
        head = window_capture(REAL_MODELS)
        fresh = rendered_field_changed(head)
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=WINDOW_MARKER), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(fresh, REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=WINDOW_MARKER):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_an_unchanged_window_hour_stays_silent(self):
        # The same state with no movement: two window captures, both sides
        # carrying their own marker, build equal note-pages and the gate
        # answers false -- a quiet window hour commits nothing.
        head = window_capture(REAL_MODELS)
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=WINDOW_MARKER), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(head, REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=WINDOW_MARKER):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "false\n"))

    def test_the_first_healthy_hour_after_a_window_heals(self):
        # Window ended: fetch cleared the marker, HEAD still tracks it, the
        # fresh capture is healthy. Old note-page vs new healthy page
        # differs, so the hour commits -- and its payload leaves the marker
        # out, which is what the workflow's `git rm` branch removes (pinned
        # in test_refresh_workflow.py).
        head = window_capture(REAL_MODELS)
        with head_serving(head, REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=WINDOW_MARKER), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(REAL_MODELS, REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=None):
            code, out = run_gate()

        self.assertEqual((code, out), (0, "true\n"))

    def test_a_window_capture_at_HEAD_without_its_marker_refuses(self):
        # The workflow half of the fix, pinned from the gate side: if
        # refresh.yml ever stops committing the marker, HEAD holds a window
        # capture whose note-page the old side cannot rebuild -- this exact
        # red is the symptom to expect, not a gate bug to chase.
        err = io.StringIO()
        with head_serving(window_capture(REAL_MODELS), REAL_AGENTS), \
             mock.patch.object(capture_gate, "read_head_window_marker",
                               return_value=None), \
             mock.patch.object(capture_gate, "read_fresh_captures",
                               return_value=(REAL_MODELS, REAL_AGENTS)), \
             mock.patch.object(capture_gate, "read_fresh_window_marker",
                               return_value=None), \
             contextlib.redirect_stderr(err):
            code = capture_gate.main()

        self.assertNotEqual(code, 0)
        self.assertIn("changed shape", err.getvalue())

    def test_the_fresh_marker_reader_converts_only_absence(self):
        # The None conversion against the real substrate, not a mock: a
        # marker missing from the live data dir reads as None -- a
        # regression propagating the FileNotFoundError would turn every
        # no-marker hour red through main()'s broad catch with the wrong
        # "capture broke the build" attribution.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "data").mkdir()
            with mock.patch.object(capture_gate, "ROOT", root):
                self.assertIsNone(capture_gate.read_fresh_window_marker())
            (root / "data" / capture_gate.WINDOW_MARKER_NAME).write_text("w\n")
            with mock.patch.object(capture_gate, "ROOT", root):
                self.assertEqual(
                    capture_gate.read_fresh_window_marker(), b"w\n")

    def test_the_head_marker_reader_converts_git_failure_to_none(self):
        # Same pin for the HEAD side: ROOT pointed at a non-repo makes the
        # real `git show` fail, and the failure reads as absent -- the
        # normal hour's answer -- never as a build break.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(capture_gate, "ROOT", pathlib.Path(tmp)):
                self.assertIsNone(capture_gate.read_head_window_marker())
