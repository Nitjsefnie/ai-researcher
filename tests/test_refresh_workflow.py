"""Structural pins on .github/workflows/refresh.yml.

The workflow publishes the live page hourly, and since issues #143 and #133
its write side is three jobs in a fixed order: `refresh` (capture, rendered
gate, rebuild, suite) runs on a read-only token and leaves the commit
payload as an artifact of its own run; `publish` -- a keyless committer --
downloads that artifact and replays the hour's commits into a git bundle
while running no repository code; `push` -- the only job that loads the
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
is a gap-fill only, so the workflow has one capture exit colour and one
commit message for a moved capture. The pins below cover the recovery and the
re-raise the Capture step keeps, not a dispute branch.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

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
        # Issues #143 and #133, narrowed by #206: the published-ref move was
        # the workflow's last contents:write holder and the live page's
        # embedded stamp replaced it, so EVERY job now declares read and no
        # write permission exists anywhere in the workflow. The push job --
        # the deploy key's only reader -- is read-only: the push
        # authenticates with the key, never the job token. No write-side
        # job checks the tree out.
        workflow = self.wf
        self.assertEqual(workflow.get("permissions"), {"contents": "read"})
        jobs = workflow["jobs"]
        for name in ("publish", "push", "hub"):
            assert name in jobs, f"the {name} job is missing from refresh.yml"
        for name, job in jobs.items():
            assert (job.get("permissions") or {}).get("contents") == "read", (
                f"{name} must declare contents: read")
        writer = jobs["hub"]
        assert not [s for s in writer["steps"]
                    if s.get("uses", "").startswith("actions/checkout@")], (
            "hub runs no repository code: no checkout step")
        push = jobs["push"]
        assert push["needs"] == "publish", (
            "the bundle is this run's own data: needs, not a workflow_run")
        assert push.get("environment") == "main-push", (
            "the deploy key is reachable only through the main-push "
            "environment")
        assert not [s for s in push["steps"]
                    if s.get("uses", "").startswith("actions/checkout@")], (
            "the push job runs no repository code: no checkout step")
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
        # Same-run artifact only: the upload is error-gated on the name, the
        # download consumes that name, and the download precedes the commit.
        up = step(self.wf, "Upload the publish payload")
        down = pub_step(self.wf, "Download the publish payload")

        self.assertEqual(up["with"]["name"], down["with"]["name"])
        self.assertEqual(up["with"]["if-no-files-found"], "error")
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
        # #200), so the list is the four payload paths, the window marker
        # behind its own presence guard (issue #227), and nothing that
        # varies by hour.
        run = flattened(step(self.wf, "Stage the publish payload")["run"])

        for piece in ("data/aa-raw-models.json",
                      "data/aa-raw-coding-agents.json",
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
        # The new divergence cause gets its own truthful summary line.
        self.assertIn("differs from HEAD", run)

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
        self.assertEqual(len(setup), 1)
        # setup-python stays unconditional: it is cheap, and fetch_aa.py
        # runs on it.
        self.assertNotIn("if", setup[0])

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


class CaptureStepTests(unittest.TestCase):
    """The Capture step's exit contract, as it stands since issue #200.

    fetch_aa.py has ONE nonzero exit -- the designed red that means go
    re-read AA by hand -- so the step's trap exists to park the capture's
    stderr and re-emit it on the red path. There is no exit-3 branch, no
    window stamp, no baseline record and nothing to retire: the leaderboard
    route publishes every value it carries and the detail route fills only
    what it omits.
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
        self.assertEqual(up["with"]["if-no-files-found"], "error")
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
        proc = subprocess.run(["bash", "-c", block], cwd=repo, env=env,
                              capture_output=True, text=True)
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
