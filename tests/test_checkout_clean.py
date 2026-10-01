"""Pins the issue #114 invariant: the suite leaves the checkout clean.

The build-writing tests used to call build.main() with only stdout
redirected, rewriting the real out/frontier-models.html in place -- with
the source-commit stamp stripped locally (AA_SOURCE_COMMIT unset), so a
quiet `python3 -m pytest -q` left `git status --porcelain` reporting
` M out/frontier-models.html`.

The pin runs the build-writing tests in a SUBPROCESS and requires the
checkout state to be identical before and after, where the state is BOTH
`git status --porcelain` AND the bytes of out/frontier-models.html:

- Why the bytes join the text: porcelain is content-blind. It compares
  the working tree to the index, so a rewrite that leaves the same
  content as before the subprocess started moves neither side -- run 1
  against broken code dirties out/, and run 2's before/after text
  snapshots are then equal (observed: rc 0 on the second run). The
  sha256 of out/frontier-models.html folds the content into the oracle,
  and the AA_SOURCE_COMMIT marker below makes every dirtying build
  produce bytes nothing else could have written, so the digest moves.
- What the text snapshot includes, deliberately: `--porcelain` reports
  tracked modifications and untracked NON-ignored files. It does not
  report ignored paths, and this repo's deny-by-default .gitignore
  ignores everything not named back -- pytest's caches, `__pycache__/`
  and the dot-prefixed temp dirs the tests create under build.ROOT are
  all invisible to it. So the text is exactly "which shipped files
  moved". Pre-existing dirt survives the run unchanged and passes,
  deliberately: the oracle is "the tests add no dirt", not "the tree was
  clean".
- Why a subprocess and which subset: the build-writing tests themselves.
  Running this file's own test there would recurse (a test that spawns a
  suite that runs the test), so the subset names explicit node ids in
  tests/test_build.py and tests/test_browser.py only. The four writer
  sites map to four ids: GeneratedArtifactTests is named at class
  granularity so both its writer tests run, and the other three sites
  are single tests (a class's setUpClass build fires for any one of its
  tests).
- Where the browser ids run: the tests.yml matrix installs playwright
  (so collection succeeds) but no Chromium, and the browser writers'
  classes build in setUpClass -- their ids would die in chromium.launch
  and fail every matrix cell. browser_available() probes the suite's own
  launch recipe (test_browser.CHROMIUM_EXECUTABLE for the system path /
  CHROMIUM_PATH override, playwright's own launch call for its managed
  install) and the pin runs all four ids only where that recipe
  launches; elsewhere it runs the two tests/test_build.py ids, which
  keep the pin biting in every cell. The browser ids are exercised in
  the coverage job, which is where the browser writers actually run.
- Why AA_SOURCE_COMMIT is set to a fresh random value: in CI the suite
  step inherits AA_SOURCE_COMMIT = github.sha -- exactly what the
  committed page was stamped with, so even a dirtying rewrite could come
  out byte-identical to HEAD and move nothing. A fresh 40-hex marker
  defeats that: the value is SHA-shaped because build.py renders only
  well-shaped values (7-40 hex chars).
- Why JS_COVERAGE_OUT is stripped: the coverage job sets it, and
  BrowserInteractionTests.tearDownClass OVERWRITES the dump file at that
  path. Inherited into the subprocess, the subset's partial coverage
  would overwrite the outer run's full dump and the JS-coverage ratchet
  would read truncated evidence.
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent

# tests/ is not a package; import the browser suite's own module for its
# browser resolution rather than re-deriving a second resolver.
if str(pathlib.Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_browser  # noqa: E402  # pylint: disable=wrong-import-position
from playwright.sync_api import (  # noqa: E402  # pylint: disable=wrong-import-position
    sync_playwright)

# The guarded file whose bytes join the oracle: the page every writer
# targets.
GUARDED_PAGE = HERE / "out" / "frontier-models.html"

GIT_TIMEOUT = 60  # seconds; git status is local and fast

# The subset runs browser launches plus two page builds; 600 s is roughly
# 15x the measured runtime, generous for a slow CI host without masking a
# genuinely hung subprocess.
SUBSET_TIMEOUT = 600  # seconds

# The two ids whose classes build in setUpClass -- they need a browser.
BROWSER_WRITER_IDS = (
    "tests/test_browser.py::BrowserInteractionTests::"
    "test_footer_carries_a_licence_note_linking_the_licence",
    "tests/test_browser.py::PerfBudgetTests::"
    "test_every_journey_meets_its_committed_budget",
)

# The two ids that run anywhere: the writers in tests/test_build.py.
NON_BROWSER_WRITER_IDS = (
    "tests/test_build.py::GeneratedArtifactTests",
    "tests/test_build.py::DisplayNameRowTests::"
    "test_the_built_page_carries_no_dict_effort_text_anywhere",
)

ALL_WRITER_IDS = BROWSER_WRITER_IDS + NON_BROWSER_WRITER_IDS


def browser_available() -> bool:
    """Whether the browser ids can run here: the suite's own launch
    recipe succeeds.

    Reuses test_browser's CHROMIUM_EXECUTABLE resolution (the system
    path, overridable by CHROMIUM_PATH) and lets playwright itself
    resolve its managed install through the same launch call the suite
    uses -- a launch probe, not a second resolver: since playwright 1.49
    a headless launch resolves to the headless-shell binary, which no
    filename check names without re-implementing the registry. Fails
    fast where no browser exists (the matrix cells).
    """
    try:
        with sync_playwright() as probe:
            browser = probe.chromium.launch(
                executable_path=test_browser.CHROMIUM_EXECUTABLE,
                headless=True,
                args=["--no-sandbox"])
            browser.close()
    except Exception:  # pylint: disable=broad-exception-caught
        return False
    return True


def snapshot() -> tuple:
    """The checkout state as (porcelain text, guarded-page sha256).

    The page digest reads as None when the file does not exist; both
    snapshots then compare None == None, so a checkout without a built
    page is handled the same way the text side is.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(HERE), capture_output=True, check=False,
        timeout=GIT_TIMEOUT)
    assert proc.returncode == 0, proc.stderr
    try:
        digest = hashlib.sha256(GUARDED_PAGE.read_bytes()).hexdigest()
    except FileNotFoundError:
        digest = None
    return proc.stdout.decode("utf-8"), digest


class CheckoutCleanTests(unittest.TestCase):
    def test_the_build_writing_tests_leave_the_checkout_clean(self):
        with_browser = browser_available()
        subset = ALL_WRITER_IDS if with_browser else NON_BROWSER_WRITER_IDS
        partition = (f"writer ids: {len(subset)}/{len(ALL_WRITER_IDS)} "
                     f"(browser {'present' if with_browser else 'ABSENT'})")
        print(partition, flush=True)  # visible under -s and on failure

        try:
            before = snapshot()
        except subprocess.TimeoutExpired:
            self.fail(
                f"the pre-run git status exceeded its {GIT_TIMEOUT} s ceiling")

        env = dict(os.environ)
        env["AA_SOURCE_COMMIT"] = os.urandom(20).hex()
        env.pop("JS_COVERAGE_OUT", None)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", *subset],
                cwd=str(HERE), capture_output=True, check=False, env=env,
                timeout=SUBSET_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.fail(f"{partition}: the build-writing subset exceeded its "
                      f"{SUBSET_TIMEOUT} s ceiling")

        try:
            after = snapshot()
        except subprocess.TimeoutExpired:
            self.fail(
                f"the post-run git status exceeded its {GIT_TIMEOUT} s ceiling")

        tail = proc.stdout.decode("utf-8", "replace")[-2000:]
        self.assertEqual(
            proc.returncode, 0,
            f"{partition}: the build-writing subset itself failed:\n{tail}")
        self.assertEqual(
            after, before,
            f"{partition}: the build-writing tests dirtied the checkout:\n"
            f"{after}\n"
            f"subset tail:\n{tail}")
