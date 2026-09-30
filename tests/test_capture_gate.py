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
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

# The real captures work as fixtures and are fast (a full build measures
# ~0.1 s); the suite already builds from them twice. The FRESH side of the
# gate reads data/ directly, so tests stay hermetic by monkeypatching the
# factored HEAD read only -- nothing here writes to the working tree.
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

    def test_raw_only_churn_is_not_a_change(self):
        # The gate this script replaces compared raw bytes and voted true on
        # exactly this fixture -- 23 of 30 refresh commits. Reordering keys
        # changes nothing the page parses, renders or (after masking) prints.
        with head_serving(churn(REAL_MODELS), churn(REAL_AGENTS)):
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
        # The workflow consumes stdout verbatim into a step output, so the
        # process entry point must answer `true`/`false` and nothing else,
        # with exit 0 either way. Run for real against this checkout: on a
        # clean tree the answer is false, on a moved-capture tree true --
        # the gate step has already decided by the time the suite runs.
        proc = subprocess.run(
            [sys.executable, "scripts/capture_gate.py"],
            cwd=str(build.ROOT), capture_output=True, check=False)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(proc.stdout, (b"true\n", b"false\n"))
