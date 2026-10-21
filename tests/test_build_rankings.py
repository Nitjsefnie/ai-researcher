"""Exercise ranking history and the standalone page against real git commits."""
from __future__ import annotations

from datetime import datetime, timezone
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
    """Read the generated chart marks, table tags and text as a consumer."""

    def __init__(self, document):
        super().__init__()
        self.points = []
        self.tables = []
        self.text = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "circle":
            self.points.append(attributes)
        if tag == "table":
            self.tables.append(attributes)

    def handle_data(self, data):
        self.text.append(data)


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


class RankingsFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(_cleanup_rankings_fixture, self.directory)
        self.repo = pathlib.Path(self.directory) / "repo"
        self.repo.mkdir()
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.name", "fixture")
        self._git("config", "user.email", "fixture@example.com")
        self._git("config", "commit.gpgsign", "false")
        self.first = self.commit(HF, ["org/a", "org/b"], "id")
        self.or_first = self.commit(OR, ["lab/x", "lab/y"], "slug")

    def _git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True,
            capture_output=True, text=True, encoding="utf-8", timeout=60).stdout

    def commit(self, path, models, key):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"source": "fixture", "models": [
            {key: model} for model in models]}), encoding="utf-8")
        self._git("add", path)
        self._git("commit", "-qm", "Update list")
        return self._git("rev-parse", "HEAD").strip()

    def _document(self, *arguments):
        output = pathlib.Path(self.directory) / "nested" / "rankings.html"
        build_rankings.main(["--repo", str(self.repo), "--out", str(output),
                             *arguments])
        return output.read_text(encoding="utf-8")


class RankingsTests(RankingsFixture):
    def test_history_limits_each_list_to_its_own_changing_commits(self):
        second = self.commit(HF, ["org/b", "org/a"], "id")
        self.commit(OR, ["lab/y", "lab/x"], "slug")
        (self.repo / "README.md").write_text("unrelated", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-qm", "Documentation")
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
        self.assertEqual(len(page.tables), 0)
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

        # An explicit commit must reproduce those bytes without moving HEAD.
        before = self._git("rev-parse", "HEAD").strip()
        original = self._document()
        self.commit(HF, ["org/b", "org/new"], "id")
        self.commit(OR, ["lab/y", "lab/new"], "slug")
        current = self._git("rev-parse", "HEAD").strip()
        self.assertEqual(self._document("--commit", before), original)
        self.assertNotEqual(self._document(), original)
        self.assertEqual(self._git("rev-parse", "HEAD").strip(), current)

    def test_page_has_no_external_subresources(self):
        document = self._document()
        self.assertNotRegex(document, r'(?i)(?:src|href)\s*=\s*[\"\x27]?https?://')
        self.assertNotRegex(document, r'(?i)(?:@import\s+|url\(\s*)[\"\x27]?https?://')

    def test_every_point_has_its_utc_commit_timestamp_and_visible_tick(self):
        with mock.patch.dict(os.environ, {"TZ": "JST-9"}):
            latest = self.commit(HF, ["org/b", "org/a"], "id")
        raw = self._git("show", "-s", "--format=%cI", latest).strip()
        self.assertTrue(raw.endswith("+09:00"), raw)
        document = self._document()
        page = Page(document)
        for point in page.points:
            seconds = int(self._git("show", "-s", "--format=%ct", point["data-commit"]))
            timestamp = datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.assertEqual(point["data-timestamp"], timestamp)
            self.assertIn(timestamp, " ".join(page.text))
        self.assertNotIn(raw, document)
        self.assertEqual(document.count('class="timestamp-tick"'), 3)

    def test_page_has_no_table_view(self):
        self.commit(HF, ["org/b", "org/a"], "id")
        document = self._document()
        page = Page(document)
        text = " ".join(page.text)
        self.assertEqual(len(page.tables), 0)
        self.assertNotIn("Table view", text)
        descriptions = re.findall(r'<desc[^>]*>(.*?)</desc>', document, re.S)
        self.assertEqual(len(descriptions), 2)
        for description in descriptions:
            self.assertNotRegex(description, r'(?i)\btable\b')
        self.assertEqual(document.count('<svg'), 2)
        self.assertEqual(document.count('<ul class="legend"'), 2)
        self.assertTrue(page.points)
        self.assertIn("org/a", text)
        self.assertIn("lab/x", text)
        for point in page.points:
            self.assertEqual(point["tabindex"], "0")
            self.assertEqual(point["aria-label"],
                             f'Rank {point["data-rank"]} · {point["data-model"]} · '
                             f'{point["data-timestamp"]}')

    def test_model_text_is_escaped_in_svg_and_tooltip_data(self):
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

    def test_charts_fit_their_containers_at_common_widths(self):
        for index in range(1, 10):
            hf_models = [f"org/hf-{(index + rank) % 11}" for rank in range(10)]
            latest_hf = self.commit(HF, hf_models, "id")
        for index in range(1, 5):
            router_models = [f"lab/or-{(index + rank) % 6}" for rank in range(10)]
            latest_or = self.commit(OR, router_models, "slug")

        document = self._document("--limit", "10")
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
                page = browser.new_page(viewport={"width": 390, "height": 900},
                                        color_scheme="dark")
                page.set_content(document)
                latest_commits = [latest_hf, latest_or]
                for width in (390, 768, 1280, 2560):
                    page.set_viewport_size({"width": width, "height": 900})
                    if width == 2560:
                        main_width = page.locator("main").evaluate(
                            "node => node.getBoundingClientRect().width")
                        self.assertGreater(
                            main_width, 2000,
                            f"main should use the wide viewport at {width}px; got {main_width}px")
                    page.locator(".chart-scroll").evaluate_all(
                        "containers => containers.forEach(container => container.scrollLeft = 0)")
                    charts = page.locator(".chart-scroll").evaluate_all("""(containers, commits) =>
                      containers.map((container, index) => {
                        const svg = container.querySelector('svg');
                        const bounds = svg.getBoundingClientRect();
                        const containerBounds = container.getBoundingClientRect();
                        const newestPoints = Array.from(svg.querySelectorAll('.point'))
                          .filter(point => point.dataset.commit === commits[index]);
                        const newestBounds = newestPoints.map(point =>
                          point.getBoundingClientRect());
                        return {
                          svgWidth: bounds.width,
                          containerWidth: containerBounds.width,
                          svgRight: bounds.right,
                          containerRight: containerBounds.right,
                          scrollWidth: container.scrollWidth,
                          clientWidth: container.clientWidth,
                          newestVisible: newestBounds.length > 0 && newestBounds.every(point =>
                            point.left >= containerBounds.left - 0.5 &&
                            point.right <= containerBounds.right + 0.5)
                        };
                      })""", latest_commits)
                    widths = [chart["svgWidth"] for chart in charts]
                    self.assertLessEqual(
                        max(widths) - min(widths), 0.5,
                        f"chart SVG widths differ at {width}px: {widths}")
                    for index, chart in enumerate(charts):
                        message = f"chart {index} at {width}px: {chart}"
                        self.assertLessEqual(
                            chart["svgWidth"], chart["containerWidth"] + 0.5,
                            f"SVG exceeds its container; {message}")
                        self.assertLessEqual(
                            chart["scrollWidth"], chart["clientWidth"] + 1,
                            f"chart scrolls horizontally; {message}")
                        self.assertLessEqual(
                            chart["svgRight"], chart["containerRight"] + 0.5,
                            f"SVG right edge is clipped; {message}")
                        self.assertTrue(
                            chart["newestVisible"],
                            f"newest commit points are clipped; {message}")

                latest_point = page.locator(
                    f"#hugging-face .point[data-commit='{latest_hf}']").first
                expected_timestamp = latest_point.get_attribute("data-timestamp")
                latest_point.hover()
                self.assertEqual(page.locator(
                    "#hugging-face .point.selected").get_attribute("data-commit"), latest_hf)
                self.assertIn(expected_timestamp, page.locator(
                    "#hugging-face .tooltip").inner_text())

                page.locator("#theme").click()
                self.assertEqual(page.locator("html").get_attribute("data-theme"), "light")
                light_surface = page.locator("#hugging-face .chart").evaluate(
                    "node => getComputedStyle(node).backgroundColor")
                page.locator("#theme").click()
                self.assertEqual(page.locator("html").get_attribute("data-theme"), "dark")
                dark_surface = page.locator("#hugging-face .chart").evaluate(
                    "node => getComputedStyle(node).backgroundColor")
                self.assertNotEqual(light_surface, dark_surface)
                self.assertLessEqual(page.locator(".chart-scroll").evaluate_all("""containers => {
                  const widths = containers.map(container =>
                    container.querySelector('svg').getBoundingClientRect().width);
                  return Math.max(...widths) - Math.min(...widths);
                }"""), 0.5)
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
        viewbox_height = float(svg.attrib["viewBox"].split()[3])
        self.assertGreaterEqual(coordinates[0], 16)
        self.assertLessEqual(coordinates[-1], viewbox_height - 16)
        self.assertTrue(all(right - left >= 22
                            for left, right in zip(coordinates, coordinates[1:])))


class FreshRankingsTests(RankingsFixture):
    def test_quoted_snapshot_label_survives_render_parse_round_trip(self):
        label = 'run "quoted" & <snapshot>'
        snapshot = build_rankings.Snapshot(label, "2026-10-20T09:41:00Z", {"org/model": 1})
        document = build_rankings.section_html(
            "hugging-face", "Hugging Face", "Hugging Face", [snapshot])
        self.assertEqual([point["data-commit"] for point in Page(document).points], [label])

    def _fresh_file(self, models, key):
        target = pathlib.Path(self.directory) / f"fresh-{key}.json"
        target.write_text(json.dumps({"source": "fixture", "models": [
            {key: model} for model in models]}), encoding="utf-8")
        return str(target)

    def test_fresh_columns_render_the_label_and_each_lists_fetch_timestamp(self):
        hf = self._fresh_file(["org/new", "org/a"], "id")
        router = self._fresh_file(["lab/y", "lab/new"], "slug")
        document = self._document(
            "--fresh-hf", hf, "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
            "--fresh-or", router, "--fresh-or-timestamp", "2026-10-20T09:42:00Z",
            "--fresh-label", "run 123")
        sections = re.findall(r'<section\b.*?</section>', document, re.S)
        for section, timestamp, expected in (
                (sections[0], "2026-10-20T09:41:00Z", {"org/new": "1", "org/a": "2"}),
                (sections[1], "2026-10-20T09:42:00Z", {"lab/y": "1", "lab/new": "2"})):
            with self.subTest(timestamp=timestamp):
                points = [point for point in Page(section).points
                          if point["data-commit"] == "run 123"]
                self.assertEqual({point["data-model"]: point["data-rank"]
                                  for point in points}, expected)
                self.assertEqual({point["data-timestamp"] for point in points}, {timestamp})
                for point in points:
                    self.assertEqual(point["aria-label"],
                                     f'Rank {point["data-rank"]} · '
                                     f'{point["data-model"]} · {timestamp}')
                self.assertEqual(section.count('class="timestamp-tick"'), 2)
                self.assertIn(f"<title>{timestamp}</title>", section)
                self.assertIn(timestamp[11:19], section)
                self.assertIn("2 changing commits · ", section)
                self.assertIn(f" → {timestamp}</p>", section)

    def test_one_sided_fresh_keeps_the_other_lists_full_history(self):
        self.commit(HF, ["org/b", "org/a"], "id")
        self.commit(OR, ["lab/y", "lab/x"], "slug")
        original = re.findall(r'<section\b.*?</section>', self._document("--limit", "2"), re.S)
        hf = self._fresh_file(["org/new"], "id")
        document = self._document(
            "--limit", "2", "--fresh-hf", hf,
            "--fresh-hf-timestamp", "2026-10-20T09:41:00Z", "--fresh-label", "run 123")
        sections = re.findall(r'<section\b.*?</section>', document, re.S)
        self.assertEqual(sections[1], original[1])
        self.assertNotEqual(sections[0], original[0])
        self.assertNotIn(self.first, sections[0])
        self.assertIn('data-commit="run 123"', sections[0])

    def test_fresh_column_replaces_the_oldest_of_ten_history_columns(self):
        commits = [self.first]
        for index in range(9):
            commits.append(self.commit(HF, [f"org/model-{index}"], "id"))
        hf = self._fresh_file(["org/fresh"], "id")
        document = self._document(
            "--fresh-hf", hf, "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
            "--fresh-label", "run 123")
        section = re.findall(r'<section\b.*?</section>', document, re.S)[0]
        points = Page(section).points
        self.assertEqual(list(dict.fromkeys(point["data-commit"] for point in points)),
                         [*commits[1:], "run 123"])
        self.assertEqual(len({point["cx"] for point in points}), 10)
        self.assertEqual(section.count('class="timestamp-tick"'), 10)
        self.assertIn("10 changing commits · ", section)
        self.assertNotIn("org/a", section)

    def test_limit_one_with_fresh_input_keeps_only_the_fresh_column(self):
        for option, key, model, other in (
                ("hf", "id", "org/fresh", self.or_first),
                ("or", "slug", "lab/fresh", self.first)):
            with self.subTest(option=option):
                fresh = self._fresh_file([model], key)
                document = self._document(
                    "--limit", "1", f"--fresh-{option}", fresh,
                    f"--fresh-{option}-timestamp", "2026-10-20T09:41:00Z",
                    "--fresh-label", "run 123")
                self.assertEqual({point["data-commit"] for point in Page(document).points},
                                 {"run 123", other})
                self.assertEqual(document.count('class="timestamp-tick"'), 2)

    def test_fresh_arguments_require_a_file_timestamp_pair_and_label(self):
        hf = self._fresh_file(["org/fresh"], "id")
        router = self._fresh_file(["lab/fresh"], "slug")
        for arguments, message in (
                (["--fresh-hf", hf], "--fresh-label"),
                (["--fresh-or", router], "--fresh-label"),
                (["--fresh-hf", hf, "--fresh-label", "run 123"], "--fresh-hf-timestamp"),
                (["--fresh-or", router, "--fresh-label", "run 123"], "--fresh-or-timestamp"),
                (["--fresh-hf-timestamp", "2026-10-20T09:41:00Z"], "--fresh-hf"),
                (["--fresh-or-timestamp", "2026-10-20T09:42:00Z"], "--fresh-or"),
                (["--fresh-label", "run 123"], "--fresh-label"),
                (["--fresh-hf", hf, "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
                  "--fresh-label", "run 123", "--fresh-or", router], "--fresh-or-timestamp")):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/build_rankings.py"), *arguments],
                    cwd=self.repo, check=False, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertNotIn("unrecognized arguments", result.stderr)
                self.assertFalse((self.repo / "out/trending-rankings.html").exists())

    def test_fresh_inputs_build_byte_identical_html(self):
        hf = self._fresh_file(["org/new", "org/a"], "id")
        router = self._fresh_file(["lab/y", "lab/new"], "slug")
        arguments = (
            "--fresh-hf", hf, "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
            "--fresh-or", router, "--fresh-or-timestamp", "2026-10-20T09:42:00Z",
            "--fresh-label", "run 123")
        self.assertEqual(self._document(*arguments).encode("utf-8"),
                         self._document(*arguments).encode("utf-8"))


class IdentityRankingsTests(RankingsFixture):
    """Committed column identities remain fixed across quiet rebuilds."""

    def _land_fresh(self):
        page = self.repo / "out/trending-rankings.html"
        arguments = ["--repo", str(self.repo), "--out", str(page),
                     "--fresh-label", 'run 12345 & "capture"']
        for path, key, flag, models, timestamp in (
                (HF, "id", "hf", ["org/b", "org/new"], "2026-10-20T09:41:00Z"),
                (OR, "slug", "or", ["lab/y", "lab/new"], "2026-10-20T09:42:00Z")):
            fresh = self.repo / path
            fresh.write_text(json.dumps({"models": [{key: model} for model in models]}),
                             encoding="utf-8")
            arguments.extend([f"--fresh-{flag}", str(fresh), f"--fresh-{flag}-timestamp",
                              timestamp])
        build_rankings.main(arguments)
        self._git("add", HF, OR, "out/trending-rankings.html")
        self._git("commit", "-qm", "Land snapshots and page")
        return page

    def test_sha_identity_is_a_fixed_point_with_a_single_snapshot(self):
        original = self._document()
        identity = pathlib.Path(self.directory) / "identity.html"
        identity.write_text(original, encoding="utf-8")
        for limit in (1, 10):
            with self.subTest(limit=limit):
                self.assertEqual(self._document("--identity-page", str(identity),
                                                "--limit", str(limit)), original)

    def test_fresh_landing_preserves_identity_and_full_independent_windows(self):
        for index in range(12):
            self.commit(HF, [f"org/old-{index}"], "id")
        self.commit(OR, ["lab/old"], "slug")
        page = self._land_fresh()
        original = page.read_text(encoding="utf-8")
        # Identity supplies labels, while ranks come from the selected git ref.
        selected = self._git("rev-parse", "HEAD").strip()
        self.commit(HF, ["org/later"], "id")
        (self.repo / OR).write_text("uncommitted invalid JSON", encoding="utf-8")
        rebuilt = self._document("--identity-page", str(page), "--commit", selected)
        self.assertEqual(rebuilt, original)
        sections = re.findall(r'<section\b.*?</section>', rebuilt, re.S)
        self.assertEqual([section.count('class="timestamp-tick"') for section in sections],
                         [10, 3])

    def test_stale_identity_uses_history_while_the_matching_list_keeps_its_identity(self):
        page = self._land_fresh()
        original = re.findall(r'<section\b.*?</section>', page.read_text(encoding="utf-8"), re.S)
        landed = self.commit(HF, ["new/model"], "id")
        timestamp = datetime.fromisoformat(self._git("show", "-s", "--format=%cI", landed)
                                           .strip()).astimezone(timezone.utc).isoformat()
        timestamp = timestamp.replace("+00:00", "Z")
        self.commit(HF, ["later/model"], "id")
        pure = re.findall(r'<section\b.*?</section>',
                          self._document("--commit", landed), re.S)
        rebuilt = self._document("--identity-page", str(page), "--commit", landed)
        sections = re.findall(r'<section\b.*?</section>', rebuilt, re.S)
        self.assertEqual(sections[0], pure[0])
        self.assertEqual(sections[1], original[1])
        points = Page(sections[0]).points
        right = max(float(point["cx"]) for point in points)
        newest = [point for point in points if float(point["cx"]) == right]
        self.assertEqual({point["data-commit"] for point in newest}, {landed})
        self.assertEqual({point["data-timestamp"] for point in newest}, {timestamp})
        self.assertEqual({point["data-model"]: point["data-rank"] for point in newest},
                         {"new/model": "1"})

    def test_fresh_input_changes_only_its_section_beside_identity_reconstruction(self):
        page = self._land_fresh()
        original = re.findall(r'<section\b.*?</section>', page.read_text(encoding="utf-8"), re.S)
        for flag, path, key, identifier in (("hf", HF, "id", 0), ("or", OR, "slug", 1)):
            with self.subTest(flag=flag):
                fresh = pathlib.Path(self.directory) / "new.json"
                fresh.write_text(json.dumps({"models": [{key: "new/model"}]}), encoding="utf-8")
                rebuilt = self._document(
                    "--identity-page", str(page), f"--fresh-{flag}", str(fresh),
                    f"--fresh-{flag}-timestamp", "2026-10-20T10:41:00Z",
                    "--fresh-label", "run 54321")
                sections = re.findall(r'<section\b.*?</section>', rebuilt, re.S)
                self.assertNotEqual(sections[identifier], original[identifier], path)
                self.assertEqual(sections[1 - identifier], original[1 - identifier], path)

    def test_fresh_list_ignores_its_missing_or_unparseable_identity_section(self):
        original = self._document()
        sections = re.findall(r'<section\b.*?</section>', original, re.S)
        identity = pathlib.Path(self.directory) / "identity.html"
        for flag, path, index in (("hf", HF, 0), ("or", OR, 1)):
            arguments = [f"--fresh-{flag}", str(self.repo / path),
                         f"--fresh-{flag}-timestamp", "2026-10-20T09:41:00Z",
                         "--fresh-label", "run 12345"]
            expected = self._document(*arguments)
            for section in ("", sections[index].replace('class="point"', 'class="gone"')):
                with self.subTest(flag=flag, missing=not section):
                    identity.write_text(original.replace(sections[index], section),
                                        encoding="utf-8")
                    self.assertEqual(self._document(*arguments, "--identity-page", str(identity)),
                                     expected)
            identity.write_text(original.replace(sections[1 - index], ""), encoding="utf-8")
            with self.subTest(flag=flag, missing_inactive=True):
                with self.assertRaises(SystemExit) as caught:
                    self._document(*arguments, "--identity-page", str(identity))
                self.assertEqual(caught.exception.code, 2)

    def test_both_fresh_lists_never_consult_the_identity_page(self):
        arguments = ["--fresh-hf", str(self.repo / HF),
                     "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
                     "--fresh-or", str(self.repo / OR),
                     "--fresh-or-timestamp", "2026-10-20T09:42:00Z",
                     "--fresh-label", "run 12345"]
        expected = self._document(*arguments)
        invalid = pathlib.Path(self.directory) / "invalid.html"
        invalid.write_text("no parseable columns", encoding="utf-8")
        for identity in (invalid, pathlib.Path(self.directory) / "missing.html",
                         pathlib.Path(self.directory)):
            with self.subTest(identity=identity.name):
                self.assertEqual(self._document(*arguments, "--identity-page", str(identity)),
                                 expected)

    def test_unparseable_or_unreadable_identity_errors_without_writing_output(self):
        original = self._document()
        identity = pathlib.Path(self.directory) / "identity.html"
        for case, document in (
                ("empty", b""),
                ("no-points", original.replace('class="point"', 'class="gone"').encode()),
                ("nonfinite", original.replace('cx="180.0"', 'cx="nan"', 1).encode()),
                ("missing", None)):
            with self.subTest(case=case):
                if document is None:
                    identity.unlink()
                else:
                    identity.write_bytes(document)
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/build_rankings.py"),
                     "--identity-page", str(identity)], cwd=self.repo, check=False,
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("identity", result.stderr)
                self.assertNotIn("unrecognized arguments", result.stderr)
                self.assertFalse((self.repo / "out/trending-rankings.html").exists())
