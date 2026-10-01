"""Pins the issue #114 invariant: the suite leaves the checkout clean.

The build-writing tests used to call build.main() with only stdout
redirected, rewriting the real out/frontier-models.html in place -- with
the source-commit stamp stripped locally (AA_SOURCE_COMMIT unset), so a
quiet `python3 -m pytest -q` left `git status --porcelain` reporting
` M out/frontier-models.html`.

The pin runs the build-writing tests in a SUBPROCESS and requires
`git status --porcelain` to be identical before and after:

- What the snapshot includes, deliberately: `--porcelain` reports tracked
  modifications and untracked NON-ignored files. It does not report
  ignored paths, and this repo's deny-by-default .gitignore ignores
  everything not named back -- pytest's caches, `__pycache__/` and the
  dot-prefixed temp dirs the tests create under build.ROOT are all
  invisible to it. So the snapshot is exactly "which SHIPPED files moved".
- Why a subprocess and which subset: the build-writing tests themselves.
  Running this file's own test there would recurse (a test that spawns a
  suite that runs the test), so the subset names explicit node ids in
  tests/test_build.py and tests/test_browser.py only -- one test of each
  build-writing class is enough, because a class's build happens in its
  setUpClass or in the class's tests, and the whole class runs either way.
- Why AA_SOURCE_COMMIT is set to a fresh random value: without it the pin
  false-passes. A dirtying rebuild is idempotent once out/ is already
  stamp-less (a second suite run rewrites the same bytes, porcelain
  equal, defect invisible), and in CI the suite step inherits
  AA_SOURCE_COMMIT = github.sha -- exactly what the committed page was
  stamped with, so even a dirtying rewrite would come out byte-identical.
  A fresh 40-hex marker defeats both: any surviving real-out writer
  produces bytes nothing else could have written, so the after-snapshot
  differs. The value is SHA-shaped because build.py renders only
  well-shaped values (7-40 hex chars).
- Why JS_COVERAGE_OUT is stripped: the coverage job sets it, and
  BrowserInteractionTests.tearDownClass OVERWRITES the dump file at that
  path. Inherited into the subprocess, the subset's partial coverage
  would overwrite the outer run's full dump and the JS-coverage ratchet
  would read truncated evidence.
"""
import os
import pathlib
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent

# One test per build-writing class: BrowserInteractionTests (setUpClass
# build), PerfBudgetTests (setUpClass build) and GeneratedArtifactTests
# (two in-test builds). No node id names this file, so the subprocess
# cannot recurse into the pin.
BUILD_WRITING_TESTS = (
    "tests/test_browser.py::BrowserInteractionTests::"
    "test_footer_carries_a_licence_note_linking_the_licence",
    "tests/test_browser.py::PerfBudgetTests::"
    "test_every_journey_meets_its_committed_budget",
    "tests/test_build.py::GeneratedArtifactTests",
)


def porcelain() -> str:
    """`git status --porcelain` for the repo rooted at HERE."""
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(HERE), capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8")


class CheckoutCleanTests(unittest.TestCase):
    def test_the_build_writing_tests_leave_the_checkout_clean(self):
        before = porcelain()
        env = dict(os.environ)
        env["AA_SOURCE_COMMIT"] = os.urandom(20).hex()
        env.pop("JS_COVERAGE_OUT", None)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *BUILD_WRITING_TESTS],
            cwd=str(HERE), capture_output=True, check=False, env=env)
        after = porcelain()

        self.assertEqual(
            proc.returncode, 0,
            f"the build-writing subset itself failed:\n"
            f"{proc.stdout.decode('utf-8', 'replace')[-3000:]}"
            f"{proc.stderr.decode('utf-8', 'replace')[-2000:]}")
        self.assertEqual(
            after, before,
            "the build-writing tests dirtied the checkout:\n"
            f"{after or '(nothing)'}\n"
            f"subset tail:\n{proc.stdout.decode('utf-8', 'replace')[-2000:]}")
