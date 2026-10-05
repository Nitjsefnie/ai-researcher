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
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parent.parent

GIT_TIMEOUT = 60  # seconds; git check-ignore is local and fast


def added_paths():
    """Every path the refresh's commit step `git add`s, parsed out of
    .github/workflows/refresh.yml -- never a hand-copied twin."""
    workflow = yaml.safe_load(
        (HERE / ".github/workflows/refresh.yml").read_text(encoding="utf-8"))
    steps = [s for s in workflow["jobs"]["publish"]["steps"]
             if s.get("name") == "Commit the capture"]
    assert len(steps) == 1, (
        "expected exactly one 'Commit the capture' step in the publish "
        f"job, found {len(steps)}")
    # Join backslash continuations first, so an add split across lines
    # is read whole.
    joined = []
    for line in steps[0]["run"].splitlines():
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


# Synthetic probe paths: no real artifact would ever carry them. Every
# committed name under data/ is `aa-*` or `captured-at.txt`, and out/
# ships exactly one file, so a future LEGITIMATE negation -- which names
# a new committed path exactly (`!/data/aa-new-thing.json`) -- cannot
# match a synthetic name and cannot turn these probes falsely red. Any
# edit broad enough to un-deny a probe flips the verdict -- a wholesale
# `!/data/*` (the issue's own repro) or a class-scoped `!/data/*.json`
# alike -- and every such edit is exactly the rot this pin exists to
# catch, because each of them un-denies scratch files along with it.
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
