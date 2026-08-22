import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import diff_aa  # noqa: E402  # pylint: disable=wrong-import-position

# A report in the exact shape diff_aa.report() prints, trimmed to one entry per
# section. The renderer reads this back rather than re-running the analysis, so
# the shape is the contract and this fixture is what pins it.
REPORT = """old: git:HEAD  (610 models)
new: data/aa-raw-models.json  (616 models)

== models added: 6
  + Grok 4.6 (xhigh)  [SpaceXAI]  II 60.0  cost/task $1.04
== models removed: 0

== field changes

  Claude Opus 5 (Adaptive Reasoning, Max Effort)  [Anthropic]
    mlcrOverall: — -> 0.555556

== rendered speed re-sampled by more than 25%: 769 value(s), 471 model(s)
  Muse Spark 1.2 (xhigh)  [Meta]  medianOutputTokensPerSecond: 40 -> 90
  Motif 3  [Motif Technologies]  medianOutputTokensPerSecond: 30 -> 80

== efficient frontier (expanded): 16 -> 17 of 136 -> 142 plotted
  + Grok 4.6 (xhigh)  II 60.0  $1.04/task

== coding frontier: 11 -> 11 of 136 -> 142 plotted
  (unchanged)

discarded: 7199 re-sampled speed/latency values the page never renders
"""


class CommitMessageTests(unittest.TestCase):
    def test_subject_names_what_moved(self):
        subject = diff_aa.as_commit_message(REPORT).splitlines()[0]

        self.assertEqual(
            subject,
            "Refresh capture: 616 models, +6/-0 models, frontier 16 -> 17")

    def test_subject_says_so_when_nothing_material_moved(self):
        quiet = REPORT.replace("== models added: 6", "== models added: 0") \
                      .replace("16 -> 17 of 136 -> 142", "17 -> 17 of 142 -> 142")

        self.assertEqual(diff_aa.as_commit_message(quiet).splitlines()[0],
                         "Refresh capture: 616 models, no material change")

    def test_drops_the_jitter_section_and_keeps_the_significant_one(self):
        body = diff_aa.as_commit_message(REPORT)

        # Jitter is re-measured every crawl and would bury everything else.
        self.assertNotIn("rendered speed re-sampled", body)
        self.assertNotIn("Muse Spark", body)
        # The significant move, the new model and every frontier survive.
        self.assertIn("mlcrOverall: — -> 0.555556", body)
        self.assertIn("+ Grok 4.6 (xhigh)  [SpaceXAI]", body)
        self.assertIn("== efficient frontier (expanded): 16 -> 17", body)
        self.assertIn("== coding frontier", body)
        self.assertIn("discarded: 7199", body)

    def test_undefined_sentinel_is_absence_not_a_value(self):
        # AA writes JavaScript `undefined` as this string; a key that gains it
        # has not changed, it is still unset.
        self.assertEqual(diff_aa.flatten({"a": "$undefined", "b": 1}), {"b": 1})
        self.assertEqual(diff_aa.flatten({"n": {"deep": "$undefined"}}), {})


if __name__ == "__main__":
    unittest.main()
