"""Exercise ranking history and the standalone page against real git commits."""
from __future__ import annotations

from html.parser import HTMLParser
import errno
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from playwright.sync_api import (
    Error as PlaywrightError,
    sync_playwright)

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_rankings  # noqa: E402  # pylint: disable=wrong-import-position

HF = "data/hf-trending.json"
OR = "data/openrouter-trending.json"


def _retry_readonly_removal(function, path, error):
    """Retry one read-only removal; propagate unrelated and retry failures."""
    if not isinstance(error, PermissionError) or function not in (os.unlink, os.remove, os.rmdir):
        raise error
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & stat.S_IWRITE:
        raise error
    os.chmod(path, mode | stat.S_IWRITE)
    function(path)


def _cleanup_rankings_fixture(path):
    """Use the supported error callback on every matrix Python version."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry_readonly_removal)
    else:
        def onerror(function, failed_path, exc_info):
            _retry_readonly_removal(function, failed_path, exc_info[1])

        # Python 3.11 requires onerror; newer runtimes use onexc above.
        shutil.rmtree(path, onerror=onerror)  # pylint: disable=deprecated-argument


class Page(HTMLParser):
    """Read the generated chart marks and accessible tables as a consumer."""

    def __init__(self, document):
        super().__init__()
        self.points = []
        self.tables = []
        self.headers = []
        self.header_text = []
        self.in_header = False
        self.text = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "circle":
            self.points.append(attributes)
        if tag == "table":
            self.tables.append(attributes)
        if tag == "th":
            self.headers.append(attributes)
            self.in_header = True

    def handle_endtag(self, tag):
        if tag == "th":
            self.in_header = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_header:
            self.header_text.append(data)


class ReadonlyCleanupTests(unittest.TestCase):
    def test_fixture_teardown_removes_readonly_git_objects(self):
        real_unlink = os.unlink

        def windows_unlink(path, *args, **kwargs):
            mode = os.stat(path, dir_fd=kwargs.get('dir_fd')).st_mode
            if not mode & stat.S_IWRITE:
                raise PermissionError(errno.EACCES, 'read-only file', path)
            return real_unlink(path, *args, **kwargs)

        versions = (((3, 11), (3, 12), (3, 13))
                    if sys.version_info >= (3, 12) else ((3, 11),))
        for version in versions:
            with self.subTest(version=version):
                case = RankingsTests('test_single_snapshot_renders_without_padding')
                result = unittest.TestResult()
                with mock.patch.object(os, 'unlink', windows_unlink), \
                        mock.patch.object(sys, 'version_info', version):
                    case.run(result)
                self.assertEqual(result.errors, [])
                self.assertEqual(result.failures, [])
                self.assertFalse(pathlib.Path(case.directory).exists())

    def test_retry_preserves_mode_and_removes_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'readonly'
            target.write_text('fixture', encoding='utf-8')
            target.chmod(stat.S_IREAD)
            original_mode = stat.S_IMODE(target.stat().st_mode)
            real_unlink = os.unlink
            retries = []

            def remove(path):
                retries.append(stat.S_IMODE(os.stat(path).st_mode))
                real_unlink(path)

            with mock.patch.object(os, 'unlink', remove):
                _retry_readonly_removal(os.unlink, target, PermissionError(errno.EACCES, 'readonly'))
            self.assertFalse(target.exists())
            self.assertEqual(len(retries), 1)
            self.assertTrue(retries[0] & stat.S_IWRITE)
            self.assertEqual(retries[0] & original_mode, original_mode)

    def test_nonpermission_errors_propagate(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'readonly'
            target.write_text('fixture', encoding='utf-8')
            target.chmod(stat.S_IREAD)
            error = OSError(errno.EIO, 'unrelated failure')
            try:
                with self.assertRaises(OSError) as caught:
                    _retry_readonly_removal(os.unlink, target, error)
                self.assertIs(caught.exception, error)
                self.assertFalse(target.stat().st_mode & stat.S_IWRITE)
            finally:
                if target.exists():
                    target.chmod(target.stat().st_mode | stat.S_IWRITE)

    def test_writable_permission_errors_propagate(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'writable'
            target.write_text('fixture', encoding='utf-8')
            error = PermissionError(errno.EACCES, 'not a readonly failure')
            with self.assertRaises(PermissionError) as caught:
                _retry_readonly_removal(os.unlink, target, error)
            self.assertIs(caught.exception, error)
            self.assertTrue(target.exists())

    def test_nonremoval_permission_errors_propagate(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'readonly'
            target.write_text('fixture', encoding='utf-8')
            target.chmod(stat.S_IREAD)
            error = PermissionError(errno.EACCES, 'stat failure')
            try:
                with self.assertRaises(PermissionError) as caught:
                    _retry_readonly_removal(os.stat, target, error)
                self.assertIs(caught.exception, error)
                self.assertFalse(target.stat().st_mode & stat.S_IWRITE)
            finally:
                if target.exists():
                    target.chmod(target.stat().st_mode | stat.S_IWRITE)

    def test_a_failed_retry_propagates_without_another_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'readonly'
            target.write_text('fixture', encoding='utf-8')
            target.chmod(stat.S_IREAD)
            error = PermissionError(errno.EACCES, 'still blocked')
            retries = []

            def remove(path):
                retries.append(path)
                raise error

            try:
                with mock.patch.object(os, 'unlink', remove):
                    with self.assertRaises(PermissionError) as caught:
                        _retry_readonly_removal(os.unlink, target,
                                                PermissionError(errno.EACCES, 'readonly'))
                self.assertIs(caught.exception, error)
                self.assertEqual(retries, [target])
                self.assertTrue(target.exists())
            finally:
                if target.exists():
                    target.chmod(target.stat().st_mode | stat.S_IWRITE)


class RankingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(_cleanup_rankings_fixture, self.directory)
        self.repo = pathlib.Path(self.directory) / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "fixture")
        self.git("config", "user.email", "fixture@example.com")
        self.git("config", "commit.gpgsign", "false")
        self.first = self.commit(HF, ["org/a", "org/b"], "id")
        self.or_first = self.commit(OR, ["lab/x", "lab/y"], "slug")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True,
            capture_output=True, text=True, encoding="utf-8", timeout=60).stdout

    def commit(self, path, models, key):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"source": "fixture", "models": [
            {key: model} for model in models]}), encoding="utf-8")
        self.git("add", path)
        self.git("commit", "-qm", "Update list")
        return self.git("rev-parse", "HEAD").strip()

    def _document(self, *arguments):
        output = pathlib.Path(self.directory) / "nested" / "rankings.html"
        build_rankings.main(["--repo", str(self.repo), "--out", str(output),
                             *arguments])
        return output.read_text(encoding="utf-8")

    def test_history_limits_each_list_to_its_own_changing_commits(self):
        second = self.commit(HF, ["org/b", "org/a"], "id")
        self.commit(OR, ["lab/y", "lab/x"], "slug")
        (self.repo / "README.md").write_text("unrelated", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "Documentation")
        third = self.commit(HF, ["org/c", "org/b"], "id")
        history = build_rankings.read_history(self.repo, HF, "id", 2)
        self.assertEqual([snapshot.commit for snapshot in history], [second, third])
        self.assertEqual(len(build_rankings.read_history(self.repo, OR, "slug", 10)), 2)

    def test_ranks_come_from_each_committed_snapshot_not_the_working_tree(self):
        second = self.commit(HF, ["org/b", "org/c", "org/a"], "id")
        (self.repo / HF).write_text("not committed JSON", encoding="utf-8")
        history = build_rankings.read_history(self.repo, HF, "id", 10)
        self.assertEqual([snapshot.ranks for snapshot in history], [
            {"org/a": 1, "org/b": 2}, {"org/b": 1, "org/c": 2, "org/a": 3}])
        self.assertEqual(history[-1].commit, second)

    def test_single_snapshot_renders_without_padding(self):
        page = Page(self._document())
        self.assertEqual(len(page.tables), 2)
        self.assertEqual(len(page.points), 4)
        self.assertEqual({point["data-commit"] for point in page.points},
                         {self.first, self.or_first})
        self.assertTrue(all(float(point["r"]) >= 4 for point in page.points))

    def test_a_new_model_enters_at_its_first_carried_snapshot(self):
        entered = self.commit(HF, ["org/new", "org/a"], "id")
        newest = self.commit(HF, ["org/a", "org/new"], "id")
        points = [point for point in Page(self._document()).points
                  if point["data-model"] == "org/new"]
        self.assertEqual([point["data-commit"] for point in points], [entered, newest])
        self.assertEqual([point["data-rank"] for point in points], ["1", "2"])

    def test_absence_breaks_a_line_instead_of_drawing_through_it(self):
        self.commit(HF, ["org/b"], "id")
        self.commit(HF, ["org/a", "org/b"], "id")
        document = self._document()
        paths = re.findall(r'<path\b[^>]*data-model="org/a"[^>]*d="([^"]+)"', document)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].count("M"), 2)
        self.assertNotIn("L", paths[0])

    def test_same_history_builds_byte_identical_html(self):
        self.commit(HF, ["org/b", "org/a"], "id")
        self.assertEqual(self._document().encode("utf-8"),
                         self._document().encode("utf-8"))

    def test_page_has_no_external_subresources(self):
        document = self._document()
        self.assertNotRegex(document, r'(?i)(?:src|href)\s*=\s*[\"\x27]?https?://')
        self.assertNotRegex(document, r'(?i)(?:@import\s+|url\(\s*)[\"\x27]?https?://')

    def test_every_point_has_its_full_commit_timestamp_and_visible_tick(self):
        self.commit(HF, ["org/b", "org/a"], "id")
        document = self._document()
        page = Page(document)
        for point in page.points:
            timestamp = self.git("show", "-s", "--format=%cI", point["data-commit"]).strip()
            self.assertEqual(point["data-timestamp"], timestamp)
            self.assertIn(timestamp, " ".join(page.text))
        self.assertEqual(document.count('class="timestamp-tick"'), 3)

    def test_each_table_exposes_model_rank_history_and_timestamps(self):
        self.commit(HF, ["org/b", "org/a"], "id")
        page = Page(self._document())
        text = " ".join(page.text)
        self.assertEqual(len(page.tables), 2)
        self.assertEqual(len(page.headers), 8)
        for heading in ("Model", "Rank history", "First-seen", "Latest timestamp"):
            self.assertEqual(page.header_text.count(heading), 2)
        self.assertIn("org/a", text)
        self.assertIn("lab/x", text)
        self.assertTrue(all(header.get("scope") == "col" for header in page.headers))

    def test_model_text_is_escaped_in_svg_table_and_tooltip_data(self):
        self.commit(HF, ['org/</script><script>alert("x")</script>'], "id")
        document = self._document()
        self.assertNotIn('<script>alert("x")</script>', document)
        self.assertIn('org/</script><script>alert("x")</script>',
                      " ".join(Page(document).text))

    def test_cli_defaults_create_the_expected_output_path(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_rankings.py")], cwd=self.repo,
            check=False, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo / "out/trending-rankings.html").is_file())

    def test_nonpositive_limit_is_rejected(self):
        for limit in (0, -1):
            with self.subTest(limit=limit):
                with self.assertRaises(SystemExit) as caught:
                    self._document("--limit", str(limit))
                self.assertEqual(caught.exception.code, 2)

    def test_limit_above_ten_is_rejected(self):
        with self.assertRaises(SystemExit) as caught:
            self._document("--limit", "11")
        self.assertEqual(caught.exception.code, 2)

    def test_history_rejects_limits_outside_one_to_ten(self):
        for limit in (0, -1, 11):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    build_rankings.read_history(self.repo, HF, "id", limit)

    def test_hidden_crosshair_has_an_explicit_display_rule(self):
        rule = re.search(r"\.crosshair\[hidden\]\s*\{[^}]*display:\s*none\s*;?\s*\}",
                         self._document())
        self.assertIsNotNone(rule, "a hidden SVG crosshair must have display: none")

    def test_browser_rings_stay_solid_and_crosshair_hides_after_escape(self):
        self.commit(HF, [f"org/model-{rank}" for rank in range(10)], "id")
        document = self._document()
        chromium = os.environ.get("CHROMIUM_PATH") or "/usr/bin/chromium"
        executable = chromium if pathlib.Path(chromium).exists() else None
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True, executable_path=executable)
            except PlaywrightError as error:
                if "Executable doesn't exist at " in str(error):
                    self.skipTest("Chromium executable is not installed")
                raise
            try:
                page = browser.new_page(color_scheme="light")
                page.set_content(document)
                crosshair = page.locator("#hugging-face .crosshair")
                with self.subTest(state="initial crosshair"):
                    self.assertEqual(crosshair.evaluate(
                        "node => getComputedStyle(node).display"), "none")
                point = page.locator("#hugging-face .point[data-dashed='true']").first
                styles = point.evaluate("""node => {
                    const chart = node.closest('.chart');
                    const path = Array.from(chart.querySelectorAll('.series'))
                      .find(series => series.dataset.model === node.dataset.model);
                    const ring = getComputedStyle(node);
                    return {dash: ring.strokeDasharray, width: ring.strokeWidth,
                      stroke: ring.stroke, surface: getComputedStyle(chart).backgroundColor,
                      pathDash: getComputedStyle(path).strokeDasharray};
                }""")
                with self.subTest(state="marker ring"):
                    self.assertEqual(styles["dash"], "none")
                    self.assertEqual(styles["width"], "2px")
                    self.assertEqual(styles["stroke"], styles["surface"])
                with self.subTest(state="series path"):
                    self.assertNotEqual(styles["pathDash"], "none")
                point.focus()
                with self.subTest(state="focused crosshair"):
                    self.assertNotEqual(crosshair.evaluate(
                        "node => getComputedStyle(node).display"), "none")
                page.keyboard.press("Escape")
                with self.subTest(state="dismissed crosshair"):
                    self.assertEqual(crosshair.evaluate(
                        "node => getComputedStyle(node).display"), "none")
            finally:
                browser.close()

    def test_many_departed_models_keep_endpoint_labels_within_the_chart(self):
        for index in range(10):
            self.commit(HF, [f"org/model-{index}-{rank}" for rank in range(10)], "id")
        document = self._document()
        match = re.search(r"<svg\b.*?</svg>", document, re.S)
        assert match is not None
        svg = ET.fromstring(match.group())
        labels = [element for element in svg.iter()
                  if element.attrib.get("class") == "end-label"]
        self.assertEqual(len(labels), 100)
        coordinates = sorted(float(label.attrib["y"]) for label in labels)
        self.assertGreaterEqual(coordinates[0], 16)
        self.assertLessEqual(coordinates[-1], float(svg.attrib["height"]) - 16)
        self.assertTrue(all(right - left >= 22
                            for left, right in zip(coordinates, coordinates[1:])))
