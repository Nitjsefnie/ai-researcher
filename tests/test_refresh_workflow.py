"""Structural pins on .github/workflows/refresh.yml.

The workflow publishes the live page hourly, and since issues #143 and #133
its write side is three jobs in a fixed order: `refresh` (capture, rendered
gate, rebuild, suite) runs on a read-only token and leaves the commit
payload as an artifact of its own run; `publish` -- a keyless committer --
downloads that artifact and replays the hour's commits into a git bundle
while running no repository code; `push` -- the AA job that loads the
deploy key, in the main-push environment -- delivers the bundle to main;
`hub` -- read-only since issue #206 -- uploads the verified page when the
live page's embedded source-commit stamp shows the hub behind.
Its safety lives in the gating BETWEEN steps and BETWEEN jobs: what runs only
after the suite passed, what only when the commit actually landed, what
republishes a stale live page. Those contracts are invisible to the Python
suite until something parses the YAML, so this file does -- structurally, on
step shape and on substrings that name the mechanism, never on line numbers
or whole-run-block equality that any reflow would break.

There is NO route-disagreement state (issue #200): AA's two routes are
independently cached, the leaderboard is the authority and the detail route
fills shared-model gaps and adds detail-only models, so the workflow has one capture exit colour and one
commit message for a moved capture. The pins below cover the recovery and the
re-raise the Capture step keeps, not a dispute branch.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _workflowrun  # noqa: E402  # pylint: disable=wrong-import-position

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "refresh.yml"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step_in(wf, job, name):
    matches = [s for s in wf["jobs"][job]["steps"]
               if s.get("name") == name]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one step named {name!r} in job {job!r}, "
            f"found {len(matches)}")
    return matches[0]


def step(wf, name):
    return step_in(wf, "refresh", name)


def pub_step(wf, name):
    return step_in(wf, "publish", name)


def hub_step(wf, name):
    return step_in(wf, "hub", name)


def flattened(text):
    """A run block with whitespace runs collapsed, so a pin survives
    reflowing but a dropped command or gate word does not."""
    return " ".join(text.split())


def commands(text):
    """The flattened run block minus its comment lines, so a pin on what
    EXECUTES cannot be satisfied by -- or tripped by -- the prose."""
    return flattened("\n".join(line for line in text.splitlines()
                               if not line.lstrip().startswith("#")))


class GateTests(unittest.TestCase):  # pylint: disable=too-many-public-methods
    # The disable mirrors tests/test_browser.py:69: this class pins one
    # workflow's step/job contracts, and splitting it would hide that.
    def setUp(self):
        self.wf = load()

    def test_workflow_permissions_floor_and_job_read_scope(self):
        # Issue #52 fold, narrowed by #143: the workflow-level floor is
        # contents: read, so a job added later without its own permissions
        # block inherits read instead of the repository default. The refresh
        # job DECLARES read: it runs the capture, third-party installs and
        # the suite, so nothing in it may ride a write token.
        self.assertEqual(self.wf.get("permissions"), {"contents": "read"})
        self.assertEqual(self.wf["jobs"]["refresh"]["permissions"],
                         {"contents": "read"})

    def test_no_job_holds_contents_write(self):
        # Issues #143 and #133, narrowed by #206: the workflow floor and
        # every job declare contents: read. The publish, push and hub jobs
        # remain present; push depends on publish and runs in main-push.
        # Check the publish job's explicit read permission alongside the
        # catalogue-wide declarations and the push job's delivery wiring.
        workflow = self.wf
        self.assertEqual(workflow.get("permissions"), {"contents": "read"})
        jobs = workflow["jobs"]
        for name in ("publish", "push", "hub"):
            assert name in jobs, f"the {name} job is missing from refresh.yml"
        for name, job in jobs.items():
            assert (job.get("permissions") or {}).get("contents") == "read", (
                f"{name} must declare contents: read")
        push = jobs["push"]
        assert push["needs"] == "publish", (
            "the bundle is this run's own data: needs, not a workflow_run")
        assert push.get("environment") == "main-push", (
            "the deploy key is reachable only through the main-push "
            "environment")
        assert (jobs["publish"].get("permissions") or {}).get(
            "contents") == "read", (
            "the committer is keyless and read-only: it pushes nothing")

    def test_the_publish_job_is_gated_on_the_refresh_jobs_success_and_proceed(self):
        # A red capture or a red suite leaves needs.refresh.result != success
        # and the writer never starts; a quiet hour leaves proceed unset and
        # the writer never starts either. Nothing reaches main or the hub
        # that the refresh job did not verify.
        cond = self.wf["jobs"]["publish"]["if"]

        self.assertIn("needs.refresh.result == 'success'", cond)
        self.assertIn("needs.refresh.outputs.proceed == 'true'", cond)

    def test_the_refresh_job_exports_proceed(self):
        # The writer's gate reads proceed through the job output; the step
        # output must be wired to it.
        outputs = self.wf["jobs"]["refresh"]["outputs"]

        self.assertEqual(outputs["proceed"],
                         "${{ steps.capture.outputs.proceed }}")

    def test_the_payload_travels_as_this_runs_own_artifact(self):
        # The upload and download agree on the artifact name, and the
        # download precedes the commit in the publish job.
        # Issue #283: the producer and consumer define the transport's
        # shared identifier, so each supplies the other's expected value.
        # A rename applied to both remains valid; a one-sided edit would
        # leave the committer waiting for a differently named payload.
        # The ordering check addresses a separate dependency: the commit
        # needs its downloaded files before it starts. Neither assertion
        # establishes the payload's contents or upload failure policy;
        # those properties cannot be inferred from matching identifiers.
        up = step(self.wf, "Upload the publish payload")
        down = pub_step(self.wf, "Download the publish payload")

        self.assertEqual(up["with"]["name"], down["with"]["name"])
        names = [s.get("name") for s in self.wf["jobs"]["publish"]["steps"]]
        self.assertLess(names.index("Download the publish payload"),
                        names.index("Commit the capture"))

    def test_the_upload_is_gated_on_success_and_proceed(self):
        # An explicit step `if` REPLACES the implicit success() gate, so the
        # upload must re-state it: a red suite must not hand a payload to
        # the writer even before the job-level needs check runs.
        up = step(self.wf, "Upload the publish payload")

        self.assertIn("success()", up["if"])
        self.assertIn("steps.capture.outputs.proceed == 'true'", up["if"])

    def test_publish_requires_proceed_and_the_commit_steps_publish_output(self):
        # A commit step can finish green WITHOUT a publishable state (a lost
        # push race concedes with exit 0), so the publish step must read the
        # commit step's own verdict. Proceed is the writer JOB's gate; the
        # verdict is the publish STEP's gate inside it.
        cond = self.wf["jobs"]["hub"]["if"]
        gate = self.wf["jobs"]["publish"]["if"]

        self.assertIn("needs.refresh.outputs.proceed == 'true'", gate)
        self.assertIn("needs.publish.outputs.publish == 'true'", cond)

    def test_the_publish_job_runs_no_repository_code(self):
        # The writer runs no checkout, no third-party install, no test
        # suite, and no script from the tree: its only inputs are the
        # artifact, git plumbing, and curl/jq/gh against the pinned hub
        # host. Anything executed here would ride the write token.
        banned = re.compile(r"\bpython3\b|\bpip[0-9]?\b")
        for job in ("publish", "push", "hub"):
            for s in self.wf["jobs"][job]["steps"]:
                run = s.get("run", "")
                self.assertIsNone(banned.search(commands(run)),
                                  commands(run))

    def test_the_suite_step_rebuilds_the_page_stamped_too(self):
        # Issue #92: the suite's browser tests used to call build.main() over
        # the REAL out/frontier-models.html, and that rebuild used to run with
        # AA_SOURCE_COMMIT unset -- so the commit step staged an unstamped
        # page and the Rebuild step's stamp was thrown away. The suite step
        # must carry the same env the Rebuild step has: since #114 the suite
        # builds into temp dirs and no longer rewrites the working page, so
        # the env is belt-and-suspenders, but the equality stays pinned.
        suite = step(self.wf, "Run the suite against the new capture")
        rebuild = step(self.wf, "Rebuild the page")

        self.assertEqual(suite["env"]["AA_SOURCE_COMMIT"],
                         rebuild["env"]["AA_SOURCE_COMMIT"])
        self.assertEqual(suite["env"]["AA_SOURCE_COMMIT"], "${{ github.sha }}")

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

    def test_the_gate_compares_the_rendered_page_not_the_raw_capture_bytes(self):
        # Issue #94: the raw-byte comparison (`git diff --quiet -- data/...`)
        # answered "did the bytes move", and AA's payload churns hourly in
        # fields the page never renders -- 23 of 30 refresh commits carried
        # "nothing the page renders". The gate step must invoke the rendered
        # gate, which builds the page from HEAD's captures and from the fresh
        # ones and compares with provenance normalized out; its single word
        # of stdout is the step output everything downstream reads.
        s = step(self.wf, "Did anything move?")
        raw = s["run"]
        run = flattened(raw)

        self.assertIn('changed="$(python3 scripts/capture_gate.py)"', run)
        self.assertIn('echo "changed=$changed" >> "$GITHUB_OUTPUT"', run)
        # No raw-VCS view of data/ may leak back into this step, whatever
        # the spelling: any `git diff` or `git status` here must not name
        # data/. The republish gate compares pages too, but through the
        # hub's live bytes, not a git diff (issue #206).
        joined = raw.replace("\\\n", " ")
        for line in joined.splitlines():
            if line.lstrip().startswith("#"):
                continue
            if "git diff" in line or "git status" in line:
                self.assertNotIn("data/", line, line.strip())

    def test_the_unchanged_path_drops_the_whole_data_directory(self):
        # Issue #94: captures the gate found rendered-equivalent must not sit
        # in the tree -- the staging step would otherwise ship them toward a
        # later commit. The restore widens from the stamp file to
        # the directory, which also restores captured-at.txt: the stamp still
        # moves only when the data moved, and a quiet fetch still leaves the
        # tree clean.
        run = flattened(step(self.wf, "Did anything move?")["run"])

        self.assertIn("git checkout -- data/", run)
        self.assertNotIn("git checkout -- data/captured-at.txt", run)
        # The restore stands on the unchanged path: after the gate's answer,
        # before the republish gate's live-page fetch.
        self.assertLess(run.index("git checkout -- data/"),
                        run.index("docs.nitjsefni.eu/d/ai-researcher"))

    def test_the_payload_staging_restores_heads_page_when_the_capture_did_not_move(self):
        # Issue #94, second half: on a republish run the suite's rebuild is now
        # stamped with THIS run's github.sha (issue #92's env fix), while
        # HEAD's committed page carries the previous tip's sha -- the commit
        # a page lands in always postdates the stamp it carries -- so
        # committing the rebuilt page would be stamp-only churn. The guard
        # moved from the old commit step into the staging step, which must
        # restore HEAD's page before anything ships whenever the capture did
        # not change and the run is not forced; a forced run may commit
        # stamp churn, accepted because force is manual and rare.
        s = step(self.wf, "Stage the publish payload")
        run = flattened(s["run"])

        self.assertEqual(s["env"]["CHANGED"],
                         "${{ steps.capture.outputs.changed }}")
        self.assertEqual(s["env"]["FORCE"], "${{ inputs.force }}")
        self.assertIn(
            'if [ "$CHANGED" != "true" ] && [ "$FORCE" != "true" ]; then', run)
        self.assertIn(
            "git show HEAD:out/frontier-models.html > out/frontier-models.html",
            run)
        self.assertLess(
            run.index("git show HEAD:out/frontier-models.html"),
            run.index("cp --parents"))

    def test_the_staging_step_ships_the_commit_payload(self):
        # The artifact is the exact commit payload the old single job staged:
        # the fixed add list and the differ's message when one ran. The
        # disagreement-era files are gone with the disagreement state (issue
        # #200), so the list is the five payload paths, the window marker
        # behind its own presence guard (issue #227), and nothing that
        # varies by hour.
        run = flattened(step(self.wf, "Stage the publish payload")["run"])

        for piece in ("data/aa-raw-models.json",
                      "data/aa-raw-coding-agents.json",
                      "data/aa-generation-state.json",
                      "data/captured-at.txt",
                      "out/frontier-models.html",
                      "data/cost-breakdown-window.txt",
                      "commit-msg.txt"):
            self.assertIn(piece, run)
        # The marker copies only when this hour actually recorded one.
        self.assertIn(
            "[ ! -f data/cost-breakdown-window.txt ] || "
            "cp --parents data/cost-breakdown-window.txt", run)
        # No disagreement-era file and no retirement switch survives on this
        # path; the window marker is the one conditional payload file, and
        # the guard above is its whole conditional.
        for gone in ("data/aa-disagreement-snapshot.json",
                     "data/aa-route-disagreement.txt",
                     "data/aa-last-agreeing-capture.json",
                     "$RETIRE"):
            self.assertNotIn(gone, run)

    def test_capture_artifact_upload_requires_failure_and_successful_capture(self):
        artifact = step(self.wf, "Upload the capture on failure")
        self.assertIn("failure()", artifact["if"])
        self.assertIn("steps.fetch.outputs.captured == 'true'", artifact["if"])

    def test_the_write_job_stages_the_window_marker_both_ways(self):
        # Issue #227: the gate's HEAD-side rebuild reads the window marker
        # from GIT at HEAD, so a window hour's commit must carry it and the
        # first healthy hour's commit must remove it. The add keys on the
        # PAYLOAD, never on the worktree file -- the scratch checkout at
        # main's tip materializes a tracked marker into the tree and
        # `cp -a` never deletes, so a worktree probe would fire the add on
        # exactly the heal hour and the marker would never leave main (the
        # reviewer-reproduced defect this condition fixes). The removal is
        # the elif's `git rm`. Neither branch fires in a normal hour.
        run = flattened(step_in(self.wf, "publish",
                                "Commit the capture")["run"])

        self.assertIn(
            'if [ -f "${PAYLOAD}/tree/data/cost-breakdown-window.txt" ]; then',
            run)
        self.assertIn("git add data/cost-breakdown-window.txt", run)
        self.assertIn(
            "git cat-file -e HEAD:data/cost-breakdown-window.txt", run)
        self.assertIn("git rm -q data/cost-breakdown-window.txt", run)
        # Presence stages before absence is considered, and the rm is the
        # elif -- never an unconditional removal.
        self.assertLess(
            run.index("git add data/cost-breakdown-window.txt"),
            run.index("git rm -q data/cost-breakdown-window.txt"))

    def test_the_unchanged_path_checks_whether_the_live_page_is_current(self):
        # Issue 42 taught the unchanged path to check; issue #206 changed
        # what it consults: the hub's live page IS the publish record --
        # the page HTML embeds its source-commit stamp, so the served
        # bytes are their own memory. A page behind HEAD (a failed or
        # missed publish, an unstamped page) and a failed fetch both
        # republish; the branch that used to be fetched is gone.
        raw = step(self.wf, "Did anything move?")["run"]
        run = flattened(raw)

        self.assertIn("docs.nitjsefni.eu/d/ai-researcher/frontier-models", run)
        self.assertIn('cmp -s - "$hub_page" || hub_stale=true', run)
        self.assertNotIn("refs/heads/published", run)
        self.assertNotIn("origin/published", run)

    def test_an_off_main_dispatch_drops_the_hour_before_anything_expensive(self):
        # PR #205's conceded-run ledger, closed explicitly: workflow_dispatch
        # can target any branch, and the write half's generation tie would
        # concede an off-main dispatch anyway -- but only after a full
        # capture + pip + Chromium + suite had been paid, and under "main
        # moved under the run" wording that blames main for a move that
        # never happened. The capture step's FIRST act reads the run's ref
        # (env-mapped, the zizmor convention) and drops the hour green,
        # before the gate, under its own truthful heading. Scheduled runs
        # always fire on the default branch, so the check is exactly
        # "not refs/heads/main".
        s = step(self.wf, "Did anything move?")
        raw = s["run"]
        run = flattened(raw)

        self.assertEqual(s["env"]["REF"], "${{ github.ref }}")
        idx_gate = run.index('if [ "$REF" != "refs/heads/main" ]; then')
        # The off-main gate runs FIRST: before the rendered gate and before
        # any check that could be mislabeled as a main move.
        self.assertLess(idx_gate,
                        run.index('changed="$(python3 scripts/capture_gate.py)"'))
        self.assertIn("Dropped: dispatched off main", run)
        self.assertIn("a payload built", run)
        # The drop is green and total: proceed=false is written and the
        # branch exits before the gate's own restore runs.
        self.assertIn('echo "proceed=false" >> "$GITHUB_OUTPUT"', run)
        idx_exit = run.index("exit 0", idx_gate)
        self.assertLess(idx_exit, run.index("git checkout -- data/"))

    def test_the_publish_step_reads_the_live_page_before_the_upload(self):
        # Issue #206: the step decides whether to upload at all by reading
        # the hub's live page -- its embedded source-commit stamp and its
        # bytes -- BEFORE the upload call. The refs-API GET that used to
        # precede the upload is gone with the ref; the upload's own curl
        # keeps its status-captured form, branched on explicitly.
        run = flattened(hub_step(self.wf, "Publish to docs-hub")["run"])

        self.assertLess(
            run.index("https://docs.nitjsefni.eu/d/ai-researcher/frontier-models"),
            run.index("curl -sS"))
        self.assertLess(
            run.index("curl -sS"), run.index("cat /tmp/publish-response.json"))
        self.assertIn("Source commit <code>", run)

    def test_no_refs_api_call_remains(self):
        # Issue #206: the published ref and its refs-API move are retired --
        # the live page's embedded stamp is the publish record. No step in
        # any job calls the refs API, names the branch, or maps the job
        # token: nothing in this workflow writes to GitHub.
        for job_name, job in self.wf["jobs"].items():
            for s in job["steps"]:
                run = flattened(s.get("run", ""))
                self.assertNotIn("git/refs/", run, job_name)
                self.assertNotIn("refs/heads/published", run, job_name)
                self.assertNotIn("gh api", run, job_name)
                self.assertNotIn("GH_TOKEN", s.get("env", {}), job_name)

    def test_the_publish_step_skips_when_the_hub_already_serves_the_page(self):
        # Issue 74's newest-run-wins guarantee keeps its replacement: the
        # tie owns ordering (a newer run has necessarily landed before it
        # can publish), and the live-page gate owns the version spend.
        # The step fetches the live page, extracts its stamp, and when the
        # hub already serves EXACTLY this run's page -- stamp and every
        # byte -- leaves green through exit 0 BEFORE the upload. A failed
        # fetch publishes: availability beats the seconds-wide window, the
        # same stance the ref gates it replaced held.
        run = flattened(hub_step(self.wf, "Publish to docs-hub")["run"])

        idx_fetch = run.index(
            "https://docs.nitjsefni.eu/d/ai-researcher/frontier-models")
        idx_stamp = run.index("Source commit <code>")
        idx_cmp = run.index('cmp -s "$live_page"')
        idx_skip = run.index("nothing uploaded", idx_cmp)
        idx_exit = run.index("exit 0", idx_skip)
        idx_upload = run.index("https://docs.nitjsefni.eu/api/publish")
        self.assertLess(idx_fetch, idx_stamp)
        self.assertLess(idx_stamp, idx_cmp)
        self.assertLess(idx_cmp, idx_skip)
        self.assertLess(idx_exit, idx_upload)
        # The skip names the served page's own stamp in its summary line.
        self.assertIn("The hub already serves this run's page", run)
        self.assertIn("(source commit ${live_stamp})", run)

    def test_the_unchanged_path_checks_the_hubs_live_page(self):
        # Issue 74's hub check is now the ONLY republish check (issue #206):
        # on the unchanged path the gate fetches the hub's live page (the
        # public /d/ route serves the stored bytes verbatim, proven
        # byte-identical to the committed page (2026-09-29)) and compares
        # it byte-for-byte against HEAD's page -- the embedded stamp is one
        # of those bytes. Divergence sets hub_stale, as does a failed
        # fetch: republishing a page that was already current costs one
        # hub version, while a real outage fails red at the write job's
        # publish step.
        run = flattened(step(self.wf, "Did anything move?")["run"])

        # The check stands on the unchanged path and feeds the proceed
        # decision.
        self.assertLess(run.index('[ "$changed" = false ]'),
                        run.index("docs.nitjsefni.eu/d/ai-researcher"))
        self.assertIn("git show HEAD:out/frontier-models.html", run)
        self.assertIn('cmp -s - "$hub_page" || hub_stale=true', run)
        self.assertIn("else hub_stale=true", run)
        self.assertIn('[ "$hub_stale" = true ]', run)
        # Each divergence cause gets its own truthful summary line (issue
        # #239): the fetched page differing from HEAD, and the live-page
        # fetch failing -- a failed fetch compared no page, so the run
        # must not report a comparison result.
        self.assertIn("differs from HEAD", run)
        self.assertIn("live-page fetch failed", run)

    def test_the_commit_step_carries_an_explicit_publish_verdict(self):
        # Issue 42: the byte-identical early exit commits nothing but must
        # still publish; issue 46 adds a concede path that must publish
        # nothing. Both are the commit step's own verdict, so the step holds
        # the id the publish gate reads and sets the output on every path.
        s = pub_step(self.wf, "Commit the capture")

        self.assertEqual(s["id"], "commit")
        self.assertIn('echo "publish=true"', flattened(s["run"]))
        self.assertIn('echo "commits=true"', flattened(s["run"]))
        self.assertIn('echo "commits=false"', flattened(s["run"]))

    def test_every_message_branch_writes_the_file_the_commit_reads(self):
        # Review C1/I3 on PR #151: the differ branch appended its trailer to
        # the payload copy while `git commit -F` read the RUNNER_TEMP file --
        # nothing wrote it on an ordinary moved-capture hour, and the
        # workflow's primary publishing path died at the commit, exit 128,
        # with every structural pin green. The pin follows the dataflow: both
        # branches leave the commit's file written, no branch mutates the
        # payload copy, and the commit reads exactly that path.
        run = flattened(pub_step(self.wf, "Commit the capture")["run"])
        msg = '"${RUNNER_TEMP}/commit-msg.txt"'

        # The differ branch routes the payload message into it before the
        # trailer append...
        idx_differ = run.index('if [ -f "${PAYLOAD}/commit-msg.txt" ]; then')
        idx_cat = run.index(
            'cat "${PAYLOAD}/commit-msg.txt" > "${RUNNER_TEMP}/commit-msg.txt"',
            idx_differ)
        idx_append = run.index("> " + msg, idx_cat)
        self.assertLess(idx_cat, idx_append)
        # ...and the forced branch writes it outright.
        idx_forced = run.index("Rebuild the page: forced run")
        self.assertLess(idx_forced, run.index(f"> {msg}", idx_forced))
        # No branch mutates the payload copy, and the commit consumes the
        # one file every branch wrote.
        self.assertNotIn('>> "${PAYLOAD}/commit-msg.txt"', run)
        self.assertLess(run.index(f"> {msg}"),
                        run.index("git commit -F " + msg))

    def test_the_commit_step_performs_no_push(self):
        # Issue #133: the commit step is the keyless committer -- it stages
        # the verified commits as a bundle and pushes nothing. Every main
        # push in the workflow lives in the push job, behind the deploy key.
        run = flattened(pub_step(self.wf, "Commit the capture")["run"])

        self.assertNotIn("git push", run)
        self.assertNotIn("HEAD:main", run)
        # The bundle is staged with the base and tip the push job checks.
        self.assertIn("git bundle create", run)
        self.assertIn("FETCH_HEAD..push", run)
        self.assertIn("base.txt", run)
        self.assertIn("tip.txt", run)

    def test_the_push_job_concedes_a_lost_push_race(self):
        # Issue 46's race contract, re-homed with the push: a rejected push
        # distinguishes "main stood still" (a real error, red) from "main
        # moved before the push landed" (dropped green; the next hourly run
        # re-fetches, re-tests and lands it). Exactly two attempts: the
        # original and the post-fetch verdict, which is the final one --
        # nothing loops.
        run = flattened(
            step_in(self.wf, "push", "Push the tested tree to main")["run"])

        # Exactly one guarded push attempt: a rejection is classified once
        # (stood still vs main moved) and never loops.
        self.assertEqual(run.count("refs/heads/main"), 2)
        self.assertIn("moved under the run", run)
        self.assertIn("moved before the push landed", run)
        self.assertIn("rejected while main stood still", run)
        # The stood-still verdict compares the TESTED BASE, not tip^: the
        # bundle carries the hour's own commits on top of that base, so
        # tip^ is not necessarily the commit the run was tested against.
        self.assertIn('base.txt")" =', run)

    def test_the_fetch_runs_above_the_installs_which_gate_on_proceed(self):
        # Issue 59: pip + Chromium install burned 40-50 s on the large
        # majority of runs whose capture is unchanged. fetch_aa.py is pure
        # stdlib (it imports build.py, which is too), so it captures first,
        # above the installs; the installs gate on `proceed` -- not
        # `changed` -- so a republish run still installs the toolchain the
        # suite runs under.
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

        # Issue #51: a revert to the bare `playwright install` unwires the digest gate.
        self.assertEqual(
            flattened(step(self.wf, "Install Chromium for playwright")["run"]),
            "python3 scripts/ci/install_chromium.py")

        setup = [s for s in self.wf["jobs"]["refresh"]["steps"]
                 if s.get("uses", "").startswith("actions/setup-python@")]
        # setup-python stays unconditional: it is cheap, and fetch_aa.py
        # runs on it.
        for entry in setup:
            self.assertNotIn("if", entry)

    def test_the_hub_ties_the_upload_to_one_commit(self):
        # The tie is ENFORCED, not asserted: the upload runs only when the
        # payload page's own commit (`tip`, recorded by the publish job) is
        # still main's tip. When main has moved past it, a newer run owns
        # the tip and its hub job publishes - this run concedes green
        # before anything is uploaded. The tie is also what lets the
        # ref's compare-API gate retire (issue #206): a newer run has
        # necessarily landed before it can publish anything this run could
        # overwrite.
        run = flattened(hub_step(self.wf, "Publish to docs-hub")["run"])

        idx_target = run.index('target="$(git -C "${scratch}" rev-parse FETCH_HEAD)"')
        idx_mine = run.index('mine="$(cat "${RUNNER_TEMP}/push-data/tip.txt")"')
        # The target is fetched before the tip is read: the tie compares a
        # fresh main against the page's own commit.
        self.assertLess(idx_target, idx_mine)
        idx_tie = run.index('[ "$mine" != "$target" ]; then')
        idx_concede = run.index("Lost the race")
        # The tie's concede leaves GREEN through its own exit 0 before the
        # live-page gate: a superseded hour must neither publish nor go red.
        idx_exit = run.index("exit 0", idx_concede)
        idx_fetch = run.index(
            "https://docs.nitjsefni.eu/d/ai-researcher/frontier-models")
        idx_upload = run.index("https://docs.nitjsefni.eu/api/publish")
        self.assertLess(idx_mine, idx_tie)
        self.assertLess(idx_tie, idx_concede)
        self.assertLess(idx_concede, idx_exit)
        self.assertLess(idx_exit, idx_fetch)
        self.assertLess(idx_fetch, idx_upload)

    def test_the_upload_mirrors_publish_docs_py(self):
        # Review I2 on PR #151: the write job runs no repository code, so
        # the upload is the endpoint's wire format inlined, and the step
        # names scripts/publish_docs.py as the canonical client and mirror
        # source. Nothing else binds the two -- this pin holds the literals
        # that must drift together: the multipart part names, the key
        # header, the pinned host and endpoint, and the hub's dual failure
        # semantics (a non-2xx, or a 2xx carrying an error field).
        raw = hub_step(self.wf, "Publish to docs-hub")["run"]
        run = flattened(raw)

        for piece in ("-F 'slug=ai-researcher/frontier-models'",
                      "-F 'title=Frontier models — intelligence vs cost per task'",
                      "-F 'tags=benchmarks,comparison,interactive,ai'",
                      "-F 'project=ai-researcher'",
                      "-F 'from=ai-researcher'",
                      "-F 'file=@out/frontier-models.html;type=text/html'",
                      'x-docs-key: ${DOCS_HUB_API_KEY}',
                      "https://docs.nitjsefni.eu/api/publish",
                      "scripts/publish_docs.py",
                      '[ "${code}" -lt 200 ] || [ "${code}" -ge 300 ]',
                      "jq -e '(.error // null) != null'"):
            self.assertIn(piece, run)

    def test_the_publish_record_lives_in_the_page_itself(self):
        # Issue #152 asked that the publish record never leave main's
        # history; issue #206 retired the ref and moved the record into the
        # page: the source-commit stamp inside the HTML names the commit
        # the page was built from, and the tie above uploads only while
        # that commit is main's tip. The pin holds the shape: the step
        # extracts the stamp from the fetched live page, names both stamps
        # in the publishing summary, and never touches a GitHub ref.
        raw = hub_step(self.wf, "Publish to docs-hub")["run"]
        run = flattened(raw)

        idx_fetch = run.index(
            "https://docs.nitjsefni.eu/d/ai-researcher/frontier-models")
        idx_extract = run.index("Source commit <code>")
        idx_publishing = run.index("Publishing: the hub serves")
        idx_upload = run.index("https://docs.nitjsefni.eu/api/publish")
        self.assertLess(idx_fetch, idx_extract)
        self.assertLess(idx_extract, idx_publishing)
        self.assertLess(idx_publishing, idx_upload)
        self.assertIn("grep -oE 'Source commit <code>[0-9a-f]{40}</code>'", run)


class ExecutedHoldProbeTests(unittest.TestCase):
    """The hold probe's hour, EXECUTED, not read (issue #236).

    The structural pins this class replaces asserted the held branch's
    shape by substring and index, on the premise that the step cannot run
    hermetically -- a premise the corpus's
    ci/run-workflow-step-scripts-dont-read-them lesson (its fifth sighting
    on this file) disposes of: the step is executable code, so the contract
    is pinned by running the real run block. python3 and curl are stubbed
    (the only tools the step reaches beyond git), the gate and the probe
    answer from fixtures, and every executed case asserts the exit code,
    the proceed output, the data/ state and -- where the case's meaning
    needs it -- the summary and the hub fetch.

    Two layers pin the failure paths. THIS class is the workflow layer:
    a gate or probe exit 1 must turn the STEP red before any verdict can
    be computed, an undefined probe token must never fall through, and the
    hold outranks the force and hub_stale arms. The probe's own exit-code
    contract at the probe layer lives in tests/test_capture_gate.py's
    FreshHoldProbeTests -- including the converged corner capture, which
    the workflow never brings to the probe (the no-argument gate refuses
    it earlier in the step); the workflow-level pin for that red is the
    forced, gate-failure case below.
    """

    HEAD_FILES = {
        "data/aa-raw-models.json": "head\n",
        "out/frontier-models.html": "page\n",
    }
    FRESH = "fresh\n"
    # The republish hour's two cause lines (issue #239), byte-equal to the
    # workflow's summary echoes: the cause that set hub_stale is named, so
    # a failed fetch never reports a comparison result it did not make.
    HUB_DIVERGED_LINE = ('AA capture unchanged, but the hub serves a page '
                         'that differs from HEAD — republishing it.')
    HUB_FETCH_FAILED_LINE = ('AA capture unchanged, but the live-page '
                             'fetch failed — republishing it.')

    def setUp(self):
        if os.name == "nt":
            # The step is a GitHub-runner bash script exercising POSIX
            # tooling (mktemp, cmp, curl, a stub PATH); the refresh job
            # itself runs on ubuntu, the same skip shape as the
            # stub-gh classifier tests.
            raise unittest.SkipTest(
                "the step is a POSIX script; the Windows cells skip its "
                "execution")

    def _run_hour(self, tmp: pathlib.Path, *, gate, probe, force, hub):
        """Seed one scratch repo at HEAD, dirty it with the fresh capture
        and the untracked window marker, install the python3/curl doubles,
        and run the real run block.

        `gate` is the no-argument capture_gate.py answer -- `true`, `false`
        or the string `rc1` for exit 1 -- and `probe` the --fresh-held
        answer: `yes`, `no`, `rc1`, or a token the step does not define.
        `hub` drives the live-page fetch double: `same` (the hub serves
        HEAD's page), `stale` (it serves a stale one) or `fail` (the fetch
        itself fails). Returns the observables: the exit code, the step
        output text, the parsed proceed, the tracked capture's content,
        whether the untracked marker survived, the summary, the log the
        step wrote and the hub fetch count.
        """
        gate_out = {"true": "true", "false": "false"}.get(gate, "")
        gate_rc = 1 if gate == "rc1" else 0
        held_out = {"yes": "yes", "no": "no", "maybe": "maybe"}.get(probe, "")
        held_rc = 1 if probe == "rc1" else 0

        repo = tmp / "repo"
        (repo / "data").mkdir(parents=True)
        (repo / "out").mkdir()
        for rel, text in self.HEAD_FILES.items():
            (repo / rel).write_text(text, encoding="utf-8")
        git = ["git", "-C", str(repo)]
        # A fixture's throwaway repo: the commit-identity rule governs OUR
        # commits, not scratch seeds (the same note the marker conditional
        # test carries).
        seed_env = {**os.environ, "GIT_AUTHOR_NAME": "seed",
                    "GIT_AUTHOR_EMAIL": "seed@example",
                    "GIT_COMMITTER_NAME": "seed",
                    "GIT_COMMITTER_EMAIL": "seed@example"}
        subprocess.run([*git, "init", "-q"], check=True, capture_output=True)
        subprocess.run([*git, "add", "."], check=True, capture_output=True)
        subprocess.run([*git, "commit", "-qm", "head"], env=seed_env,
                       check=True, capture_output=True)
        # The hour's raw material: the fresh capture, dirty against HEAD,
        # and fetch_aa.py's window marker -- untracked-but-whitelisted, so
        # `git checkout -- data/` cannot remove it. Exactly the tree state
        # a real window hour leaves.
        (repo / "data" / "aa-raw-models.json").write_text(self.FRESH,
                                                          encoding="utf-8")
        (repo / "data" / "cost-breakdown-window.txt").write_text(
            "3\n", encoding="utf-8")

        stub = tmp / "bin"
        stub.mkdir()
        (stub / "python3").write_text(STUB_PYTHON3, encoding="utf-8")
        (stub / "curl").write_text(STUB_CURL, encoding="utf-8")
        for tool in stub.iterdir():
            tool.chmod(0o755)

        step_ = _workflowrun.step_by_name(
            WORKFLOW, "refresh", "Did anything move?")
        # The workflow engine substitutes ${{ }} in run text before a
        # script exists; the harness plays that part for the expression
        # the verdict and the quiet line still read inline. The held
        # branch reads $FORCE from the step env instead.
        script = step_["run"].replace("${{ inputs.force }}",
                                      "true" if force else "")
        env = {
            "PATH": f"{stub}:{os.environ['PATH']}",
            "HOME": str(tmp),
            "CAPTURED": "true",
            "REF": "refs/heads/main",
            "FORCE": "true" if force else "",
            "GITHUB_OUTPUT": str(tmp / "output.txt"),
            "GITHUB_STEP_SUMMARY": str(tmp / "summary.txt"),
            "GATE_OUT": gate_out,
            "GATE_RC": str(gate_rc),
            "HELD_OUT": held_out,
            "HELD_RC": str(held_rc),
            "HUB_SAME": {"same": "1", "stale": "0", "fail": "fail"}[hub],
            "STUB_CALLS": str(tmp / "curl-calls.txt"),
        }
        done = _workflowrun.run_step(repo, dict(step_, run=script), env)

        def read(path: pathlib.Path) -> str:
            return path.read_text(encoding="utf-8") if path.exists() else ""

        outputs = read(tmp / "output.txt")
        return {
            "rc": done.returncode,
            "outputs": outputs,
            "proceed": next(
                (line.split("=", 1)[1]
                 for line in outputs.splitlines()
                 if line.startswith("proceed=")),
                None),
            "capture": (repo / "data" / "aa-raw-models.json").read_text(
                encoding="utf-8"),
            "marker": (repo / "data" / "cost-breakdown-window.txt").exists(),
            "summary": read(tmp / "summary.txt"),
            "stdout": done.stdout,
            "hub_fetches": read(tmp / "curl-calls.txt").count("\n"),
            "stderr": done.stderr,
        }

    def test_a_gate_or_probe_failure_turns_the_step_red(self):
        # bash -e is the step's whole failure discipline, and no `||` on
        # either gate or probe line may swallow it: a gate or probe that
        # exits 1 must end the step red BEFORE any verdict is computed --
        # every shape here, a forced dispatch included, which is the real
        # red-path pin: a forced run on a refused (converged, empty-axis)
        # capture must exit red, never proceed=true. Asserted: exit
        # nonzero, no proceed output written, the fresh capture left on
        # disk, the marker with it.
        for gate in ("rc1", "true", "false"):
            for probe in ("yes", "no", "rc1"):
                if gate != "rc1" and probe != "rc1":
                    continue
                for force in (False, True):
                    for hub in ("same", "stale"):
                        with self.subTest(gate=gate, probe=probe,
                                          force=force, hub=hub):
                            with tempfile.TemporaryDirectory(
                                    prefix=".hold-probe-") as raw:
                                hour = self._run_hour(
                                    pathlib.Path(raw), gate=gate, probe=probe,
                                    force=force, hub=hub)
                            self.assertNotEqual(hour["rc"], 0, hour["stderr"])
                            self.assertNotIn("proceed=", hour["outputs"])
                            self.assertEqual(hour["capture"], self.FRESH)
                            self.assertTrue(hour["marker"])

    def test_a_held_probe_drops_every_path_to_proceed_false(self):
        # probe=yes is the hold on every other axis: even a gate that saw
        # the capture MOVE, a forced dispatch and a stale hub all drop to
        # proceed=false, green. The tracked capture is restored to HEAD;
        # the fresh untracked window marker is left on disk -- inert,
        # because a held hour stages no payload -- which is the honest
        # tree state the old structural pin misdescribed as a clean tree;
        # and the hub fetch never runs: the held branch exits before the
        # live-page check could. The summary carries the pins the old
        # structural class owned and the first executed draft dropped:
        # the hold is named; a dispatch that asked for force learns from
        # its override line that nothing was rebuilt; the ordinary held
        # hour stays PATH-NEUTRAL -- it names no cause it does not have
        # (the round-1 minor a716d08 fixed, here pinned by execution):
        # not the force override, asserted on an unforced hour by the
        # exact line's absence -- the lowercase-substring pin alone
        # cannot see the line, which carries no "forced" -- and not a
        # hub cause, the held branch exiting before the live-page check
        # runs. And the held hour writes EXACTLY ONE proceed= line: the
        # held branch exits after its write, so no verdict write can
        # follow it -- the harness reads only the first proceed= line,
        # which is why the count, not the first-line value, is the pin.
        for gate in ("true", "false"):
            for force in (False, True):
                for hub in ("same", "stale"):
                    with self.subTest(gate=gate, force=force, hub=hub):
                        with tempfile.TemporaryDirectory(
                                prefix=".hold-probe-") as raw:
                            hour = self._run_hour(
                                pathlib.Path(raw), gate=gate, probe="yes",
                                force=force, hub=hub)
                        self.assertEqual(hour["rc"], 0, hour["stderr"])
                        self.assertEqual(hour["proceed"], "false")
                        self.assertEqual(hour["outputs"].count("proceed="),
                                         1)
                        self.assertEqual(hour["capture"], "head\n")
                        self.assertTrue(hour["marker"])
                        self.assertIn("### Held", hour["summary"])
                        if force:
                            self.assertIn("Force was requested",
                                          hour["summary"])
                        else:
                            self.assertNotIn("forced", hour["summary"])
                            self.assertNotIn("Force was requested",
                                             hour["summary"])
                            self.assertNotIn("stale", hour["summary"])
                        self.assertEqual(hour["stdout"].count("hold probe:"),
                                         1)
                        self.assertEqual(hour["hub_fetches"], 0)

    def test_a_not_held_probe_leaves_the_hour_to_its_verdict(self):
        # probe=no on a healthy capture: the hour's answer is the verdict's
        # alone. Moved (gate true) proceeds whatever the dispatch asked;
        # unchanged + force proceeds (the build-only rebuild, its capture
        # restored); unchanged + a stale hub OR a failed live-page fetch
        # proceeds (the republish hour -- both causes set hub_stale);
        # unchanged + current hub stays quiet. The hub fetch runs exactly
        # on the unchanged, unforced shape.
        for gate in ("true", "false"):
            for force in (False, True):
                for hub in ("same", "stale", "fail"):
                    with self.subTest(gate=gate, force=force, hub=hub):
                        with tempfile.TemporaryDirectory(
                                prefix=".hold-probe-") as raw:
                            hour = self._run_hour(
                                pathlib.Path(raw), gate=gate, probe="no",
                                force=force, hub=hub)
                        self.assertEqual(hour["rc"], 0, hour["stderr"])
                        if gate == "true":
                            proceed, fetches, capture = "true", 0, self.FRESH
                        elif force:
                            proceed, fetches, capture = "true", 0, "head\n"
                        elif hub == "same":
                            proceed, fetches, capture = "false", 1, "head\n"
                        else:
                            proceed, fetches, capture = "true", 1, "head\n"
                        self.assertEqual(hour["proceed"], proceed)
                        self.assertEqual(hour["hub_fetches"], fetches)
                        self.assertEqual(hour["capture"], capture)
                        self.assertTrue(hour["marker"])
                        # Exactly one proceed= line on the verdict path
                        # too (issue #240): the value read by the harness
                        # takes the FIRST proceed= line, so a stray second
                        # write behind a correct first one passes the value
                        # assertion and must fail the count instead.
                        self.assertEqual(
                            hour["outputs"].count("proceed="), 1)
                        # The republish hour names its cause (issue #239):
                        # a stale page and a failed fetch print different
                        # summary lines -- a failed fetch compared no page,
                        # so the run must not report a comparison result --
                        # and the republish decision above stays hub_stale's
                        # alone, identical for both causes. Where the
                        # live-page check never ran (a moved capture, a
                        # forced dispatch) or found the hub current, neither
                        # line may appear.
                        if gate == "false" and not force and hub == "stale":
                            self.assertIn(self.HUB_DIVERGED_LINE,
                                          hour["summary"])
                            self.assertNotIn(self.HUB_FETCH_FAILED_LINE,
                                             hour["summary"])
                        elif gate == "false" and not force and hub == "fail":
                            self.assertIn(self.HUB_FETCH_FAILED_LINE,
                                          hour["summary"])
                            self.assertNotIn(self.HUB_DIVERGED_LINE,
                                             hour["summary"])
                        else:
                            self.assertNotIn("republishing", hour["summary"])

    def test_an_undefined_probe_token_is_red_never_a_fall_through(self):
        # The `case` guard: the probe's stdout is the step's verdict, and a
        # token outside {yes, no} -- a swallowed failure's empty answer, a
        # half-written one, a typo'd word in the script itself -- is a
        # broken probe, red under bash -e, never a silent fall through to
        # the verdict.
        for force in (False, True):
            for hub in ("same", "stale"):
                with self.subTest(force=force, hub=hub):
                    with tempfile.TemporaryDirectory(
                            prefix=".hold-probe-") as raw:
                        hour = self._run_hour(
                            pathlib.Path(raw), gate="false", probe="maybe",
                            force=force, hub=hub)
                    self.assertNotEqual(hour["rc"], 0, hour["stderr"])
                    self.assertNotIn("proceed=", hour["outputs"])
                    self.assertEqual(hour["capture"], self.FRESH)
                    # The red names the token it refused (issue #240): the
                    # case's *) arm echoes the diagnostic to stderr before
                    # exit 1, so an exit-1 with the echo deleted -- red for
                    # the same rc, the same missing output, the same fresh
                    # capture left on disk (the arm exits before any
                    # restore) -- fails on this pin alone.
                    self.assertIn("hold probe: undefined answer 'maybe'",
                                  hour["stderr"])


STUB_PYTHON3 = """\
#!/bin/bash
# The test double for python3 inside the "Did anything move?" step: the
# no-argument call is the rendered gate, --fresh-held the hold probe, each
# answering from its fixture variable. A FAILURE prints nothing on stdout,
# byte-faithful to the real scripts/capture_gate.py, whose diagnostics go
# to stderr (measured: exit 1, 0 bytes on stdout) -- so a failed probe or
# gate leaves the step's command substitution empty exactly as the real
# script does.
if [ "$2" = "--fresh-held" ] && [ -n "$HELD_OUT" ]; then
  printf '%s\\n' "$HELD_OUT"
  exit "$HELD_RC"
fi
if [ "$2" = "--fresh-held" ]; then
  exit "$HELD_RC"
fi
[ -n "$GATE_OUT" ] && printf '%s\\n' "$GATE_OUT"
exit "$GATE_RC"
"""

STUB_CURL = """\
#!/bin/bash
# The test double for the hub's live-page fetch: writes HEAD's page when
# HUB_SAME=1, a stale page when HUB_SAME=0, and a failed fetch when
# HUB_SAME=fail -- the step's else hub_stale=true arm. Every invocation
# is recorded, the failed ones included.
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    printf '%s\\n' "$1" >> "$STUB_CALLS"
    if [ "$HUB_SAME" = fail ]; then exit 1; fi
    if [ "$HUB_SAME" = 1 ]; then printf 'page\\n' > "$1"; else printf 'old\\n' > "$1"; fi
  fi
  shift
done
exit 0
"""


class CaptureStepTests(unittest.TestCase):
    """The Capture step's exit contract, as it stands since issue #200.

    fetch_aa.py has ONE nonzero exit -- the designed red that means go
    re-read AA by hand -- so the step's trap exists to park the capture's
    stderr and re-emit it on the red path. There is no exit-3 branch, no
    window stamp, no baseline record and nothing to retire: the leaderboard
    route publishes every value it carries; the detail route fills omitted
    fields on shared models and supplies detail-only records (issue #266).
    """

    def setUp(self):
        self.wf = load()
        self.step = step(self.wf, "Capture the leaderboard")
        self.block = flattened(self.step["run"])
        self.header = WORKFLOW.read_text(
            encoding="utf-8").split("\njobs:", 1)[0]

    def test_the_fetch_runs_behind_an_rc_trap_that_parks_the_stderr(self):
        # The capture's stderr is parked in a file so the red path can
        # re-emit it under the step's own log; the rc is captured before
        # `set -e` restores the fail-fast the job runs under.
        for piece in ("set +e",
                      "python3 scripts/fetch_aa.py --cross-run-lookback "
                      "2> /tmp/fetch-err.txt",
                      "rc=$?",
                      "set -e"):
            self.assertIn(piece, self.block)
        self.assertIn("cat /tmp/fetch-err.txt >&2", self.block)

    def test_the_step_has_one_recovery_and_one_red_and_no_third_colour(self):
        # Recovery (rc 0) stands first and sets the force gate's verdict,
        # then every other rc is the designed red, re-raised unchanged so
        # the run's own colour is fetch_aa.py's. Issue #200 removed the
        # exit-3 dispute branch: nothing between the two.
        self.assertLess(self.block.index('[ "$rc" -eq 0 ]'),
                        self.block.index('exit "$rc"'))
        self.assertLess(self.block.index('[ "$rc" -eq 0 ]'),
                        self.block.index('echo "captured=true"'))
        self.assertNotIn('[ "$rc" -eq 3 ]', self.block)
        for gone in ("data/aa-disagreement-snapshot.json",
                     "data/aa-route-disagreement.txt",
                     "data/aa-last-agreeing-capture.json",
                     "git rm", "git add", "healed", "retire"):
            self.assertNotIn(gone, self.block)

    def test_the_header_documents_the_absence_of_a_disagreement_state(self):
        # The file's contract lives in its header, and the contract changed:
        # a reader must find the single-generation rule there, not
        # reconstruct a dispute branch that no longer exists.
        self.assertIn("THERE IS NO ROUTE-DISAGREEMENT STATE", self.header)
        self.assertIn("issue #200", self.header)
        self.assertIn("never exits 3", self.header)


class _SeededOrigin:
    """A local git origin the commit step really fetches, plus the runner
    environment it really runs under.

    Every executed test of the publish job's commit step needs the same
    three things: an `origin` the step's `https://github.com/...` remote
    resolves to (via `insteadOf`, never a real network), the SHA the run was
    dispatched at (`GITHUB_SHA`, the workflow generation its payload belongs
    to), and a writable HOME/RUNNER_TEMP. One seed helper serves them all, so
    a scenario differs only in the files it lands.
    """

    def _git(self, *args, cwd=None, env=None):
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, check=True,
            capture_output=True, text=True)

    def _seed_origin(self, root: pathlib.Path, files: dict):
        """Seed a local origin; return (config, base sha, origin, seed, env)."""
        origin = root / "origin.git"
        seed = root / "seed"
        self._git("init", "-q", "--bare", str(origin))
        self._git("init", "-q", str(seed))
        config = root / "gitconfig"
        # as_uri(): file:///C:/Users/... on Windows, file:///tmp/... on
        # POSIX -- a raw str(Path) renders backslashes the file:// transport
        # eats (the windows-latest matrix cell caught exactly that).
        config.write_text(
            f'[url "{origin.as_uri()}"]\n'
            "    insteadOf = https://github.com/Nitjsefnie/ai-researcher\n",
            encoding="utf-8")
        env = {
            "GIT_CONFIG_GLOBAL": str(config),
            "GIT_AUTHOR_NAME": "seed", "GIT_AUTHOR_EMAIL": "seed@example",
            "GIT_COMMITTER_NAME": "seed", "GIT_COMMITTER_EMAIL": "seed@example",
        }
        for rel, text in files.items():
            path = seed / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self._git("add", "-A", cwd=str(seed), env=env)
        self._git("commit", "-q", "-m", "seed", cwd=str(seed), env=env)
        self._git("push", "-q", str(origin), "HEAD:main",
                  cwd=str(seed), env=env)
        base = self._git("rev-parse", "HEAD", cwd=str(seed)).stdout.strip()
        return str(config), base, origin, seed, env

    def _env(self, tmp: pathlib.Path, config: str, sha: str) -> dict:
        return {
            "PATH": os.environ["PATH"],
            "HOME": str(tmp),
            "RUNNER_TEMP": str(tmp),
            "GITHUB_REPOSITORY": "Nitjsefnie/ai-researcher",
            "GITHUB_OUTPUT": str(tmp / "output.txt"),
            "GITHUB_STEP_SUMMARY": str(tmp / "summary.txt"),
            "GIT_CONFIG_GLOBAL": config,
            "GITHUB_SHA": sha,
        }


class ExecutedCommitMessageTests(_SeededOrigin, unittest.TestCase):
    """The commit step's message selection, EXECUTED, not pinned as text.

    The review corpus's ci/run-workflow-step-scripts-dont-read-them, fourth
    sighting on this file: the --diff-filter=A narrowing shipped green over
    every text pin in this module -- only running the step caught it (review
    on PR #192). Since #200 the selection has exactly two shapes, one per
    payload: the differ's own rendering (the hour whose data moved) and the
    forced rebuild's own subject (the hour the data did not). Both are run
    here over a local origin -- the https remote rewritten to it by
    GIT_CONFIG_GLOBAL -- so each scenario's commit is read back, not read
    about.
    """

    BASE_FILES = {
        "data/aa-raw-models.json": '{"models": []}\n',
        "data/aa-raw-coding-agents.json": "[]\n",
        "data/captured-at.txt": "2026-10-04\n",
        "out/frontier-models.html": "<p>base</p>\n",
    }
    MOVED_FILES = {
        "data/aa-raw-models.json": '{"models": [1]}\n',
        "data/aa-raw-coding-agents.json": "[1]\n",
        "data/aa-generation-state.json": '{"held": null}\n',
        "data/captured-at.txt": "2026-10-04T11\n",
        "out/frontier-models.html": "<p>moved</p>\n",
    }

    @classmethod
    def setUpClass(cls):
        cls.step = _workflowrun.step_by_name(
            WORKFLOW, "publish", "Commit the capture")

    def _stage_payload(self, tmp: pathlib.Path, differ_msg):
        payload = tmp / "publish-payload"
        (payload / "tree").mkdir(parents=True)
        for rel, text in self.MOVED_FILES.items():
            path = payload / "tree" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if differ_msg:
            (payload / "commit-msg.txt").write_text(differ_msg,
                                                    encoding="utf-8")

    def _run_hour(self, tmp: pathlib.Path, differ_msg):
        """Stage one hour's payload and run the real commit step."""
        config, base, _, _, _ = self._seed_origin(tmp, self.BASE_FILES)
        self._stage_payload(tmp, differ_msg)
        # The run's own workflow generation is the commit it was dispatched
        # at: the payload and the tree it lands on are one generation.
        env = self._env(tmp, config, base)
        proc = _workflowrun.run_step(tmp, self.step, env)
        self.assertEqual(proc.returncode, 0,
                         f"step failed: {proc.stderr}")
        scratch = tmp / "scratch"
        message = self._git("log", "-1", "--format=%B", cwd=str(scratch)).stdout
        names = self._git("diff-tree", "--no-commit-id", "--name-status",
                          "-r", "HEAD", cwd=str(scratch)).stdout
        log = self._git("log", "--format=%s", cwd=str(scratch)).stdout
        return message, names, log

    def test_a_moved_capture_commits_the_differ_s_own_rendering(self):
        with tempfile.TemporaryDirectory(prefix=".commit-msg-") as raw:
            message, names, log = self._run_hour(
                pathlib.Path(raw),
                differ_msg="Refresh capture: 690 models\n\nspeed rows\n")
        self.assertIn("Refresh capture: 690 models", message)
        self.assertIn("speed rows", message)
        self.assertIn("Captured by .github/workflows/refresh.yml.", message)
        self.assertNotIn("Rebuild the page: forced run", message)
        self.assertIn("M\tdata/aa-raw-models.json", names)
        self.assertIn("A\tdata/aa-generation-state.json", names)
        self.assertIn("M\tout/frontier-models.html", names)
        # The hour's data commit is the only commit it makes.
        self.assertEqual(log.count("\n"), 2, log)

    def test_a_forced_run_without_a_differ_message_writes_its_own_subject(self):
        # The republish/force shape: no commit-msg.txt in the payload, so
        # the step writes the forced rebuild's subject itself -- the one
        # subject the hour gets when the data did not move.
        with tempfile.TemporaryDirectory(prefix=".commit-msg-") as raw:
            message, names, log = self._run_hour(
                pathlib.Path(raw), differ_msg=None)
        self.assertIn(
            "Rebuild the page: forced run, AA capture unchanged", message)
        self.assertIn(
            "The build moved, the data did not. Republished so the live "
            "page matches main.", message)
        self.assertNotIn("Refresh capture", message)
        self.assertIn("M\tout/frontier-models.html", names)
        self.assertEqual(log.count("\n"), 2, log)

    def test_unchanged_republish_with_tracked_state_commits_nothing(self):
        state_path = "data/aa-generation-state.json"
        self.assertTrue((ROOT / state_path).exists())
        files = {**self.BASE_FILES, state_path: (ROOT / state_path).read_text()}
        with tempfile.TemporaryDirectory(prefix=".republish-state-") as raw, \
                mock.patch.object(self, "BASE_FILES", files), \
                mock.patch.object(self, "MOVED_FILES", files):
            tmp = pathlib.Path(raw)
            message, names, log = self._run_hour(tmp, differ_msg=None)
            outputs = (tmp / "output.txt").read_text()
            self.assertIn("publish=true\n", outputs)
            self.assertIn("commits=false\n", outputs)
            self.assertNotIn("commits=true\n", outputs)
            self.assertEqual(names, "")
            self.assertEqual(log.count("\n"), 1)
            self.assertNotIn("Rebuild the page", message)


class ExecutedGenerationTieTests(_SeededOrigin, unittest.TestCase):
    """The generation tie (issue #202), EXECUTED against a moved main.

    Run 37291766447 replayed a6d74a6's payload -- produced by a generation
    of this workflow whose payload still carried the disagreement snapshot --
    onto a main whose .gitignore no longer named it back, and died at
    `git add`. The tie is proved here the same way the failure was: the
    seed names `data/aa-disagreement-snapshot.json` back and the payload
    carries one, exactly as the older generation's did; then main moves a
    commit that drops the rule. With the tie in place the step concedes the
    hour green -- the deliberate outcome -- instead of staging a payload of
    another generation's shape.
    """

    @classmethod
    def setUpClass(cls):
        cls.step = _workflowrun.step_by_name(
            WORKFLOW, "publish", "Commit the capture")
        cls.base_files = {
            "data/aa-raw-models.json": '{"models": []}\n',
            "data/aa-raw-coding-agents.json": "[]\n",
            "data/captured-at.txt": "2026-10-04\n",
            "out/frontier-models.html": "<p>base</p>\n",
            # The older generation named the snapshot back; #200 removed
            # the rule, and the payload of that older generation still has
            # the file to stage.
            ".gitignore": (
                "*\n!/data/\n/data/*\n!/data/aa-raw-models.json\n"
                "!/data/aa-raw-coding-agents.json\n!/data/captured-at.txt\n"
                "!/data/aa-disagreement-snapshot.json\n"
                "!/out/\n/out/*\n!/out/frontier-models.html\n"),
            "data/aa-disagreement-snapshot.json": '{"older": true}\n',
        }

    @staticmethod
    def _has_commit(scratch: pathlib.Path) -> bool:
        """Whether the scratch repo holds any commit at all.

        `git init` runs before the fetch, so the scratch exists even on the
        conceding path; what must be absent is a checkout of main's tree and
        the commit on top of it.
        """
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=str(scratch),
            check=False, capture_output=True, text=True)
        return probe.returncode == 0

    def _payload(self, tmp: pathlib.Path):
        payload = tmp / "publish-payload" / "tree"
        files = {
            "data/aa-raw-models.json": '{"models": [1]}\n',
            "data/aa-raw-coding-agents.json": "[1]\n",
            "data/captured-at.txt": "2026-10-04T11\n",
            "out/frontier-models.html": "<p>moved</p>\n",
            "data/aa-disagreement-snapshot.json": '{"older": true}\n',
        }
        for rel, text in files.items():
            path = payload / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (tmp / "publish-payload" / "commit-msg.txt").write_text(
            "Refresh capture: 690 models\n\nspeed rows\n", encoding="utf-8")

    def _land_newer_generation(self, seed, origin, env):
        """Land the #200 tree: the snapshot's .gitignore rule is gone."""
        (seed / ".gitignore").write_text(
            "*\n!/data/\n/data/*\n!/data/aa-raw-models.json\n"
            "!/data/aa-raw-coding-agents.json\n!/data/captured-at.txt\n"
            "!/out/\n/out/*\n!/out/frontier-models.html\n", encoding="utf-8")
        self._git("rm", "-q", "data/aa-disagreement-snapshot.json",
                  cwd=str(seed), env=env)
        self._git("commit", "-q", "-m", "retire the window files (#200)",
                  cwd=str(seed), env=env)
        self._git("push", "-q", str(origin), "HEAD:main", cwd=str(seed),
                  env=env)
        return self._git("rev-parse", "HEAD", cwd=str(seed)).stdout.strip()

    def test_a_payload_older_than_main_concedes_the_hour_instead_of_staging_it(self):
        with tempfile.TemporaryDirectory(prefix=".generation-tie-") as raw:
            tmp = pathlib.Path(raw)
            config, base, origin, seed, git_env = self._seed_origin(
                tmp, self.base_files)
            self._payload(tmp)
            newer = self._land_newer_generation(seed, origin, git_env)
            self.assertNotEqual(base, newer)
            proc = _workflowrun.run_step(
                tmp, self.step, self._env(tmp, config, base))
            # Green, and nothing committed: the deliberate outcome.
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # The EXACT outputs, not substrings: a step that wrote
            # publish=false and later publish=true satisfies both `in`
            # checks, and one job output has one meaning.
            outputs = (tmp / "output.txt").read_text(encoding="utf-8")
            self.assertEqual(outputs, "publish=false\ncommits=false\n")
            # The scratch repo exists (it is inited before the fetch) but
            # never held a commit: main's newer tree was never checked out
            # and no payload byte was ever copied over it.
            self.assertFalse(self._has_commit(tmp / "scratch"))
            summary = (tmp / "summary.txt").read_text(encoding="utf-8")
            self.assertIn("Dropped: the payload's workflow generation",
                          summary)
            self.assertIn(base, summary)
            self.assertIn(newer, summary)

    def test_a_sha_that_is_absent_or_empty_still_concedes(self):
        # The tie fails toward the dropped hour: a GITHUB_SHA that is absent
        # and one that is empty are BOTH driven, because the workflow runs
        # under `bash -e` with no `set -u` and a `set -u` added later would
        # split them into two shapes where only one is refused today.
        for absent in (True, False):
            with self.subTest(absent=absent):
                with tempfile.TemporaryDirectory(
                        prefix=".generation-tie-") as raw:
                    tmp = pathlib.Path(raw)
                    config, _, _, _, _ = self._seed_origin(
                        tmp, self.base_files)
                    self._payload(tmp)
                    env = self._env(tmp, config, "")
                    if absent:
                        del env["GITHUB_SHA"]
                    proc = _workflowrun.run_step(tmp, self.step, env)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(
                        (tmp / "output.txt").read_text(encoding="utf-8"),
                        "publish=false\ncommits=false\n")
                    self.assertFalse(self._has_commit(tmp / "scratch"))


class DeployKeyPushTests(unittest.TestCase):
    """Issue #133 part 2: the push job's deploy-key contract.

    The push is the workflow's one privileged delivery, and its safety
    shape is copied from claudit's refresh-pricing push job: the key is
    loaded in one step of one job, fails closed when the environment is
    missing it, and never outlives the step that loaded it. The trigger
    set pin freezes what issue #180 taught about externally triggerable
    events reaching privileged surfaces.
    """

    def setUp(self):
        self.wf = load()

    def test_the_deploy_key_fails_closed_when_the_environment_misses_it(self):
        run = flattened(
            step_in(self.wf, "push", "Push the tested tree to main")["run"])
        self.assertIn(
            "MASTER_PUSH_DEPLOY_KEY is empty: the main-push environment is "
            "missing its secret", run)
        # The fallback is never a token: the push step names no token at all.
        self.assertNotIn("github.token", run)

    def test_the_agent_never_outlives_the_step_that_loaded_it(self):
        run = flattened(
            step_in(self.wf, "push", "Push the tested tree to main")["run"])
        self.assertIn('trap \'kill "$SSH_AGENT_PID" 2>/dev/null || true\' EXIT',
                      run)
        self.assertIn("ssh-add <(printf '%s\\n' \"$MASTER_PUSH_DEPLOY_KEY\")",
                      run)

    def test_no_step_before_the_hub_job_holds_a_credential(self):
        # #143 and #133: the capture step pushes nothing, and the commit
        # step's fetches went anonymous, so NO step before the hub job
        # holds a credential at all. The deploy key lives only in the push
        # job; the docs-hub key and the job token live only in the hub.
        capture = step(self.wf, "Capture the leaderboard")
        commit = pub_step(self.wf, "Commit the capture")
        push_step = step_in(self.wf, "push", "Push the tested tree to main")
        hub = hub_step(self.wf, "Publish to docs-hub")

        self.assertNotIn("GH_TOKEN", capture.get("env", {}))
        self.assertNotIn("GH_TOKEN", commit.get("env", {}))
        self.assertNotIn("MASTER_PUSH_DEPLOY_KEY", commit.get("env", {}))
        self.assertEqual(self.wf["jobs"]["push"].get("environment"),
                         "main-push")
        self.assertEqual(push_step["env"]["MASTER_PUSH_DEPLOY_KEY"],
                         "${{ secrets.MASTER_PUSH_DEPLOY_KEY }}")
        self.assertNotIn("GH_TOKEN", push_step.get("env", {}))
        self.assertEqual(hub["env"]["DOCS_HUB_API_KEY"],
                         "${{ secrets.DOCS_HUB_API_KEY }}")
        # The job token is mapped nowhere since #206: the refs-API call
        # that held GH_TOKEN is retired with the ref.
        self.assertNotIn("GH_TOKEN", hub.get("env", {}))
        self.assertNotIn("MASTER_PUSH_DEPLOY_KEY", hub.get("env", {}))

    def test_the_refresh_trigger_set_stays_frozen(self):
        # Schedule plus the force dispatch. Issue #180's lesson applies to
        # the ci-gate caller/callee pair, not here -- this workflow has no
        # privileged cross-context sink -- but the set is pinned anyway, so
        # a trigger added later is a decision, not a slip.
        triggers = self.wf.get("on") or self.wf.get(True) or {}
        self.assertEqual(set(triggers), {"schedule", "workflow_dispatch"})

    def test_the_bundle_is_never_fetched_from_a_foreign_run(self):
        # Same-run artifact only: the push job's download consumes the
        # publish job's upload name, and nothing keys on a workflow_run.
        up = step_in(self.wf, "publish", "Upload the push data")
        down = step_in(self.wf, "push", "Download the push bundle")
        self.assertEqual(up["with"]["name"], down["with"]["name"])
        self.assertEqual(self.wf["jobs"]["push"]["needs"], "publish")


# ---------------------------------------------------------------------------
# issue #227: the marker conditional's operator semantics
# ---------------------------------------------------------------------------


def _commit_capture_step():
    return step_in(load(), "publish", "Commit the capture")


def _marker_conditional() -> str:
    """The if/elif block extracted verbatim from the commit step's run."""
    lines = _commit_capture_step()["run"].splitlines()
    start = next(i for i, line in enumerate(lines)
                 if 'if [ -f "${PAYLOAD}/tree/data/'
                 'cost-breakdown-window.txt" ]; then' in line)
    end = next(i for i in range(start, len(lines))
               if lines[i].strip() == "fi")
    return "\n".join(lines[start:end + 1])


def test_the_marker_conditional_behaves_on_the_four_hours(tmp_path):
    # The operator semantics behind the source-text pin above, because the
    # text alone cannot carry them -- the first draft pinned the text and
    # was green over a dead elif whose add branch fired on the checkout's
    # own materialized copy. The block is extracted from refresh.yml
    # VERBATIM and run in a scratch repo shaped like the write job's --
    # sitting at the tip being committed onto, the payload tree copied
    # over it -- across the four hours of the marker lifecycle.
    if os.name == "nt":
        pytest.skip(
            "the block under test is GitHub-runner bash against a "
            "POSIX payload path, and the write job itself runs on "
            "ubuntu; the same skip shape as the stub-gh classifier "
            "tests")
    block = _marker_conditional()
    payload_data = tmp_path / "payload" / "tree" / "data"
    payload_data.mkdir(parents=True)
    env = {**os.environ, "PAYLOAD": str(tmp_path / "payload")}

    def scratch(hour: str, tracked: bool) -> pathlib.Path:
        # One FRESH repo per hour: a reused path would carry the previous
        # hour's staged state into the next commit and pollute the case.
        repo = tmp_path / f"scratch-{hour}"
        (repo / "data").mkdir(parents=True)
        git = ["git", "-C", str(repo)]
        subprocess.run([*git, "init", "-q", "-b", "main"], check=True,
                       capture_output=True)
        # A runner carries no global git identity (the commit-scopes hook
        # governs OUR commits, not a fixture's throwaway repo); the scratch
        # gets the same local identity the write job's own scratch uses.
        subprocess.run([*git, "config", "user.name", "github-actions[bot]"],
                       check=True, capture_output=True)
        subprocess.run([*git, "config", "user.email",
                        "41898282+github-actions[bot]@users.noreply.github.com"],
                       check=True, capture_output=True)
        (repo / "data" / "captured-at.txt").write_text("2026-10-08\n")
        if tracked:
            (repo / "data" / "cost-breakdown-window.txt").write_text("w\n")
            subprocess.run([*git, "add", "data/"], check=True,
                           capture_output=True)
        else:
            subprocess.run([*git, "add", "data/captured-at.txt"], check=True,
                           capture_output=True)
        subprocess.run([*git, "commit", "-qm", "tip"], check=True,
                       capture_output=True)
        return repo

    def status(repo: pathlib.Path) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True, capture_output=True, text=True).stdout

    def run_block(repo: pathlib.Path) -> None:
        # The write job's sequence: the payload tree overlays the checkout
        # (`cp -a` -- copies over, never deletes), THEN the conditional.
        shutil.copytree(tmp_path / "payload" / "tree", repo,
                        dirs_exist_ok=True)
        # check stays off on purpose: the nonzero case is asserted below,
        # with the block's own stderr in the message.
        proc = subprocess.run(["bash", "-c", block], cwd=repo, env=env,
                              check=False, capture_output=True, text=True)
        assert proc.returncode == 0, (
            f"marker conditional rc={proc.returncode}: {proc.stderr}")

    # Heal hour: tracked at the tip, absent from the payload -- the
    # checkout's own materialized copy must not fire the add branch; the
    # removal stages.
    repo = scratch("heal", tracked=True)
    run_block(repo)
    assert "D  data/cost-breakdown-window.txt" in status(repo)

    # Window hour: the payload carries it -- staged in, tracked or not.
    (payload_data / "cost-breakdown-window.txt").write_text("w\n")
    repo = scratch("window", tracked=False)
    run_block(repo)
    assert "A  data/cost-breakdown-window.txt" in status(repo)

    # Persist hour: tracked and unchanged in the payload -- a no-op.
    repo = scratch("persist", tracked=True)
    run_block(repo)
    assert status(repo) == ""

    # Quiet hour: absent from both -- a no-op.
    (payload_data / "cost-breakdown-window.txt").unlink()
    repo = scratch("quiet", tracked=False)
    run_block(repo)
    assert status(repo) == ""


class HFTrackerStructureTests(unittest.TestCase):
    """The key is accessible only to the push job, which executes no tree code."""

    tracker = 'hf'
    fetcher = 'hf'

    def tracker_step(self, job, name):
        return step_in(load(), f'{self.tracker}-{job}', name)

    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file())
        self.assertFalse((ROOT / '.github/workflows/hf-trending.yml').exists())

    def test_triggers_concurrency_and_main_only(self):
        workflow = load()
        workflow['jobs'] = {name: workflow['jobs'][f'{self.tracker}-{name}']
                            for name in ('fetch', 'push')}
        self.assertEqual(workflow['concurrency'], {
            'group': 'refresh', 'cancel-in-progress': False})
        self.assertEqual(workflow['jobs']['fetch']['if'],
                         "github.ref == 'refs/heads/main'")
        self.assertNotIn('needs', workflow['jobs']['fetch'])

    def test_permissions_and_secret_scope(self):
        workflow = load()
        workflow['jobs'] = {name: workflow['jobs'][f'{self.tracker}-{name}']
                            for name in ('fetch', 'push')}
        self.assertEqual(set(workflow['jobs']), {'fetch', 'push'})
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertNotIn('secrets.', str(workflow['jobs']['fetch']))
        for name, job in workflow['jobs'].items():
            with self.subTest(job=name):
                self.assertEqual(job['permissions'], {'contents': 'read'})
                self.assertEqual(job['timeout-minutes'],
                                 10 if name == 'fetch' else 15)
                self.assertEqual(job.get('environment'),
                                 'main-push' if name == 'push' else None)
                for entry in job['steps']:
                    if name == 'fetch':
                        self.assertNotIn('secrets.', str(entry))
        push = workflow['jobs']['push']
        preceding = 'push' if self.tracker == 'hf' else 'hf-push'
        dependencies = [f'{self.tracker}-fetch', preceding]
        if self.tracker == 'hf':
            dependencies.append('hub')
        self.assertEqual(push['needs'], dependencies)
        self.assertEqual(push['if'],
                         f"!cancelled() && needs.{self.tracker}-fetch.outputs.commits == 'true' && "
                         f"needs.{preceding}.result != 'cancelled'")
        self.assertNotIn('needs.hub.result', push['if'])
        self.assertEqual(push['outputs'], {
            'landed': '${{ steps.push.outputs.landed }}'})
        self.assertEqual(workflow['jobs']['fetch']['outputs'], {
            'commits': '${{ steps.commit.outputs.commits }}'})
        key_steps = [entry for entry in push['steps']
                     if 'secrets.' in str(entry)]
        self.assertEqual(key_steps, [self.tracker_step('push', 'Push the trending commit')])
        self.assertEqual(key_steps[0]['env']['MASTER_PUSH_DEPLOY_KEY'],
                         '${{ secrets.MASTER_PUSH_DEPLOY_KEY }}')
        self.assertEqual(key_steps[0]['if'],
                         "steps.replay.outputs.commits == 'true'")
        self.assertNotIn('env', workflow)
        self.assertNotIn('env', push)

    def test_tracker_excludes_frontier_scripts_and_push_excludes_python_and_github_token(self):
        workflow = load()
        workflow['jobs'] = {name: workflow['jobs'][f'{self.tracker}-{name}']
                            for name in ('fetch', 'push')}
        for name, job in workflow['jobs'].items():
            for entry in job['steps']:
                run = entry.get('run', '')
                self.assertNotRegex(run, r'build\.py|capture_gate\.py|fetch_aa\.py|publish_docs\.py|diff_aa\.py')
                if name == 'push':
                    self.assertNotRegex(run, r'\bpython3?\b|\bpip\b')
                    self.assertNotIn('github.token', str(entry))

    def test_artifact_is_this_runs_bundle_and_upload_is_success_gated(self):
        # The two jobs exchange a bundle through an agreed artifact name
        # and staging path. Deriving those expectations from their YAML
        # catches a producer/consumer mismatch without freezing either
        # setting in Python. A coordinated transport change can preserve
        # that agreement without changing the data the tracker commits.
        # The success condition remains an independent boundary: a failed
        # fetch must not hand a bundle to delivery merely because its
        # artifact configuration agrees with the download configuration.
        # These structural checks complement the executed commit/replay
        # cases, which exercise the bundle and its effects on git history.
        upload = self.tracker_step('fetch', 'Upload the push bundle')
        download = self.tracker_step('push', 'Download the push bundle')
        self.assertEqual(upload['if'], "success() && steps.commit.outputs.commits == 'true'")
        self.assertEqual(upload['with']['name'], download['with']['name'])
        self.assertEqual(upload['with']['path'], download['with']['path'])
        self.assertEqual([entry.get('name') for entry in load()['jobs'][f'{self.tracker}-push']['steps']],
                         ['Download the push bundle', 'Replay onto fresh main',
                          'Push the trending commit'])

    def test_capture_message_and_exact_add_list(self):
        self.assertEqual(self.tracker_step('fetch', 'Fetch the top 10')['run'],
                         f'python3 scripts/fetch_{self.fetcher}_trending.py --message "$RUNNER_TEMP/message"')
        run = self.tracker_step('fetch', 'Commit when changed')['run']
        adds = re.findall(r'^\s*git add (.+)$', run, re.MULTILINE)
        self.assertEqual(adds, [f'data/{self.fetcher}-trending.json'])
        self.assertIn('git commit -q -F "$RUNNER_TEMP/message"', run)
        self.assertNotIn('git push', run)

    def test_key_lifecycle_matches_refresh_and_has_no_force_push(self):
        run = self.tracker_step('push', 'Push the trending commit')['run']
        self.assertIn('trap \'kill "$SSH_AGENT_PID" 2>/dev/null || true\' EXIT', run)
        self.assertIn('ssh-add <(printf \'%s\\n\' "$MASTER_PUSH_DEPLOY_KEY")', run)
        self.assertIn('StrictHostKeyChecking=yes', run)
        self.assertNotIn('--force', run)
        self.assertNotIn('--depth', run)

    def test_deploy_key_delivery_stays_in_lockstep_with_refresh(self):
        refresh_path = ROOT / '.github/workflows/refresh.yml'
        refresh = _workflowrun.step_by_name(
            refresh_path, 'push', 'Push the tested tree to main')['run'].splitlines()
        trending = self.tracker_step('push', 'Push the trending commit')['run'].splitlines()
        files = f'refresh.yml: push and {self.tracker}-push'
        success_output = ['else', '  echo "landed=true" >> "$GITHUB_OUTPUT"']
        self.assertEqual(trending[-3:-1], success_output)
        trending[-3:-1] = []
        # Apart from the pinned output, only truthful diagnostics differ.
        differences = (
            # Trending's pre-push concession promises a fresh list, not a suite.
            ('  echo "::notice::main moved under the run (tested base $base, current tip $fetched); the next hourly run re-fetches, re-tests and lands it"',
             '  echo "::notice::main moved under the run (tested base $base, current tip $fetched); the next hourly run fetches and lands the trending list"', 1),
            # Trending's post-rejection concession likewise promises no suite.
            ('  echo "::notice::main moved before the push landed; the next hourly run re-fetches, re-tests and lands it"',
             '  echo "::notice::main moved before the push landed; the next hourly run fetches and lands the trending list"', 1),
            # Both summary branches describe fetching the list without a suite.
            ('    echo "The next hourly run re-fetches on the new tip, re-runs the suite"',
             '    echo "The next hourly run fetches the trending list on the new tip"', 2),
            # Both summary branches omit refresh's capture-job-specific wording.
            ('    echo "in the capture job, and lands the data there."',
             '    echo "and lands the data there."', 2),
        )
        canonical = {}
        for refresh_line, trending_line, count in differences:
            self.assertEqual(refresh.count(refresh_line), count, files)
            self.assertEqual(trending.count(trending_line), count, files)
            canonical[trending_line] = refresh_line
        # Whole-line canonicalization retains every line and its position: a
        # one-sided edit, insertion, deletion or reorder fails the comparison.
        self.assertEqual(refresh, [canonical.get(line, line) for line in trending],
                         f'Deploy-key delivery diverged between {files}')


class ORTrackerStructureTests(HFTrackerStructureTests):
    tracker = 'or'
    fetcher = 'openrouter'


class RankingsStructureTests(unittest.TestCase):
    """Build landed history without keys; publish only this run's artifact."""

    def setUp(self):
        self.wf = load()

    def test_rankings_waits_for_deliveries_and_runs_every_hour_on_main(self):
        job = self.wf['jobs']['rankings']
        self.assertEqual(job['needs'], ['push', 'hf-push', 'or-push'])
        self.assertEqual(job['if'],
                         "!cancelled() && github.ref == 'refs/heads/main'")
        self.assertEqual(self.wf['concurrency'], {
            'group': 'refresh', 'cancel-in-progress': False})

    def test_rankings_hub_has_an_explicit_failure_isolated_condition(self):
        self.assertEqual(self.wf['jobs']['rankings-hub'].get('if'),
                         "!cancelled() && needs.rankings.result == 'success' && "
                         "(needs.rankings-push.result == 'success' || "
                         "needs.rankings-push.result == 'skipped')")

    def test_rankings_stages_push_data_on_every_successful_build(self):
        job = self.wf['jobs']['rankings']
        self.assertEqual(job['outputs'], {'commits': '${{ steps.commit.outputs.commits }}'})
        commit = step_in(self.wf, 'rankings', 'Commit when changed')
        self.assertEqual(commit['id'], 'commit')
        self.assertIn('git diff --quiet -- out/trending-rankings.html', commit['run'])
        self.assertEqual(re.findall(r'^\s*git add (.+)$', commit['run'], re.MULTILINE),
                         ['out/trending-rankings.html'])
        upload = step_in(self.wf, 'rankings', 'Upload the push bundle')
        self.assertNotIn('if', upload)
        names = [entry.get('name') for entry in job['steps']]
        self.assertLess(names.index('Build the rankings page'), names.index('Commit when changed'))
        self.assertLess(names.index('Commit when changed'), names.index('Upload the push bundle'))

    def test_rankings_push_mirrors_tracker_delivery_with_only_page_adjustments(self):
        push = self.wf['jobs']['rankings-push']
        tracker = self.wf['jobs']['hf-push']
        self.assertEqual(push['needs'], ['rankings'])
        self.assertEqual(push['if'],
                         "!cancelled() && needs.rankings.result == 'success' && "
                         "needs.rankings.outputs.commits == 'true'")
        for key in ('environment', 'permissions', 'timeout-minutes', 'outputs'):
            self.assertEqual(push[key], tracker[key])
        expected_steps = json.loads(json.dumps(tracker['steps']))
        expected_steps[0]['with']['name'] = step_in(
            self.wf, 'rankings', 'Upload the push bundle')['with']['name']
        expected_steps[1]['run'] = expected_steps[1]['run'].replace(
            'data/hf-trending.json', 'out/trending-rankings.html').replace(
                'Fresh main already carries the trending list',
                'Fresh main already carries the rankings page')
        expected_steps[2]['run'] = expected_steps[2]['run'].replace(
            'the trending list', 'the rankings page')
        self.assertEqual(push['steps'], expected_steps)
        for entry in push['steps']:
            self.assertNotRegex(commands(entry.get('run', '')),
                                r'\bpython3?\b|\bpip\b|\bnpm\b|\bbash\b|\bsh\b')
            self.assertNotIn('github.token', str(entry))

    def test_rankings_hub_compares_main_page_bytes_before_comparing_live_bytes(self):
        job = self.wf['jobs']['rankings-hub']
        self.assertNotIn('rankings-push-data', str(job))
        self.assertNotIn('tip.txt', str(job))
        run = commands(step_in(self.wf, 'rankings-hub', 'Publish to docs-hub')['run'])
        self.assertIn('if ! git -C "${scratch}" fetch --quiet origin main', run)
        self.assertIn('show FETCH_HEAD:out/trending-rankings.html', run)
        self.assertIn('cmp -s "$main_page"', run)
        self.assertLess(run.index('cmp -s "$main_page"'), run.index('if curl'))
        self.assertNotIn('--depth', run)
        self.assertNotIn('git push', run)

    def test_rankings_builds_with_defaults_without_dispatch_sha(self):
        job = self.wf['jobs']['rankings']
        self.assertNotIn('github.sha', str(job))
        build_step = step_in(self.wf, 'rankings', 'Build the rankings page')
        self.assertEqual(build_step['run'], 'python3 scripts/build_rankings.py')

    def test_rankings_hub_waits_for_delivery_and_page_build_precedes_upload(self):
        self.assertEqual(self.wf['jobs']['rankings-hub']['needs'],
                         ['rankings', 'rankings-push'])
        names = [s.get('name') for s in self.wf['jobs']['rankings']['steps']]
        self.assertLess(names.index('Build the rankings page'),
                        names.index('Upload the rankings page'))

    def test_rankings_credentials_stay_in_the_code_free_upload_job(self):
        self.assertNotIn('env', self.wf)
        for name in ('rankings', 'rankings-hub'):
            job = self.wf['jobs'][name]
            self.assertEqual(job['permissions'], {'contents': 'read'})
            self.assertGreater(job['timeout-minutes'], 0)
            self.assertNotIn('environment', job)
            self.assertNotIn('env', job)
        self.assertNotIn('secrets.', str(self.wf['jobs']['rankings']))
        upload = step_in(self.wf, 'rankings-hub', 'Publish to docs-hub')
        self.assertEqual(upload['env'], {
            'DOCS_HUB_API_KEY': '${{ secrets.DOCS_HUB_API_KEY }}'})
        key_jobs = {name for name, job in self.wf['jobs'].items()
                    if 'secrets.DOCS_HUB_API_KEY' in str(job)}
        self.assertEqual(key_jobs, {'hub', 'rankings-hub'})
        steps = self.wf['jobs']['rankings-hub']['steps']
        self.assertEqual([s for s in steps if 'secrets.' in str(s)], [upload])
        for entry in steps:
            self.assertNotRegex(commands(entry.get('run', '')),
                                r'\bpython3?\b|\bpip[0-9]?\b')

    def test_rankings_upload_mirrors_the_hub_wire_format(self):
        run = commands(step_in(self.wf, 'rankings-hub', 'Publish to docs-hub')['run'])
        for piece in ("-F 'slug=ai-researcher/trending-rankings'",
                      "-F 'title=Trending rankings — Hugging Face & OpenRouter top 10 over time'",
                      "-F 'tags=trending,rankings,ai'",
                      "-F 'project=ai-researcher'", "-F 'from=ai-researcher'",
                      "-F 'file=@out/trending-rankings.html;type=text/html'",
                      '-H "x-docs-key: ${DOCS_HUB_API_KEY}"',
                      'https://docs.nitjsefni.eu/api/publish',
                      '[ "${code}" -lt 200 ] || [ "${code}" -ge 300 ]',
                      "jq -e '(.error // null) != null'"):
            self.assertIn(piece, run)
        self.assertNotIn('DOCS_HUB_URL', run)
        self.assertNotIn('github.sha', run)


@pytest.mark.parametrize('upstream', ['success', 'failure', 'skipped'])
@pytest.mark.parametrize('rankings', ['success', 'failure', 'skipped', 'cancelled'])
@pytest.mark.parametrize('pushed', ['success', 'failure', 'skipped', 'cancelled'])
@pytest.mark.parametrize('cancelled', [False, True])
def test_rankings_hub_condition_covers_ancestor_outcomes(upstream, rankings, pushed, cancelled):
    """Ancestor failures cannot block publication; a failed page push must."""
    condition = load()['jobs']['rankings-hub'].get('if', 'success()')
    terms = {
        'success()': not cancelled and upstream == 'success' and rankings == 'success',
        '!cancelled()': not cancelled,
        "needs.rankings.result == 'success'": rankings == 'success',
        "needs.rankings-push.result == 'success'": pushed == 'success',
        "needs.rankings-push.result == 'skipped'": pushed == 'skipped',
    }
    for term, value in terms.items():
        condition = condition.replace(term, str(value))
    actual = eval(condition.replace('&&', 'and').replace('||', 'or'),  # pylint: disable=eval-used
                  {'__builtins__': {}}, {})
    assert actual is (not cancelled and rankings == 'success' and pushed in ('success', 'skipped'))


RANKINGS_CURL = '''import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith('https://'))
output = Path(args[args.index('-o') + 1])
with Path(os.environ['HUB_CALLS']).open('a', encoding='utf-8') as calls:
    calls.write(json.dumps(args) + chr(10))
if url == 'https://docs.nitjsefni.eu/d/ai-researcher/trending-rankings':
    if os.environ['LIVE_PAGE'] == 'fail':
        raise SystemExit(22)
    page = (Path(os.environ['RANKINGS_PAGE']).read_bytes()
            if os.environ['LIVE_PAGE'] == 'same' else b'previous page')
    output.write_bytes(page)
elif url == 'https://docs.nitjsefni.eu/api/publish':
    if os.environ['UPLOAD_CODE'] == 'transport':
        raise SystemExit(7)
    output.write_text(os.environ['UPLOAD_BODY'], encoding='utf-8')
    print(os.environ['UPLOAD_CODE'], end='')
else:
    raise SystemExit('unexpected curl endpoint: ' + url)
'''


@pytest.mark.skipif(os.name == 'nt', reason='workflow shell runs on Ubuntu')
@pytest.mark.parametrize('main,live,code,body,expected,uploads', [
    ('moved', 'stale', '200', '{}', 0, 0),
    ('moved-same', 'stale', '200', '{}', 0, 1),
    ('fetch-fail', 'stale', '200', '{}', 0, 0),
    ('empty-head', 'stale', '200', '{}', 0, 0),
    ('unreadable-head', 'stale', '200', '{}', 0, 0),
    ('landed', 'same', '200', '{}', 0, 0),
    ('landed', 'stale', '200', '{}', 0, 1),
    ('landed', 'fail', '201', '{}', 0, 1),
    ('landed', 'stale', '199', '{}', 1, 1),
    ('landed', 'stale', '300', '{}', 1, 1),
    ('landed', 'stale', '403', '{"error":"refused"}', 1, 1),
    ('landed', 'stale', '200', '{"error":"refused"}', 1, 1),
    ('landed', 'stale', '200', '{"error":false}', 0, 1),
    ('landed', 'stale', '200', '{"error":null}', 0, 1),
    ('landed', 'stale', 'transport', '{}', 7, 1),
])
def test_rankings_hub_upload_verdicts(tmp_path, main, live, code, body, expected, uploads):
    """Publish verified main bytes, skip duplicates, and surface hub refusals."""
    repo = tmp_path / 'origin'
    repo.mkdir()
    git = HFTrackerExecutedStepsTests.git
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'config', 'user.name', 'fixture')
    git(repo, 'config', 'user.email', 'fixture@example.com')
    git(repo, 'config', 'commit.gpgsign', 'false')
    committed = repo / 'out/trending-rankings.html'
    committed.parent.mkdir()
    committed.write_bytes(b'previous page')
    git(repo, 'add', 'out/trending-rankings.html')
    git(repo, 'commit', '-q', '-m', 'base')
    base = git(repo, 'rev-parse', 'HEAD').strip()
    committed.write_bytes(b'<html>rankings</html>\n')
    git(repo, 'add', 'out/trending-rankings.html')
    git(repo, 'commit', '-q', '-m', 'page landed with a new SHA')
    assert git(repo, 'rev-parse', 'HEAD').strip() != base
    if main == 'moved':
        committed.write_bytes(b'newer page')
        git(repo, 'add', 'out/trending-rankings.html')
        git(repo, 'commit', '-q', '-m', 'main moved with a newer page')
    elif main == 'moved-same':
        git(repo, 'commit', '-q', '--allow-empty', '-m', 'main moved with the same page')
    config = tmp_path / 'gitconfig'
    remote = repo / 'unavailable.git' if main == 'fetch-fail' else repo
    git(repo, 'config', '--file', str(config),
        f'url.{remote.as_posix()}.insteadOf', 'https://github.com/fixture/rankings')
    runner = tmp_path / 'runner'
    page = runner / 'rankings-page/trending-rankings.html'
    page.parent.mkdir(parents=True)
    page.write_bytes(b'<html>rankings</html>\n')
    stub = tmp_path / 'bin'
    stub.mkdir()
    if main in ('empty-head', 'unreadable-head'):
        # Keep the real successful fetch, then make its FETCH_HEAD unusable.
        # The tie must affirmatively read the committed page before any HTTP.
        (stub / 'git').write_text(
            '#!/bin/sh\n"$REAL_GIT" "$@" || exit $?\n'
            'case "$*" in\n'
            '  *" fetch --quiet origin main")\n'
            '    "$TEST_PYTHON" -c \'from pathlib import Path; import os, sys; '
            'p = Path(sys.argv[1]) / ".git/FETCH_HEAD"; '
            'p.write_text("") if os.environ["HEAD_STATE"] == "empty-head" '
            'else (p.unlink(), p.mkdir())\' "$2" ;;\n'
            'esac\n', encoding='utf-8')
        (stub / 'git').chmod(0o755)
    (stub / 'curl_payload.py').write_text(RANKINGS_CURL, encoding='utf-8')
    (stub / 'curl').write_text(
        '#!/bin/sh\nexec "$TEST_PYTHON" "$(dirname "$0")/curl_payload.py" "$@"\n',
        encoding='utf-8')
    (stub / 'curl').chmod(0o755)
    calls = tmp_path / 'calls'
    env = {**os.environ, 'PATH': str(stub) + os.pathsep + os.environ['PATH'],
           'TEST_PYTHON': sys.executable, 'RUNNER_TEMP': str(runner),
           'GITHUB_STEP_SUMMARY': str(tmp_path / 'summary'),
           'DOCS_HUB_API_KEY': 'fixture', 'LIVE_PAGE': live,
           'UPLOAD_CODE': code, 'UPLOAD_BODY': body,
           'HUB_CALLS': str(calls), 'RANKINGS_PAGE': str(page),
           'GITHUB_REPOSITORY': 'fixture/rankings', 'GIT_CONFIG_GLOBAL': str(config),
           'REAL_GIT': shutil.which('git') or 'git', 'HEAD_STATE': main}
    entry = dict(step_in(load(), 'rankings-hub', 'Publish to docs-hub'))
    entry['run'] = entry['run'].replace(
        '/tmp/publish-response.json', '"${RUNNER_TEMP}/publish-response.json"')
    done = _workflowrun.run_step(tmp_path, entry, env)
    assert done.returncode == expected, done.stdout + done.stderr
    if main in ('moved', 'fetch-fail', 'empty-head', 'unreadable-head'):
        assert 'Nothing published by this run.' in done.stdout
        summary = (tmp_path / 'summary').read_text(encoding='utf-8')
        if main == 'moved':
            assert "Lost the race: main's tip moved past this run's rankings page" in summary
        else:
            assert ("could not verify main's committed page — publishing nothing this run; "
                    "the next hourly run self-heals") in summary
        assert not calls.exists()
        assert not (runner / 'page').exists()
        return
    requests = [json.loads(line) for line in calls.read_text(encoding='utf-8').splitlines()]
    assert len(requests) == 1 + uploads
    assert requests[0][-3:] == [
        'https://docs.nitjsefni.eu/d/ai-researcher/trending-rankings',
        '-o', requests[0][-1]]
    assert '-H' not in requests[0]
    if not uploads:
        assert 'Nothing uploaded' in done.stdout
        assert not (runner / 'page').exists()
        return
    request = requests[1]
    assert request[-1] == 'https://docs.nitjsefni.eu/api/publish'
    assert request[request.index('-H') + 1] == 'x-docs-key: fixture'
    assert [request[i + 1] for i, arg in enumerate(request) if arg == '-F'] == [
        'slug=ai-researcher/trending-rankings',
        'title=Trending rankings — Hugging Face & OpenRouter top 10 over time',
        'tags=trending,rankings,ai', 'project=ai-researcher', 'from=ai-researcher',
        'file=@out/trending-rankings.html;type=text/html']
    assert (runner / 'page/out/trending-rankings.html').read_bytes() == page.read_bytes()
    if expected == 1:
        assert f'publish failed: HTTP {code}' in done.stderr
        assert body in done.stderr


@unittest.skipIf(os.name == 'nt', 'workflow shell runs on Ubuntu')
class HFTrackerExecutedStepsTests(unittest.TestCase):
    """Run the actual YAML scripts against local git repos and a stubbed fetch."""

    tracker = 'hf'
    fetcher = 'hf'
    data = 'data/hf-trending.json'
    message = 'Trending: 1 new in the top 10: org/new\n\nNEW  rank 1 org/new\n'

    def tracker_step(self, job, name):
        return step_in(load(), f'{self.tracker}-{job}', name)

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-q', '-b', 'main')
        self.configure(self.repo)
        (self.repo / self.data).parent.mkdir()
        (self.repo / self.data).write_text('old\n', encoding='utf-8')
        (self.repo / 'README.md').write_text('base\n', encoding='utf-8')
        self.git(self.repo, 'add', self.data, 'README.md')
        self.git(self.repo, 'commit', '-qm', 'base')
        self.base = self.git(self.repo, 'rev-parse', 'HEAD').strip()
        self.origin = self.root / 'origin.git'
        self.git(self.root, 'clone', '-q', '--bare', str(self.repo), str(self.origin))
        self.git(self.repo, 'remote', 'add', 'origin', str(self.origin))
        self.runner = self.root / 'runner'
        self.runner.mkdir()
        (self.runner / 'message').write_text(self.message, encoding='utf-8')
        home = self.root / 'home'
        home.mkdir()
        (self.root / 'output').touch()
        (self.root / 'summary').touch()
        self.env = {**os.environ, 'RUNNER_TEMP': str(self.runner),
                    'GITHUB_OUTPUT': str(self.root / 'output'),
                    'GITHUB_STEP_SUMMARY': str(self.root / 'summary'),
                    'GITHUB_REPOSITORY': 'fixture/trending',
                    'REPO': 'fixture/trending',
                    'MASTER_PUSH_DEPLOY_KEY': '',
                    'HOME': str(home), 'PUSH_REMOTE': str(self.origin)}

    @staticmethod
    def git(repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              capture_output=True, text=True, timeout=60).stdout

    def configure(self, repo):
        self.git(repo, 'config', 'user.name', 'fixture')
        self.git(repo, 'config', 'user.email', 'fixture@example.com')
        self.git(repo, 'config', 'commit.gpgsign', 'false')

    def run_step(self, job, name, expected=0):
        result = _workflowrun.run_step(self.repo, self.tracker_step(job, name), self.env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        summary = pathlib.Path(self.env['GITHUB_STEP_SUMMARY']).read_text(encoding='utf-8')
        if name == 'Push the trending commit' and (expected or 'Dropped:' in summary):
            self.assertNotIn('landed=true', pathlib.Path(
                self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8'))
        return result

    def stage_change(self):
        (self.repo / self.data).write_text('new\n', encoding='utf-8')
        self.run_step('fetch', 'Commit when changed')

    def replay(self):
        # Redirect the production anonymous HTTPS fetch to the local bare remote.
        self.git(self.repo, 'config', '--file', str(self.root / 'gitconfig'),
                 f'url.{self.origin}.insteadOf', 'https://github.com/fixture/trending')
        self.env['GIT_CONFIG_GLOBAL'] = str(self.root / 'gitconfig')
        self.run_step('push', 'Replay onto fresh main')

    def advance_main(self, path='README.md', content='moved\n'):
        other = self.root / 'other'
        self.git(self.root, 'clone', '-q', str(self.origin), str(other))
        self.configure(other)
        (other / path).write_text(content, encoding='utf-8')
        self.git(other, 'add', path)
        self.git(other, 'commit', '-qm', 'main moved')
        self.git(other, 'push', '-q', 'origin', 'main')
        return self.git(other, 'rev-parse', 'HEAD').strip()

    def load_ephemeral_key(self):
        key = self.root / 'key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                        '-f', str(key)], check=True, capture_output=True, timeout=60)
        self.env['MASTER_PUSH_DEPLOY_KEY'] = key.read_text(encoding='utf-8')

    def test_unchanged_capture_creates_no_commit_or_bundle(self):
        self.run_step('fetch', 'Commit when changed')
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD').strip(), self.base)
        self.assertEqual(pathlib.Path(self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8'),
                         'commits=false\n')
        self.assertFalse((self.runner / 'push-data').exists())

    def test_changed_capture_commits_only_data_with_exact_message(self):
        (self.repo / 'README.md').write_text('do not commit\n', encoding='utf-8')
        self.stage_change()
        self.assertEqual(self.git(self.repo, 'diff-tree', '--no-commit-id',
                                  '--name-only', '-r', 'HEAD').splitlines(), [self.data])
        self.assertEqual(self.git(self.repo, 'log', '-1', '--format=%B').rstrip(),
                         self.message.rstrip())
        self.assertEqual(self.git(self.repo, 'log', '-1', '--format=%an').strip(),
                         'github-actions[bot]')
        self.assertNotIn('Co-Authored-By:', self.git(self.repo, 'log', '-1', '--format=%B'))
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), self.base)
        self.assertTrue((self.runner / 'push-data/push.bundle').exists())
        self.assertEqual((self.runner / 'push-data/base.txt').read_text(encoding='utf-8').strip(),
                         self.base)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_replay_preserves_fresh_main_and_message_then_pushes(self):
        self.stage_change()
        fresh = self.advance_main()
        self.replay()
        push_repo = self.runner / 'scratch'
        self.assertEqual(self.git(push_repo, 'rev-parse', 'HEAD^').strip(), fresh)
        self.assertEqual(self.git(push_repo, 'show', 'HEAD:README.md'), 'moved\n')
        self.assertEqual(self.git(push_repo, 'show', f'HEAD:{self.data}'), 'new\n')
        self.assertEqual(self.git(push_repo, 'log', '-1', '--format=%B').rstrip(), self.message.rstrip())
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        self.assertIn('landed=true\n', pathlib.Path(
            self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8'))
        landed = self.git(self.origin, 'rev-parse', 'main').strip()
        self.assertEqual(landed, (self.runner / 'push-data/tip.txt').read_text(encoding='utf-8').strip())

    def test_replay_preserves_the_other_trackers_landed_commit(self):
        self.stage_change()
        other_data = ('data/openrouter-trending.json' if self.tracker == 'hf'
                      else 'data/hf-trending.json')
        fresh = self.advance_main(other_data, 'other list\n')
        self.replay()
        scratch = self.runner / 'scratch'
        self.assertEqual(self.git(scratch, 'rev-parse', 'HEAD^').strip(), fresh)
        self.assertEqual(self.git(scratch, 'show', f'HEAD:{other_data}'),
                         'other list\n')
        self.assertEqual(self.git(scratch, 'diff-tree', '--no-commit-id',
                                  '--name-only', '-r', 'HEAD').splitlines(),
                         [self.data])

    def test_replay_noops_when_main_already_has_capture(self):
        self.stage_change()
        fresh = self.advance_main(self.data, 'new\n')
        self.replay()
        self.assertTrue(pathlib.Path(self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8').endswith('commits=false\n'))
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), fresh)
        self.assertNotIn('landed=true', pathlib.Path(
            self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8'))

    def test_push_missing_key_fails_before_delivery(self):
        result = self.run_step('push', 'Push the trending commit', 1)
        self.assertIn('MASTER_PUSH_DEPLOY_KEY is empty', result.stderr)
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), self.base)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_main_move_after_replay_concedes_without_force(self):
        self.stage_change()
        self.replay()
        fresh = self.advance_main()
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), fresh)
        self.assertIn('main moved under the run', pathlib.Path(self.env['GITHUB_STEP_SUMMARY']).read_text(encoding='utf-8'))

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_rejected_push_with_main_still_at_base_fails(self):
        self.stage_change()
        self.replay()
        hook = self.origin / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8')
        hook.chmod(0o755)
        self.load_ephemeral_key()
        result = self.run_step('push', 'Push the trending commit', 1)
        self.assertIn('the push was rejected while main stood still', result.stderr)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_main_moving_during_push_concedes_after_rejection(self):
        self.stage_change()
        self.replay()
        writer = self.root / 'racer'
        self.git(self.root, 'clone', '-q', str(self.origin), str(writer))
        self.configure(writer)
        (writer / 'README.md').write_text('race\n', encoding='utf-8')
        self.git(writer, 'add', 'README.md')
        self.git(writer, 'commit', '-qm', 'raced')
        raced = self.git(writer, 'rev-parse', 'HEAD').strip()
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        wrapper = bin_dir / 'git'
        wrapper.write_text(
            '#!/bin/sh\ncase "$*" in\n'
            '  *" push origin "*) "$REAL_GIT" -C "$RACE_REPO" push -q origin main ;;\n'
            'esac\nexec "$REAL_GIT" "$@"\n', encoding='utf-8')
        wrapper.chmod(0o755)
        real_git = shutil.which('git')
        assert real_git is not None, 'git is required to execute the workflow'
        self.env.update({'REAL_GIT': real_git, 'RACE_REPO': str(writer),
                         'PATH': str(bin_dir) + os.pathsep + os.environ['PATH']})
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), raced)
        self.assertIn('main moved before the push landed', pathlib.Path(self.env['GITHUB_STEP_SUMMARY']).read_text(encoding='utf-8'))

    def test_fetch_script_is_invoked_with_message_and_failure_propagates(self):
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        script = f'scripts/fetch_{self.fetcher}_trending.py'
        target = self.repo / script
        shutil.copyfile(ROOT / script, target)
        # A sitecustomize stub answers the fetcher's network boundary only.
        stub = self.root / 'stub'
        stub.mkdir()
        models = ('[{"id": f"org/{n}"} for n in range(int(os.environ["COUNT"]))]'
                  if self.tracker == 'hf' else
                  '{"data": {"models": [{"slug": f"org/{n}"} '
                  'for n in range(int(os.environ["COUNT"]))]}}')
        (stub / 'sitecustomize.py').write_text(
            'import io, json, os, urllib.request\n'
            'urllib.request.urlopen = lambda *a, **k: io.BytesIO(json.dumps('
            + models +
            ').encode())\n', encoding='utf-8')
        (self.repo / self.data).write_text('{"models": []}\n', encoding='utf-8')
        self.env.update({'PYTHONPATH': str(stub), 'COUNT': '10'})
        self.run_step('fetch', 'Fetch the top 10')
        self.assertTrue((self.runner / 'message').read_text(encoding='utf-8').startswith(
            'Trending: 10 new in the top 10:' if self.tracker == 'hf' else
            'Top 10: 10 new:'))
        saved = (self.repo / self.data).read_bytes()
        self.env['COUNT'] = '9'
        result = self.run_step('fetch', 'Fetch the top 10', 1)
        self.assertIn('expected 10 models, got 9', result.stderr)
        self.assertEqual((self.repo / self.data).read_bytes(), saved)


class ORTrackerExecutedStepsTests(HFTrackerExecutedStepsTests):
    tracker = 'or'
    fetcher = 'openrouter'
    data = 'data/openrouter-trending.json'
    message = 'Top 10: 1 new: org/new\n\nNEW  rank 1 org/new\n'


@unittest.skipIf(os.name == 'nt', 'workflow shell runs on Ubuntu')
class RankingsExecutedStepsTests(unittest.TestCase):
    """Execute the page committer and the same delivery safeguards as the lists."""

    repo: pathlib.Path
    runner: pathlib.Path
    root: pathlib.Path
    origin: pathlib.Path
    base: str
    env: dict[str, str]
    data = 'out/trending-rankings.html'
    message = (
        'Rebuild the rankings page\n\n'
        "The page is rebuilt from the two trending lists' history and differs from the committed copy.\n\n"
        'Captured by .github/workflows/refresh.yml.\n')
    setUp = HFTrackerExecutedStepsTests.setUp
    git = staticmethod(HFTrackerExecutedStepsTests.git)
    configure = HFTrackerExecutedStepsTests.configure
    run_step = HFTrackerExecutedStepsTests.run_step
    stage_change = HFTrackerExecutedStepsTests.stage_change
    replay = HFTrackerExecutedStepsTests.replay
    advance_main = HFTrackerExecutedStepsTests.advance_main
    load_ephemeral_key = HFTrackerExecutedStepsTests.load_ephemeral_key
    test_changed_page_commits_only_page_with_exact_message = (
        HFTrackerExecutedStepsTests.test_changed_capture_commits_only_data_with_exact_message)
    test_replay_preserves_fresh_main_and_message_then_pushes = (
        HFTrackerExecutedStepsTests.test_replay_preserves_fresh_main_and_message_then_pushes)
    test_replay_noops_when_main_already_has_page = (
        HFTrackerExecutedStepsTests.test_replay_noops_when_main_already_has_capture)
    test_push_missing_key_fails_before_delivery = (
        HFTrackerExecutedStepsTests.test_push_missing_key_fails_before_delivery)
    test_main_move_after_replay_concedes_without_force = (
        HFTrackerExecutedStepsTests.test_main_move_after_replay_concedes_without_force)
    test_rejected_push_with_main_still_at_base_fails = (
        HFTrackerExecutedStepsTests.test_rejected_push_with_main_still_at_base_fails)
    test_main_moving_during_push_concedes_after_rejection = (
        HFTrackerExecutedStepsTests.test_main_moving_during_push_concedes_after_rejection)

    def tracker_step(self, job, name):
        return step_in(load(), 'rankings' if job == 'fetch' else 'rankings-push', name)

    def test_unchanged_page_stages_base_and_tip_without_commit_or_bundle(self):
        self.run_step('fetch', 'Commit when changed')
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD').strip(), self.base)
        self.assertEqual(pathlib.Path(self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8'),
                         'commits=false\n')
        data = self.runner / 'push-data'
        self.assertEqual(sorted(path.name for path in data.iterdir()), ['base.txt', 'tip.txt'])
        for name in ('base.txt', 'tip.txt'):
            self.assertEqual((data / name).read_text(encoding='utf-8').strip(), self.base)

    @unittest.skipUnless(sys.platform == 'linux',
                         'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
    def test_conceded_delivery_and_failed_hub_fetch_publish_nothing(self):
        self.stage_change()
        self.replay()
        fresh = self.advance_main()
        self.load_ephemeral_key()
        self.run_step('push', 'Push the trending commit')
        output = pathlib.Path(self.env['GITHUB_OUTPUT']).read_text(encoding='utf-8')
        self.assertNotIn('landed=true', output)
        self.assertEqual(self.git(self.origin, 'rev-parse', 'main').strip(), fresh)
        self.assertEqual(self.git(self.origin, 'show', f'main:{self.data}'), 'old\n')
        # A successful conceded push admits the hub under its actual job gate.
        condition = load()['jobs']['rankings-hub']['if']
        for term, value in {
                '!cancelled()': 'True',
                "needs.rankings.result == 'success'": 'True',
                "needs.rankings-push.result == 'success'": 'True',
                "needs.rankings-push.result == 'skipped'": 'False'}.items():
            condition = condition.replace(term, value)
        self.assertTrue(eval(condition.replace('&&', 'and').replace('||', 'or'),  # pylint: disable=eval-used
                             {'__builtins__': {}}, {}))
        page = self.runner / 'rankings-page/trending-rankings.html'
        page.parent.mkdir()
        page.write_bytes((self.repo / self.data).read_bytes())
        self.assertEqual(page.read_bytes(), b'new\n')
        # Redirect only the hub's main fetch to an unavailable local remote.
        self.git(self.repo, 'config', '--file', str(self.root / 'gitconfig'),
                 f'url.{self.root / "unavailable.git"}.insteadOf',
                 'https://github.com/fixture/unavailable')
        stub = self.root / 'bin'
        stub.mkdir()
        (stub / 'curl_payload.py').write_text(RANKINGS_CURL, encoding='utf-8')
        (stub / 'curl').write_text(
            '#!/bin/sh\nexec "$TEST_PYTHON" "$(dirname "$0")/curl_payload.py" "$@"\n',
            encoding='utf-8')
        (stub / 'curl').chmod(0o755)
        calls = self.root / 'hub-calls'
        self.env.update({
            'PATH': str(stub) + os.pathsep + os.environ['PATH'],
            'TEST_PYTHON': sys.executable, 'GITHUB_REPOSITORY': 'fixture/unavailable',
            'DOCS_HUB_API_KEY': 'fixture', 'LIVE_PAGE': 'stale',
            'UPLOAD_CODE': '200', 'UPLOAD_BODY': '{}',
            'HUB_CALLS': str(calls), 'RANKINGS_PAGE': str(page)})
        entry = dict(step_in(load(), 'rankings-hub', 'Publish to docs-hub'))
        entry['run'] = entry['run'].replace(
            '/tmp/publish-response.json', '"${RUNNER_TEMP}/publish-response.json"')
        done = _workflowrun.run_step(self.repo, entry, self.env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('Nothing published by this run.', done.stdout)
        self.assertIn("could not verify main's committed page — publishing nothing this run; "
                      "the next hourly run self-heals", pathlib.Path(
                          self.env['GITHUB_STEP_SUMMARY']).read_text(encoding='utf-8'))
        self.assertFalse(calls.exists(), 'neither live-page fetch nor upload may run')
        self.assertFalse((self.runner / 'page').exists())


HUB_UPLOAD_CURL = '''import os
from pathlib import Path
import sys

args = sys.argv[1:]
url = next((arg for arg in args if arg.startswith('https://')), '')
output = Path(args[args.index('-o') + 1])
if url == 'https://docs.nitjsefni.eu/d/ai-researcher/frontier-models':
    output.write_text('previous page', encoding='utf-8')
elif url == 'https://docs.nitjsefni.eu/api/publish':
    fields = [args[index + 1] for index, value in enumerate(args) if value == '-F']
    assert 'slug=ai-researcher/frontier-models' in fields, fields
    upload = next(field for field in fields if field.startswith('file=@'))
    page = Path(upload[len('file=@'):].split(';', 1)[0]).read_bytes()
    Path(os.environ['HUB_PUBLISHED']).write_bytes(page)
    output.write_text('{}', encoding='utf-8')
    print('200', end='')
else:
    raise SystemExit('unexpected curl endpoint: ' + url)
with Path(os.environ['HUB_CALLS']).open('a', encoding='utf-8') as calls:
    calls.write(url + chr(10))
'''


@unittest.skipUnless(sys.platform == 'linux',
                     'requires Linux ssh-agent/ssh-add behaviour matching ubuntu-latest')
class ExecutedHubTrackerOrderingTests(unittest.TestCase):
    """Run allowed job interleavings against one local origin and a fake hub."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.workflow = load()
        self.source = self.root / 'source'
        self.source.mkdir()
        self._git(self.source, 'init', '-q', '-b', 'main')
        self._configure(self.source)
        files = {'data/hf-trending.json': '{"models": []}\n',
                 'data/openrouter-trending.json': '{"models": []}\n',
                 'out/frontier-models.html': 'previous page\n',
                 'README.md': 'base\n'}
        for name, content in files.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        self._git(self.source, 'add', '--', *files)
        self._git(self.source, 'commit', '-qm', 'base')
        self.base = self._git(self.source, 'rev-parse', 'HEAD').strip()
        self.origin = self.root / 'origin.git'
        self._git(self.root, 'clone', '-q', '--bare', str(self.source), str(self.origin))
        self.config = self.root / 'gitconfig'
        self._git(self.source, 'config', '--file', str(self.config),
                  f'url.{self.origin.as_uri()}.insteadOf', 'https://github.com/fixture/trending')
        key = self.root / 'key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                       check=True, capture_output=True, timeout=60)
        self.key = key.read_text(encoding='utf-8')
        self.published = self.root / 'published.html'
        self.calls = self.root / 'curl-calls'
        stub = self.root / 'bin'
        stub.mkdir()
        (stub / 'curl_payload.py').write_text(HUB_UPLOAD_CURL, encoding='utf-8')
        (stub / 'curl').write_text(
            '#!/bin/sh\nexec "$(command -v python || command -v python3)" '
            '"$(dirname "$0")/curl_payload.py" "$@"\n', encoding='utf-8')
        (stub / 'curl').chmod(0o755)
        self.contexts = {}
        self._context('aa', self.source, stub)
        for tracker, key_name in (('hf', 'id'), ('or', 'slug')):
            repo = self.root / tracker
            self._git(self.root, 'clone', '-q', str(self.origin), str(repo))
            self._configure(repo)
            self._context(tracker, repo, stub)
            name = 'hf' if tracker == 'hf' else 'openrouter'
            (repo / f'data/{name}-trending.json').write_text(
                json.dumps({'models': [{key_name: 'org/new'}]}), encoding='utf-8')
            runner = pathlib.Path(self.contexts[tracker][1]['RUNNER_TEMP'])
            (runner / 'message').write_text('Update list\n', encoding='utf-8')
            self._run(f'{tracker}-fetch', 'Commit when changed', tracker)
        self.page = b'<html>new AA page</html>\n'
        (self.source / 'out/frontier-models.html').write_bytes(self.page)
        self._git(self.source, 'add', '--', 'out/frontier-models.html')
        self._git(self.source, 'commit', '-qm', 'AA page')
        self.aa_tip = self._git(self.source, 'rev-parse', 'HEAD').strip()
        self._git(self.source, 'branch', 'push')
        runner = pathlib.Path(self.contexts['aa'][1]['RUNNER_TEMP'])
        bundle = runner / 'push-data'
        bundle.mkdir()
        self._git(self.source, 'bundle', 'create', str(bundle / 'push.bundle'),
                  f'{self.base}..push')
        (bundle / 'base.txt').write_text(self.base + '\n', encoding='utf-8')
        (bundle / 'tip.txt').write_text(self.aa_tip + '\n', encoding='utf-8')
        payload = runner / 'publish-payload/tree/out'
        payload.mkdir(parents=True)
        (payload / 'frontier-models.html').write_bytes(self.page)

    @staticmethod
    def _git(repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              capture_output=True, text=True, timeout=60).stdout

    def _configure(self, repo):
        self._git(repo, 'config', 'user.name', 'fixture')
        self._git(repo, 'config', 'user.email', 'fixture@example.com')
        self._git(repo, 'config', 'commit.gpgsign', 'false')

    def _context(self, name, repo, stub):
        runner = self.root / f'{name}-runner'
        runner.mkdir()
        home = self.root / f'{name}-home'
        home.mkdir()
        (runner / 'output').touch()
        (runner / 'summary').touch()
        env = {**os.environ, 'RUNNER_TEMP': str(runner), 'HOME': str(home),
               'GITHUB_OUTPUT': str(runner / 'output'),
               'GITHUB_STEP_SUMMARY': str(runner / 'summary'),
               'GITHUB_REPOSITORY': 'fixture/trending', 'REPO': 'fixture/trending',
               'GIT_CONFIG_GLOBAL': str(self.config), 'PUSH_REMOTE': self.origin.as_uri(),
               'MASTER_PUSH_DEPLOY_KEY': self.key, 'DOCS_HUB_API_KEY': 'fixture',
               'HUB_PUBLISHED': str(self.published), 'HUB_CALLS': str(self.calls),
               'PATH': str(stub) + os.pathsep + os.environ['PATH']}
        self.contexts[name] = repo, env

    def _run(self, job, name, context):
        repo, env = self.contexts[context]
        entry = dict(step_in(self.workflow, job, name))
        if job == 'hub':
            # Relocate only the response scratch file; the tip comparison and
            # upload logic run unchanged without touching a shared /tmp file.
            entry['run'] = entry['run'].replace(
                '/tmp/publish-response.json', '"${RUNNER_TEMP}/publish-response.json"')
        result = _workflowrun.run_step(repo, entry, env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_hub_publishes_before_same_run_tracker_commits_land(self):
        self._run('push', 'Push the tested tree to main', 'aa')
        self.assertEqual(self._git(self.origin, 'rev-parse', 'main').strip(), self.aa_tip)
        completed = {'publish', 'push', 'hf-fetch', 'or-fetch'}
        pending = ['hf-push', 'or-push', 'hub']
        order = []
        for _ in range(len(pending)):
            job = next((name for name in pending
                        if set(self.workflow['jobs'][name]['needs']) <= completed), None)
            assert job is not None, f'no ready job: {pending}'
            if job == 'hub':
                result = self._run(job, 'Publish to docs-hub', 'aa')
                self.assertTrue(self.published.exists(), result.stdout)
            else:
                tracker = job.split('-')[0]
                self._run(job, 'Replay onto fresh main', tracker)
                self._run(job, 'Push the trending commit', tracker)
                output = pathlib.Path(self.contexts[tracker][1]['GITHUB_OUTPUT'])
                self.assertIn('landed=true\n', output.read_text(encoding='utf-8'))
            completed.add(job)
            pending.remove(job)
            order.append(job)
        self.assertEqual(order, ['hub', 'hf-push', 'or-push'])
        self.assertEqual(self.published.read_bytes(), self.page)
        self.assertEqual(self.calls.read_text(encoding='utf-8').splitlines(), [
            'https://docs.nitjsefni.eu/d/ai-researcher/frontier-models',
            'https://docs.nitjsefni.eu/api/publish'])
        tips = [self.aa_tip]
        for tracker in ('hf', 'or'):
            runner = pathlib.Path(self.contexts[tracker][1]['RUNNER_TEMP'])
            tip = (runner / 'push-data/tip.txt').read_text(encoding='utf-8').strip()
            self.assertEqual(self._git(self.origin, 'rev-parse', tip + '^').strip(), tips[-1])
            tips.append(tip)
        self.assertEqual(self._git(self.origin, 'rev-parse', 'main').strip(), tips[-1])

    def test_hub_still_concedes_to_a_third_party_main_move(self):
        self._run('push', 'Push the tested tree to main', 'aa')
        other = self.root / 'third-party'
        self._git(self.root, 'clone', '-q', str(self.origin), str(other))
        self._configure(other)
        (other / 'README.md').write_text('third-party change\n', encoding='utf-8')
        self._git(other, 'add', '--', 'README.md')
        self._git(other, 'commit', '-qm', 'third-party change')
        self._git(other, 'push', '-q', 'origin', 'main')
        moved = self._git(other, 'rev-parse', 'HEAD').strip()
        result = self._run('hub', 'Publish to docs-hub', 'aa')
        self.assertIn('Nothing published by this run.', result.stdout)
        self.assertFalse(self.published.exists())
        self.assertFalse(self.calls.exists())
        self.assertEqual(self._git(self.origin, 'rev-parse', 'main').strip(), moved)
