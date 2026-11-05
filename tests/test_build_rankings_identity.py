"""Exercise the rankings page's preserved column identities against real git commits."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_rankings  # noqa: E402  # pylint: disable=wrong-import-position
from test_build_rankings import (  # noqa: E402  # pylint: disable=wrong-import-position
    GH, HF, OR, Page, RankingsFixture)


class IdentityRankingsTests(RankingsFixture):
    """Committed column identities remain fixed across quiet rebuilds."""

    def _land_fresh(self):
        page = self.repo / "out/trending-rankings.html"
        arguments = ["--repo", str(self.repo), "--out", str(page),
                     "--fresh-label", 'run 12345 & "capture"']
        for path, key, flag, models, timestamp in (
                (HF, "id", "hf", ["org/b", "org/new"], "2026-10-20T09:41:00Z"),
                (OR, "slug", "or", ["lab/y", "lab/new"], "2026-10-20T09:42:00Z"),
                (GH, "full_name", "github", ["octo/b", "octo/new"], "2026-10-20T09:43:00Z")):
            fresh = self.repo / path
            fresh.write_text(json.dumps({"models": [{key: model} for model in models]}),
                             encoding="utf-8")
            arguments.extend([f"--fresh-{flag}", str(fresh), f"--fresh-{flag}-timestamp",
                              timestamp])
        build_rankings.main(arguments)
        self._git("add", HF, OR, GH, "out/trending-rankings.html")
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
                         [10, 3, 2])

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
        self.assertEqual(sections[1:], original[1:])
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
        for flag, path, key, identifier in (("hf", HF, "id", 0), ("or", OR, "slug", 1),
                                            ("github", GH, "full_name", 2)):
            with self.subTest(flag=flag):
                fresh = pathlib.Path(self.directory) / "new.json"
                fresh.write_text(json.dumps({"models": [{key: "new/model"}]}), encoding="utf-8")
                rebuilt = self._document(
                    "--identity-page", str(page), f"--fresh-{flag}", str(fresh),
                    f"--fresh-{flag}-timestamp", "2026-10-20T10:41:00Z",
                    "--fresh-label", "run 54321")
                sections = re.findall(r'<section\b.*?</section>', rebuilt, re.S)
                self.assertNotEqual(sections[identifier], original[identifier], path)
                self.assertEqual([section for index, section in enumerate(sections)
                                  if index != identifier],
                                 [section for index, section in enumerate(original)
                                  if index != identifier], path)

    def test_fresh_list_ignores_its_missing_or_unparseable_identity_section(self):
        original = self._document()
        sections = re.findall(r'<section\b.*?</section>', original, re.S)
        identity = pathlib.Path(self.directory) / "identity.html"
        for flag, path, index in (("hf", HF, 0), ("or", OR, 1), ("github", GH, 2)):
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
            identity.write_text(original.replace(sections[(index + 1) % 3], ""), encoding="utf-8")
            with self.subTest(flag=flag, missing_inactive=True):
                with self.assertRaises(SystemExit) as caught:
                    self._document(*arguments, "--identity-page", str(identity))
                self.assertEqual(caught.exception.code, 2)

    def test_all_fresh_lists_never_consult_the_identity_page(self):
        arguments = ["--fresh-hf", str(self.repo / HF),
                     "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
                     "--fresh-or", str(self.repo / OR),
                     "--fresh-or-timestamp", "2026-10-20T09:42:00Z",
                     "--fresh-github", str(self.repo / GH),
                     "--fresh-github-timestamp", "2026-10-20T09:43:00Z",
                     "--fresh-label", "run 12345"]
        expected = self._document(*arguments)
        invalid = pathlib.Path(self.directory) / "invalid.html"
        invalid.write_text("no parseable columns", encoding="utf-8")
        for identity in (invalid, pathlib.Path(self.directory) / "missing.html",
                         pathlib.Path(self.directory)):
            with self.subTest(identity=identity.name):
                self.assertEqual(self._document(*arguments, "--identity-page", str(identity)),
                                 expected)

    def test_two_fresh_lists_still_consult_the_identity_page_for_the_third(self):
        arguments = ["--fresh-hf", str(self.repo / HF),
                     "--fresh-hf-timestamp", "2026-10-20T09:41:00Z",
                     "--fresh-or", str(self.repo / OR),
                     "--fresh-or-timestamp", "2026-10-20T09:42:00Z",
                     "--fresh-label", "run 12345"]
        invalid = pathlib.Path(self.directory) / "invalid.html"
        invalid.write_text("no parseable columns", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self._document(*arguments, "--identity-page", str(invalid))
        self.assertEqual(caught.exception.code, 2)

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
