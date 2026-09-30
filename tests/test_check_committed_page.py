"""Pins on scripts/ci/check_committed_page.py -- the committed-page gate.

The check runs in CI against out/frontier-models.html as committed, and
refuses a page that carries no exactly-one well-shaped source-commit stamp
or differs from a stamp-less rebuild of the same tree once build provenance
is masked out (issue #105). These pins are on the DECISION, not the
mechanism: every failure mode yields its own distinct violation, a correct
page yields none, the mask removes exactly the provenance spans, and the
stamp shape stays coupled to what build.py actually renders.

Nothing here reads the working out/frontier-models.html:
tests/test_browser.py rebuilds that file stamp-less during the suite, and
pytest collects files alphabetically, so the browser file runs first and the
working copy is stamp-less by the time this file runs. The committed side is
read with `git show HEAD:...`, the rebuilt side from the tree's own data/
into a temp path.
"""
import contextlib
import io
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent.parent
for entry in ("scripts/ci", "scripts"):
    entry_path = HERE / entry
    if str(entry_path) not in sys.path:
        sys.path.insert(0, str(entry_path))

import check_committed_page  # noqa: E402  # pylint: disable=wrong-import-position
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

COMMIT = "e5e10f1c0ffee4215deadbeefcafe0123456789a"

# build.py splices the stamp directly after this prose, at the end of the
# provenance line; the fixture stamps below land in the same place, so a
# fixture and a real stamped page are byte-identical modulo the sha.
PROVENANCE_END = "concatenated in that order."


def stamp(page: str, commit: str = COMMIT) -> str:
    """The stamp-less page with one well-shaped stamp, where build.py puts it."""
    return page.replace(
        PROVENANCE_END,
        PROVENANCE_END + f" Source commit <code>{commit}</code>.", 1)


def committed_at_head() -> str:
    """out/frontier-models.html exactly as HEAD committed it."""
    proc = subprocess.run(
        ["git", "show", "HEAD:out/frontier-models.html"],
        cwd=str(build.ROOT), capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8")


class CheckCommittedPageTests(unittest.TestCase):
    def setUp(self):
        # Whatever a test does to build's module globals or the environment,
        # the check must hand them back exactly as it found them: the suite
        # runs other tests against the real data/ and the real out/.
        self._saved = (build.RAW, build.AGENTS_RAW, build.OUT)
        # One stamp-less rebuild serves the whole class: the rebuild is
        # deterministic over a fixed data/.
        self.rebuilt = check_committed_page.rebuild_page()

    def tearDown(self):
        self.assertEqual((build.RAW, build.AGENTS_RAW, build.OUT), self._saved)

    def test_the_committed_page_carries_its_stamp_and_matches_a_rebuild(self):
        # The standing repo invariant the CI `page` job enforces, pinned
        # locally: HEAD's committed page is exactly what its own tree
        # rebuilds to, once provenance is masked.
        self.assertEqual(
            check_committed_page.verify(committed_at_head(), self.rebuilt),
            [])

    def test_a_green_pair_yields_no_violation(self):
        self.assertEqual(
            check_committed_page.verify(stamp(self.rebuilt), self.rebuilt),
            [])

    def test_an_empty_page_yields_the_absent_stamp_violation(self):
        violations = check_committed_page.verify("", self.rebuilt)

        self.assertEqual(len(violations), 1)
        self.assertIn("carries no source-commit stamp", violations[0])

    def test_a_stampless_page_yields_the_absent_stamp_violation(self):
        violations = check_committed_page.verify(self.rebuilt, self.rebuilt)

        self.assertEqual(len(violations), 1)
        self.assertIn("carries no source-commit stamp", violations[0])

    def test_a_two_stamp_page_yields_the_multiple_stamp_violation(self):
        twice = stamp(stamp(self.rebuilt), commit="0" * 40)
        violations = check_committed_page.verify(twice, self.rebuilt)

        self.assertEqual(len(violations), 1)
        self.assertIn("carries 2 source-commit stamps", violations[0])

    def test_a_malformed_stamp_yields_the_malformed_stamp_violation(self):
        # Every shape the marker matches but STAMP_RE refuses: a non-hex or
        # too-short value, and the sentence without its closing period.
        malformed = [
            self.rebuilt.replace(
                PROVENANCE_END,
                PROVENANCE_END + " Source commit <code>not-a-sha</code>.", 1),
            self.rebuilt.replace(
                PROVENANCE_END,
                PROVENANCE_END + " Source commit <code>abc12</code>.", 1),
            self.rebuilt.replace(
                PROVENANCE_END,
                PROVENANCE_END + f" Source commit <code>{COMMIT}</code>", 1),
        ]
        for page in malformed:
            violations = check_committed_page.verify(page, self.rebuilt)

            self.assertEqual(len(violations), 1, violations)
            self.assertIn("malformed source-commit stamp", violations[0])

    def test_one_rendered_byte_changed_yields_the_mismatch_violation(self):
        changed = stamp(self.rebuilt).replace(
            "whole files concatenated", "whole file concatenated", 1)
        violations = check_committed_page.verify(changed, self.rebuilt)

        self.assertEqual(len(violations), 1)
        self.assertIn("differs from a stamp-less rebuild", violations[0])
        # the finding names both masked lengths and locates the difference
        self.assertIn("first difference at index ", violations[0])
        self.assertIn("whole file concatenated", violations[0])

    def test_the_stamp_shape_is_pinned_to_what_build_py_renders(self):
        # A build.py change that moves the stamp's prose or its SHA shape
        # must fail here instead of silently blinding the check: the check's
        # pattern is compiled from the same literals build.py renders.
        source = (build.ROOT / "build.py").read_text(encoding="utf-8")
        self.assertIn(" Source commit <code>", source)
        self.assertIn("[0-9a-f]{7,40}", source)

        # ...and the rendered page really does match the pattern: one build
        # with the env set, one real stamp found, value verbatim. The temp
        # dir lives under build.ROOT because build.main() prints
        # OUT.relative_to(ROOT) and would raise on a page outside it.
        with tempfile.TemporaryDirectory(prefix=".stamp-pin-",
                                         dir=build.ROOT) as tmp:
            page_path = pathlib.Path(tmp) / "frontier-models.html"
            with mock.patch.dict(os.environ,
                                 {check_committed_page.STAMP_ENV: COMMIT}):
                saved = (build.RAW, build.AGENTS_RAW, build.OUT)
                try:
                    build.OUT = page_path
                    with contextlib.redirect_stdout(io.StringIO()):
                        build.main()
                finally:
                    build.RAW, build.AGENTS_RAW, build.OUT = saved
            page = page_path.read_text(encoding="utf-8")

        stamps = check_committed_page.STAMP_RE.findall(page)
        self.assertEqual(stamps, [f" Source commit <code>{COMMIT}</code>."])

    def test_the_mask_is_idempotent_and_removes_exactly_the_spans(self):
        committed = stamp(self.rebuilt)

        once = check_committed_page.mask(committed)
        self.assertEqual(check_committed_page.mask(once), once)
        # The stamp is the only thing that distinguishes the two pages, so
        # with provenance masked on both sides they land byte-equal -- while
        # the raw committed page differs from its mask by exactly the stamp
        # (the digest is shared, so only the stamp can move there).
        self.assertEqual(once, check_committed_page.mask(self.rebuilt))
        self.assertNotEqual(once, committed)

    def test_the_mask_never_touches_data_outside_the_provenance_spans(self):
        page = ('sha256 <code>' + "ab" * 40 + '</code> ok '
                'Source commit <code>deadbeef</code> in a payload string '
                + stamp(self.rebuilt))
        masked = check_committed_page.mask(page)

        # a sha-shaped string elsewhere in the page is data and survives
        self.assertIn("ab" * 40, masked)
        self.assertIn("Source commit <code>deadbeef</code> in a payload "
                      "string", masked)
        self.assertEqual(len(check_committed_page.STAMP_RE.findall(masked)),
                         0)

    def test_main_accepts_a_stamped_page_and_prints_the_stamp(self):
        # main() takes the page path, so this never reads the working
        # out/frontier-models.html, which test_browser leaves stamp-less.
        with tempfile.TemporaryDirectory(prefix=".committed-page-",
                                         dir=build.ROOT) as tmp:
            page = pathlib.Path(tmp) / "frontier-models.html"
            page.write_text(stamp(self.rebuilt), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = check_committed_page.main(page)

        self.assertEqual(code, 0)
        self.assertIn(COMMIT, out.getvalue())
        self.assertIn("-- ok", out.getvalue())

    def test_main_refuses_a_missing_page_with_its_own_line(self):
        with tempfile.TemporaryDirectory(prefix=".committed-page-",
                                         dir=build.ROOT) as tmp:
            missing = pathlib.Path(tmp) / "absent.html"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = check_committed_page.main(missing)

        self.assertNotEqual(code, 0)
        self.assertIn("missing or unreadable", err.getvalue())

    def test_main_refuses_a_failing_rebuild_red_not_silent(self):
        # A rebuild that raises must turn the run red with the exception on
        # stderr, never a quiet pass: the page must be rebuildable from what
        # is committed, or the commit is broken.
        with tempfile.TemporaryDirectory(prefix=".committed-page-",
                                         dir=build.ROOT) as tmp:
            page = pathlib.Path(tmp) / "frontier-models.html"
            page.write_text(stamp(self.rebuilt), encoding="utf-8")

            def broken():
                raise ValueError("the tree does not build")

            with mock.patch.object(check_committed_page, "rebuild_page",
                                   side_effect=broken):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = check_committed_page.main(page)

        self.assertNotEqual(code, 0)
        self.assertIn("red, never a silent pass", err.getvalue())
        self.assertIn("the tree does not build", err.getvalue())


class HeadStateTests(unittest.TestCase):
    """Pins on the committed state itself, independent of the rebuild."""

    def test_head_page_matches_the_stamp_grammar_the_check_enforces(self):
        # The committed stamp, read straight from HEAD, is exactly one
        # well-shaped match -- the check's count grammar cannot green a page
        # whose stamp drifted out of shape.
        committed = committed_at_head()
        stamps = check_committed_page.STAMP_RE.findall(committed)

        self.assertEqual(len(stamps), 1, stamps)
        self.assertTrue(re.fullmatch(r"[0-9a-fA-F]{7,40}",
                                     stamps[0][len(" Source commit <code>"):
                                               -len("</code>.")]))
