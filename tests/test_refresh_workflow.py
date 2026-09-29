"""Structural pins on .github/workflows/refresh.yml.

The workflow publishes the live page hourly and holds contents:write, and its
safety lives in the gating BETWEEN steps: what runs only after the suite
passed, what only when the commit actually landed, what heals a stale
publish. Those contracts are invisible to the Python suite until something
parses the YAML, so this file does -- structurally, on step shape and on
substrings that name the mechanism, never on line numbers or whole-run-block
equality that any reflow would break.
"""
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "refresh.yml"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(wf, name):
    matches = [s for s in wf["jobs"]["refresh"]["steps"]
               if s.get("name") == name]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one step named {name!r}, found {len(matches)}")
    return matches[0]


def flattened(text):
    """A run block with whitespace runs collapsed, so a pin survives
    reflowing but a dropped command or gate word does not."""
    return " ".join(text.split())


def commands(text):
    """The flattened run block minus its comment lines, so a pin on what
    EXECUTES cannot be satisfied by -- or tripped by -- the prose."""
    return flattened("\n".join(line for line in text.splitlines()
                               if not line.lstrip().startswith("#")))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.wf = load()

    def test_publish_requires_proceed_and_the_commit_steps_publish_output(self):
        # A commit step can finish green WITHOUT a publishable state (a lost
        # push race concedes with exit 0), so the publish step must read the
        # commit step's own verdict, not just the capture gate.
        gate = step(self.wf, "Publish to docs-hub")["if"]

        self.assertIn("steps.capture.outputs.proceed == 'true'", gate)
        self.assertIn("steps.commit.outputs.publish == 'true'", gate)

    def test_rebuild_and_suite_stay_gated_on_proceed(self):
        # The uniform guarantee: nothing is rebuilt or published that the
        # suite did not pass.
        for name, run in (("Rebuild the page", "python3 build.py"),
                          ("Run the suite against the new capture",
                           "python3 -m pytest -q -ra")):
            s = step(self.wf, name)
            self.assertEqual(s["if"],
                             "steps.capture.outputs.proceed == 'true'")
            self.assertEqual(flattened(s["run"]), run)

    def test_the_unchanged_path_checks_whether_the_live_page_is_current(self):
        # Issue 42: `changed=false` used to skip both commit and publish
        # forever, so a failed or missed publish never healed. The unchanged
        # path must now consult the `published` ref: a MISSING ref means
        # never published, a ref whose page differs from HEAD means stale --
        # either republishes.
        run = flattened(step(self.wf, "Did anything move?")["run"])

        self.assertIn("refs/heads/published", run)
        self.assertIn("origin/published HEAD -- out/frontier-models.html", run)
        self.assertIn("--depth=1", run)

    def test_the_publish_step_updates_the_published_ref_after_a_successful_publish(self):
        # The ref records the last successfully published state, so the heal
        # check has something to compare against. It must move only after
        # publish_docs.py succeeded, in the same step -- the first refs-API
        # command is the GET probe that decides create-vs-update.
        run = flattened(step(self.wf, "Publish to docs-hub")["run"])

        self.assertLess(
            run.index("publish_docs.py"),
            run.index('gh api "repos/$REPO/git/refs/heads/published"'))

    def test_the_published_ref_moves_through_the_refs_api(self):
        # Issue 77: the checkout is shallow (actions/checkout's default
        # depth-1), so a local `git push` cannot walk enough ancestry to
        # prove the ref update is a fast-forward and was rejected "(fetch
        # first)" on every publishing run -- even though it was one. The
        # refs API runs the check server-side, where the full graph lives:
        # a 404 on GET means CREATE (POST needs no fast-forward proof),
        # otherwise PATCH, whose default non-forced update IS GitHub's
        # fast-forward check. The step must document that a non-forced
        # PATCH is the point, so a future reader does not "fix" the 422 by
        # adding force.
        raw = step(self.wf, "Publish to docs-hub")["run"]
        run = flattened(raw)

        # The GET probe decides create-vs-update.
        self.assertIn('gh api "repos/$REPO/git/refs/heads/published"', run)
        self.assertIn("--method PATCH", run)
        self.assertIn("--method POST", run)
        self.assertIn("-f sha=", run)
        # The non-forced fast-forward semantics are documented in the step,
        # not incidental -- and no executed call carries a `force` field at
        # all (the API default is the check).
        self.assertIn("without `force`", run)
        self.assertNotIn("force", commands(raw))

    def test_no_git_push_touches_the_published_ref(self):
        # Issue 77: the git push behind the ref update was rejected
        # "(fetch first)" on every publishing run while the upload itself
        # succeeded, so the run went red and the ref stayed stale. The refs
        # API owns this ref now: no step may git-push to it. (The heal
        # gate's `git fetch` of the same ref only reads it; the prose may
        # still name the retired mechanism.)
        for s in self.wf["jobs"]["refresh"]["steps"]:
            raw = s.get("run", "")
            if "refs/heads/published" in flattened(raw):
                self.assertNotIn("git push", commands(raw))

    def test_the_commit_step_carries_an_explicit_publish_verdict(self):
        # Issue 42: the byte-identical early exit commits nothing but must
        # still publish; issue 46 adds a concede path that must publish
        # nothing. Both are the commit step's own verdict, so the step holds
        # the id the publish gate reads and sets the output on every path.
        s = step(self.wf, "Commit the capture")

        self.assertEqual(s["id"], "commit")
        self.assertIn('echo "publish=true"', flattened(s["run"]))

    def test_the_commit_step_concedes_a_lost_push_race_instead_of_dying_red(self):
        # Issue 46: two same-group runs raced the push to main and the loser
        # died red on a non-fast-forward rejection. The loser must fetch the
        # moved main, rebase, and either push again or concede -- green, with
        # publish=false, because the concurrent run's capture stands and
        # publishing it is that run's job.
        run = flattened(step(self.wf, "Commit the capture")["run"])

        self.assertIn("git fetch --depth=1 origin main", run)
        self.assertIn("git rebase origin/main", run)
        # A conflict is the concurrent capture arriving first; the loser
        # aborts, says so in the summary, and exits 0 without publishing.
        self.assertIn("git rebase --abort", run)
        self.assertLess(run.index("git rebase --abort"),
                        run.index('echo "publish=false"'))
        self.assertIn("lost the race", run.lower())
        self.assertLess(run.rindex('echo "publish=false"'),
                        run.rindex("exit 0"))
        # Exactly two push attempts: the original and the post-rebase retry,
        # which is the final one -- a second rejection fails the run red
        # rather than looping.
        self.assertEqual(run.count("HEAD:main"), 2)

    def test_the_fetch_runs_above_the_installs_which_gate_on_proceed(self):
        # Issue 59: pip + Chromium install burned 40-50 s on the large
        # majority of runs whose capture is unchanged. fetch_aa.py is pure
        # stdlib (it imports build.py, which is too), so it captures first,
        # above the installs; the installs gate on `proceed` -- not
        # `changed` -- so a heal run still installs the toolchain the suite
        # runs under.
        names = [s.get("name") for s in self.wf["jobs"]["refresh"]["steps"]]

        self.assertLess(names.index("Capture the leaderboard"),
                        names.index("Install the test toolchain"))
        self.assertLess(names.index("Capture the leaderboard"),
                        names.index("Install Chromium for playwright"))
        for name in ("Install the test toolchain",
                     "Install Chromium for playwright"):
            self.assertEqual(
                step(self.wf, name)["if"],
                "steps.capture.outputs.proceed == 'true'")

        setup = [s for s in self.wf["jobs"]["refresh"]["steps"]
                 if s.get("uses", "").startswith("actions/setup-python@")]
        self.assertEqual(len(setup), 1)
        # setup-python stays unconditional: it is cheap, and fetch_aa.py
        # runs on it.
        self.assertNotIn("if", setup[0])
