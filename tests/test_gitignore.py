"""Pins the issue #165 invariant: the paths the refresh commits are
git-trackable.

The refresh workflow's commit step `git add`s its data paths. The
deny-by-default .gitignore's data block names those paths back with `!`
rules, and once one of them was missing the add exited 1 (issue #165):
nothing was committed, the publish was skipped, and the hour stayed red.
Fixing the block without a pin leaves the same rot available: any later
edit that re-hides a committed path re-breaks the hour the same silent
way -- `git status` will not tell you (an ignored file never appears on
it), and the workflow only reds at the commit step, a full capture and a
green suite later.

So the pin: every path the refresh's commit step names is NOT ignored.
`git check-ignore -q` exits 0 exactly when the ignore rules hide a path
(regardless of whether the file exists) and 1 when it is trackable, so
the verdict is that call's exit code. The verbose form is run only on
the failure path, to name the matching rule in the assertion message --
and ONLY there, because with `--verbose` git exits 0 even when the
matched pattern is a negation (the path is NOT ignored), so `-v` can
never deliver the verdict itself (observed under git 2.47.3: a
`!/data/aa-raw-models.json` rule matching the data block's own path still
exited 0).

The path list is derived, not a hand-copied twin of the workflow's: the
commit step is located by name and its `git add` commands are parsed,
so a path the workflow starts adding joins this pin without a second
edit -- the review corpus's shared-literal lesson, seen here in PRs 119
and 151 before this. A parse that names no path is a failure (vacuity
guard), never an empty pass.

The suite runs in a real checkout, so this is cheap. The suite never
writes into data/ (fixture rules) -- this file only evaluates the ignore
rules against pathnames, which `git check-ignore` does without the files
existing. The workflow-side proof (a committed path `git add`ing
cleanly and staging) was performed by hand against the real checkout and
reproduced in a scratch clone; in-suite it would dirty data/, which the
fixture rules forbid.
"""
import pathlib
import re
import subprocess
import tempfile
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parent.parent

GIT_TIMEOUT = 60  # seconds; git check-ignore is local and fast


def added_paths(workflow_name="refresh.yml", job="publish",
                step_name="Commit the capture"):
    """The named workflow step's git-add paths, derived rather than copied."""
    workflow = yaml.safe_load(
        (HERE / ".github/workflows" / workflow_name).read_text(encoding="utf-8"))
    steps = [s for s in workflow["jobs"][job]["steps"]
             if s.get("name") == step_name]
    assert len(steps) == 1, (
        f"expected exactly one {step_name!r} step in {workflow_name}'s "
        f"{job} job, found {len(steps)}")
    # Join backslash continuations first, so an add split across lines
    # is read whole. Comment lines are dropped BEFORE the join, not after:
    # prose in the step mentions the adds it makes -- `git add <path>` in
    # a rationale for issue #202 -- and a comment is not an add, so a
    # path named only in one must not join the pin and be measured
    # against .gitignore's rules for a file the refresh never stages.
    joined = []
    for line in steps[0]["run"].splitlines():
        if line.lstrip().startswith("#"):
            continue
        if joined and joined[-1].rstrip().endswith("\\"):
            joined[-1] = joined[-1].rstrip().rstrip("\\") + " " + line.strip()
        else:
            joined.append(line)
    paths = []
    for line in joined:
        match = re.search(r"\bgit add\s+(.*)$", line)
        if match is not None:
            tail = match.group(1).replace("\\", " ")
            paths.extend(t for t in tail.split() if not t.startswith("-"))
    assert paths, "no git add paths parsed from the commit step"
    return paths


class GitignoreTrackableTests(unittest.TestCase):
    """The committed data paths must survive .gitignore's deny-by-default."""

    def test_generation_state_is_git_trackable(self):
        with tempfile.TemporaryDirectory(prefix="issue-258-ignore-") as tmp:
            root = pathlib.Path(tmp)
            (root / ".gitignore").write_bytes((HERE / ".gitignore").read_bytes())
            (root / "data").mkdir()
            (root / "data/aa-generation-state.json").write_text("{}", encoding="utf-8")
            (root / "data/unshipped.json").write_text("{}", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True,
                           capture_output=True, timeout=GIT_TIMEOUT)
            for path, code in [("data/aa-generation-state.json", 1),
                               ("data/unshipped.json", 0)]:
                verdict = subprocess.run(["git", "check-ignore", "-q", path],
                                         cwd=root, check=False, capture_output=True,
                                         timeout=GIT_TIMEOUT)
                self.assertEqual(verdict.returncode, code)

    def test_hf_trending_list_is_git_trackable(self):
        path = "data/hf-trending.json"
        verdict = check_ignore(["--no-index", "-q"], path)

        self.assertEqual(
            verdict.returncode, 1,
            f"{path} is hidden by .gitignore; it must be a tracked output")

    def test_the_paths_the_trending_workflow_commits_are_git_trackable(self):
        paths = added_paths("hf-trending.yml", "fetch", "Commit when changed")
        self.assertEqual(paths, ["data/hf-trending.json"])
        for path in paths:
            verdict = check_ignore(["--no-index", "-q"], path)
            self.assertEqual(verdict.returncode, 1, f"{path} is hidden by .gitignore")

    def test_the_paths_the_refresh_commits_are_git_trackable(self):
        for path in added_paths():
            with self.subTest(path=path):
                verdict = check_ignore(["-q"], path)
                # 0 = hidden by the rules, 1 = trackable; anything else
                # is a git error, named rather than read as a verdict.
                self.assertIn(
                    verdict.returncode, (0, 1),
                    f"git check-ignore -q errored on {path}: "
                    f"{verdict.stderr.decode('utf-8', 'replace')}")
                if verdict.returncode == 1:
                    continue
                # Hidden: name the matching rule so the offending
                # .gitignore line is findable from the failure alone.
                detail = check_ignore(["-v"], path)
                self.fail(
                    f"{path} is hidden by an ignore rule:\n"
                    f"{detail.stdout.decode('utf-8', 'replace')}")


def check_ignore(flags, path):
    """git check-ignore <flags> -- <path> in the checkout under test."""
    return subprocess.run(
        ["git", "check-ignore", *flags, "--", path],
        cwd=str(HERE), capture_output=True, check=False,
        timeout=GIT_TIMEOUT)


# Synthetic probe paths: no real artifact would ever carry them. The data
# block names the AA captures, the Hugging Face trending list, `captured-at.txt`
# and the optional cost-window marker; out/ names exactly one page. A future
# legitimate negation names a concrete path, so it cannot match a synthetic
# name and turn these probes falsely red. Any edit broad enough to un-deny a
# probe flips the verdict -- a wholesale `!/data/*` (the issue's own repro) or
# a class-scoped `!/data/*.json` alike -- and every such edit is exactly the
# rot this pin exists to catch, because each un-denies scratch files too.
DENY_PROBE_PATHS = (
    "data/zz-deny-probe-synthetic.json",
    "out/zz-deny-probe-synthetic.html",
)


class GitignoreDenyDirectionTests(unittest.TestCase):
    """Pins the deny DIRECTION of the data/ and out/ blocks (issue #169).

    test_the_paths_the_refresh_commits_are_git_trackable proves the
    positive half: the paths the refresh names are NOT ignored. This is
    the negative half: everything else in those trees stays ignored.
    The two together pin the deny-by-default SHAPE of the blocks.
    Without this half, an over-broad negation (`!/data/*` replacing a
    named path) passes the whole suite while every scratch file under
    the tree silently becomes `git status`-visible and `git add`-able in
    the refresh's scratch clone, where the commit step stages whatever
    differs.
    """

    def test_synthetic_scratch_paths_stay_denied(self):
        for path in DENY_PROBE_PATHS:
            with self.subTest(path=path):
                verdict = check_ignore(["-q"], path)
                # 0 = denied by the rules (the promise under test), 1 =
                # trackable; anything else is a git error, named rather
                # than read as a verdict.
                self.assertIn(
                    verdict.returncode, (0, 1),
                    f"git check-ignore -q errored on {path}: "
                    f"{verdict.stderr.decode('utf-8', 'replace')}")
                if verdict.returncode == 0:
                    continue
                self.fail(
                    f"{path} is git-trackable (check-ignore exit 1): the "
                    "deny-by-default shape of its ignore block is broken "
                    "-- an edit stopped denying new paths under the tree "
                    "(the verbose form names nothing here, because no "
                    "rule matches any more)")
