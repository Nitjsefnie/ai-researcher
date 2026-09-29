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
        # publish_docs.py succeeded, in the same step.
        run = flattened(step(self.wf, "Publish to docs-hub")["run"])

        self.assertLess(run.index("publish_docs.py"), run.index("git push"))
        self.assertIn("refs/heads/published", run)

    def test_the_commit_step_carries_an_explicit_publish_verdict(self):
        # Issue 42: the byte-identical early exit commits nothing but must
        # still publish; issue 46 adds a concede path that must publish
        # nothing. Both are the commit step's own verdict, so the step holds
        # the id the publish gate reads and sets the output on every path.
        s = step(self.wf, "Commit the capture")

        self.assertEqual(s["id"], "commit")
        self.assertIn('echo "publish=true"', flattened(s["run"]))
