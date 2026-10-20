"""Exercise the rankings-page gate against deterministic fixture history."""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent.parent
for entry in ("scripts/ci", "scripts"):
    entry_path = HERE / entry
    if str(entry_path) not in sys.path:
        sys.path.insert(0, str(entry_path))

import check_committed_rankings_page  # noqa: E402  # pylint: disable=wrong-import-position
import build_rankings  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_build_rankings  # noqa: E402  # pylint: disable=wrong-import-position


class CheckCommittedRankingsPageTests(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """A missing, stale or unbuildable page must fail the CI check."""

    def setUp(self):
        self.harness = test_build_rankings.RankingsTests()
        self.harness.setUp()
        self.addCleanup(self.harness.doCleanups)
        self.repo = self.harness.repo
        self.page = self.repo / "out/trending-rankings.html"
        build_rankings.main(["--repo", str(self.repo), "--out", str(self.page)])
        self.harness._git("add", "out/trending-rankings.html")  # pylint: disable=protected-access
        self.harness._git("commit", "-qm", "Commit rankings page")  # pylint: disable=protected-access

    def run_check(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import pathlib, sys; sys.path.insert(0, sys.argv[1]); "
             "import check_committed_rankings_page as check; "
             "sys.exit(check.main(pathlib.Path(sys.argv[2])))",
             str(HERE / "scripts/ci"), str(self.repo)],
            check=False, capture_output=True, text=True, timeout=60)
        return result.returncode, result.stdout, result.stderr

    def run_check_in_process(self):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = check_committed_rankings_page.main(self.repo)
        return code, output.getvalue(), error.getvalue()

    def test_identical_page_passes(self):
        for path, key in (("data/hf-trending.json", "id"),
                          ("data/openrouter-trending.json", "slug")):
            self.assertEqual(len(build_rankings.read_history(self.repo, path, key, 10)), 1)
        before = self.page.read_bytes()
        code, output, error = self.run_check()
        self.assertEqual(code, 0, error)
        self.assertIn("-- ok", output)
        self.assertEqual(error, "")
        self.assertEqual(self.page.read_bytes(), before)

    def test_empty_tracker_histories_refuse_even_matching_pages(self):
        real_git = build_rankings.git
        cases = (("data/hf-trending.json",), ("data/openrouter-trending.json",),
                 ("data/hf-trending.json", "data/openrouter-trending.json"))
        for empty_paths in cases:
            with self.subTest(empty_paths=empty_paths):
                def git(repo, *args, empty=empty_paths):
                    if args[0] == "log" and args[-1] in empty:
                        return ""
                    return real_git(repo, *args)

                with mock.patch.object(build_rankings, "git", side_effect=git):
                    build_rankings.main(["--repo", str(self.repo), "--out", str(self.page)])
                    code, output, error = self.run_check_in_process()
                self.assertEqual(code, 1)
                self.assertNotIn("-- ok", output)
                self.assertEqual(len(error.splitlines()), len(empty_paths))
                for path in empty_paths:
                    self.assertIn(f"{path} history is empty", error)
                self.assertNotIn("differs from a rebuild", error)
                self.assertNotIn("rebuild failed", error)

    def test_empty_histories_and_missing_committed_page_report_all_violations(self):
        real_git = build_rankings.git

        def git(repo, *args):
            if args[0] == "log":
                return ""
            return real_git(repo, *args)

        self.page.unlink()
        with mock.patch.object(build_rankings, "git", side_effect=git):
            code, _, error = self.run_check_in_process()
        self.assertEqual(code, 1)
        self.assertEqual(len(error.splitlines()), 3)
        self.assertIn("data/hf-trending.json history is empty", error)
        self.assertIn("data/openrouter-trending.json history is empty", error)
        self.assertIn("committed page is missing or unreadable", error)

    def test_changed_page_reports_first_differing_region(self):
        self.page.write_bytes(self.page.read_bytes().replace(
            b"<h1>Trending rankings</h1>", b"<h1>Stale rankings</h1>", 1))
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(len(error.splitlines()), 1)
        self.assertIn("differs from a rebuild", error)
        self.assertIn("first difference at index ", error)
        self.assertIn("<h1>Stale rankings</h1>", error)
        self.assertIn("<h1>Trending rankings</h1>", error)

    def test_byte_comparison_preserves_newlines_and_invalid_utf8(self):
        original = self.page.read_bytes()
        for changed in (original.replace(b"\n", b"\r\n"), original + b"\xff"):
            with self.subTest(tail=changed[-10:]):
                self.page.write_bytes(changed)
                code, _, error = self.run_check()
                self.assertEqual(code, 1)
                self.assertEqual(len(error.splitlines()), 1)
                self.assertIn("differs from a rebuild", error)

    def test_missing_committed_page_has_its_own_line(self):
        self.page.unlink()
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(len(error.splitlines()), 1)
        self.assertIn("committed page is missing or unreadable", error)
        self.assertNotIn("rebuild output", error)

    def test_uncommitted_capture_does_not_change_rebuild(self):
        (self.repo / test_build_rankings.HF).write_text("invalid JSON", encoding="utf-8")
        code, _, error = self.run_check()
        self.assertEqual(code, 0, error)

    def test_new_history_makes_the_old_page_fail(self):
        self.harness.commit(test_build_rankings.HF, ["org/b", "org/a"], "id")
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("data/hf-trending.json newest column ranks differ", error)

    def build_fresh_page(self, *, router=True):
        arguments = ["--repo", str(self.repo), "--out", str(self.page),
                     "--fresh-label", 'run 42 & "capture"']
        paths = [(test_build_rankings.HF, "id", ["org/b", "org/a"],
                  "hf", "2026-10-20T09:41:00Z")]
        if router:
            paths.append((test_build_rankings.OR, "slug", ["lab/y", "lab/x"],
                          "or", "2026-10-20T09:42:00Z"))
        for path, key, models, flag, timestamp in paths:
            (self.repo / path).write_text(json.dumps({"models": [
                {key: model} for model in models]}), encoding="utf-8")
            arguments.extend([f"--fresh-{flag}", str(self.repo / path),
                              f"--fresh-{flag}-timestamp", timestamp])
        build_rankings.main(arguments)
        git = self.harness._git  # pylint: disable=protected-access
        git("add", *(path for path, *_ in paths), "out/trending-rankings.html")
        git("commit", "-qm", "Capture lists and rankings together")

    def test_fresh_columns_reconstruct_after_the_capture_lands(self):
        self.build_fresh_page()
        before = self.page.read_bytes()
        code, output, error = self.run_check()
        self.assertEqual(code, 0, error)
        self.assertEqual(error, "")
        self.assertIn("-- ok", output)
        self.assertEqual(self.page.read_bytes(), before)

    def test_one_sided_fresh_column_keeps_other_commit_identity(self):
        self.build_fresh_page(router=False)
        code, _, error = self.run_check()
        self.assertEqual(code, 0, error)
        self.assertEqual(error, "")

    def test_fresh_page_with_newer_landed_ranks_refuses(self):
        self.build_fresh_page()
        self.harness.commit(test_build_rankings.HF, ["org/a", "org/b"], "id")
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("data/hf-trending.json newest column ranks differ", error)
        self.assertNotIn("data/openrouter-trending.json newest column ranks differ", error)

    def test_sha_columns_reconstruct_with_independent_history_windows(self):
        for index in range(12):
            self.harness.commit(test_build_rankings.HF,
                                ["org/a", "org/b"] if index % 2 else ["org/b", "org/a"],
                                "id")
        self.harness.commit(test_build_rankings.OR, ["lab/y", "lab/x"], "slug")
        build_rankings.main(["--repo", str(self.repo), "--out", str(self.page)])
        code, _, error = self.run_check()
        self.assertEqual(code, 0, error)
        self.assertEqual(error, "")

    def test_sha_columns_reconstruct_when_a_model_leaves_and_returns(self):
        self.harness.commit(test_build_rankings.HF, ["org/b", "org/c"], "id")
        self.harness.commit(test_build_rankings.HF, ["org/a", "org/b"], "id")
        build_rankings.main(["--repo", str(self.repo), "--out", str(self.page)])
        code, _, error = self.run_check()
        self.assertEqual(code, 0, error)

    def test_single_model_sections_still_have_parseable_columns(self):
        git = self.harness._git  # pylint: disable=protected-access
        git("checkout", "--orphan", "one-model")
        git("rm", "-rf", "--cached", ".")
        self.harness.commit(test_build_rankings.HF, ['org/a & "quoted"'], "id")
        self.harness.commit(test_build_rankings.OR, ["lab/x"], "slug")
        build_rankings.main(["--repo", str(self.repo), "--out", str(self.page)])
        code, _, error = self.run_check()
        self.assertEqual(code, 0, error)

    def test_missing_newest_column_is_a_tracker_violation(self):
        self.page.write_bytes(self.page.read_bytes().replace(b'class="point"', b'class="gone"'))
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("data/hf-trending.json newest column is missing or unparseable", error)
        self.assertIn("data/openrouter-trending.json newest column is missing or unparseable",
                      error)

    def test_newest_column_with_mixed_identity_is_unparseable(self):
        self.build_fresh_page()
        self.page.write_bytes(self.page.read_bytes().replace(
            b'data-commit="run 42 &amp; &quot;capture&quot;"',
            b'data-commit="different"', 1))
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("data/hf-trending.json newest column is missing or unparseable", error)

    def test_nonfinite_column_position_is_unparseable(self):
        self.page.write_bytes(self.page.read_bytes().replace(b'cx="180.0"', b'cx="nan"', 1))
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("data/hf-trending.json newest column is missing or unparseable", error)

    def test_pr_merge_checks_the_merged_result(self):
        git = self.harness._git  # pylint: disable=protected-access
        branch = git("rev-parse", "HEAD").strip()
        original = self.page.read_bytes()
        # GitHub's merge ref puts updated main first and the tested branch second.
        git("checkout", "-q", "-b", "updated-main", branch + "^")
        self.harness.commit(test_build_rankings.HF, ["org/b", "org/new"], "id")
        self.harness.commit(test_build_rankings.OR, ["lab/y", "lab/new"], "slug")
        updated_main = git("rev-parse", "HEAD").strip()
        git("merge", "--no-ff", "-qm", "Simulate the PR merge ref", branch)
        parents = git("rev-list", "--parents", "-n", "1", "HEAD").split()
        self.assertEqual(parents[1:], [updated_main, branch])
        merged_page = self.repo / "out/merged-rankings.html"
        build_rankings.main(["--repo", str(self.repo), "--out", str(merged_page)])
        merged = merged_page.read_bytes()
        self.assertNotEqual(original, merged, "walking merged HEAD must change the snapshot window")
        self.assertTrue(check_committed_rankings_page.verify(original, merged))
        for label, page, expected in (("branch", original, 1), ("merged", merged, 0)):
            with self.subTest(history=label):
                self.page.write_bytes(page)
                code, _, error = self.run_check()
                self.assertEqual(code, expected, error)
                if expected:
                    self.assertIn("differs from a rebuild", error)

    def merge_into_refreshed_main(self, branch):
        """Merge the branch after main lands both rank reorders and their page."""
        git = self.harness._git  # pylint: disable=protected-access
        git("checkout", "-q", "main")
        self.build_fresh_page()
        main_page = self.page.read_bytes()
        code, _, error = self.run_check()
        self.assertEqual(code, 0, error)
        updated_main = git("rev-parse", "HEAD").strip()
        git("merge", "--no-ff", "-X", "theirs", "-qm", "Merge branch into refreshed main", branch)
        parents = git("rev-list", "--parents", "-n", "1", "HEAD").split()
        self.assertEqual(parents[1:], [updated_main, branch])
        return main_page

    def test_pr_merge_with_untouched_rankings_passes_after_main_refresh(self):
        git = self.harness._git  # pylint: disable=protected-access
        git("checkout", "-q", "-b", "unrelated-change")
        (self.repo / "README.md").write_text("Unrelated change\n", encoding="utf-8")
        git("add", "README.md")
        git("commit", "-qm", "Update unrelated documentation")
        branch = git("rev-parse", "HEAD").strip()
        main_page = self.merge_into_refreshed_main(branch)
        self.assertEqual(self.page.read_bytes(), main_page)
        code, output, error = self.run_check()
        self.assertEqual(code, 0, error)
        self.assertEqual(error, "")
        self.assertIn("-- ok", output)

    def test_pr_merge_with_only_tracker_edit_refuses_main_page(self):
        git = self.harness._git  # pylint: disable=protected-access
        self.harness.commit(test_build_rankings.HF, ["org/a", "org/b", "org/c"], "id")
        build_rankings.main(["--repo", str(self.repo), "--out", str(self.page)])
        git("add", "out/trending-rankings.html")
        git("commit", "-qm", "Commit rankings for three models")
        git("checkout", "-q", "-b", "tracker-change")
        branch = self.harness.commit(test_build_rankings.HF, ["org/b", "org/c", "org/a"], "id")
        branch_tracker = (self.repo / test_build_rankings.HF).read_bytes()
        main_page = self.merge_into_refreshed_main(branch)
        self.assertEqual(self.page.read_bytes(), main_page)
        self.assertEqual((self.repo / test_build_rankings.HF).read_bytes(), branch_tracker)
        code, _, error = self.run_check()
        self.assertEqual(code, 1, error)
        self.assertIn("data/hf-trending.json newest column ranks differ from landed JSON", error)
        self.assertNotIn("data/openrouter-trending.json newest column ranks differ", error)

    def test_pr_merge_with_only_page_edit_refuses_changed_page(self):
        git = self.harness._git  # pylint: disable=protected-access
        git("checkout", "-q", "-b", "page-change")
        self.page.write_bytes(self.page.read_bytes().replace(
            b"<h1>Trending rankings</h1>", b"<h1>Stale rankings</h1>", 1))
        git("add", "out/trending-rankings.html")
        git("commit", "-qm", "Change rankings heading")
        branch = git("rev-parse", "HEAD").strip()
        main_page = self.merge_into_refreshed_main(branch)
        self.assertNotEqual(self.page.read_bytes(), main_page)
        self.assertIn(b"<h1>Stale rankings</h1>", self.page.read_bytes())
        code, _, error = self.run_check()
        self.assertEqual(code, 1, error)
        self.assertIn("differs from a rebuild", error)

    def test_failed_rebuild_is_red(self):
        self.harness.commit(test_build_rankings.HF, [None], "id")
        code, _, error = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("rebuild failed", error)
        self.assertIn("red, never a silent pass", error)

    def test_system_exit_from_builder_is_red(self):
        with mock.patch.object(build_rankings, "main", side_effect=SystemExit(2)):
            code, _, error = self.run_check_in_process()
        self.assertEqual(code, 1)
        self.assertIn("rebuild failed", error)

    def test_missing_rebuild_output_has_its_own_line(self):
        with mock.patch.object(build_rankings, "main"):
            code, _, error = self.run_check_in_process()
        self.assertEqual(code, 1)
        self.assertEqual(len(error.splitlines()), 1)
        self.assertIn("rebuild output is missing or unreadable", error)

    def test_missing_second_rebuild_output_is_red(self):
        real_main = build_rankings.main
        builds = []

        def build(arguments):
            builds.append(arguments)
            if len(builds) == 1:
                real_main(arguments)

        with mock.patch.object(build_rankings, "main", side_effect=build):
            code, _, error = self.run_check_in_process()
        self.assertEqual(code, 1)
        self.assertIn("rebuild output is missing or unreadable", error)

    def test_both_missing_pages_report_distinct_lines(self):
        self.page.unlink()
        with mock.patch.object(build_rankings, "main"):
            code, _, error = self.run_check_in_process()
        self.assertEqual(code, 1)
        self.assertEqual(len(error.splitlines()), 2)
        self.assertIn("committed page is missing or unreadable", error)
        self.assertIn("rebuild output is missing or unreadable", error)
