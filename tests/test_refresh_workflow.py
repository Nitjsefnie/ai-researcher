"""Structural pins on .github/workflows/refresh.yml.

The workflow publishes the live page hourly, and since issues #143 and #133
its write side is three jobs in a fixed order: `refresh` (capture, rendered
gate, rebuild, suite) runs on a read-only token and leaves the commit
payload as an artifact of its own run; `publish` -- a keyless committer --
downloads that artifact and replays the hour's commits into a git bundle
while running no repository code; `push` -- the only job that loads the
deploy key, in the main-push environment -- delivers the bundle to main;
`hub` -- the workflow's only contents:write holder since the split -- uploads
the verified page and moves the `published` ref.
Its safety lives in the gating BETWEEN steps and BETWEEN jobs: what runs only
after the suite passed, what only when the commit actually landed, what heals
a stale publish. Those contracts are invisible to the Python suite until
something parses the YAML, so this file does -- structurally, on step shape
and on substrings that name the mechanism, never on line numbers or
whole-run-block equality that any reflow would break.
"""
import pathlib
import re
import unittest

import yaml

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

    def test_only_the_hub_job_holds_contents_write(self):
        # Issues #143 and #133: the hub job is the workflow's only
        # contents:write holder (the published-ref move). The push job --
        # the deploy key's only reader -- is read-only: the push
        # authenticates with the key, never the job token. No write-side
        # job checks the tree out.
        workflow = self.wf
        self.assertEqual(workflow.get("permissions"), {"contents": "read"})
        jobs = workflow["jobs"]
        for name in ("publish", "push", "hub"):
            assert name in jobs, f"the {name} job is missing from refresh.yml"
        for name, job in jobs.items():
            contents = (job.get("permissions") or {}).get("contents")
            if name == "hub":
                assert contents == "write", (
                    "hub is the workflow's only writer and must declare it")
            else:
                assert contents != "write", (
                    f"{name} holds contents: write; only hub may")
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
        # data/. (The heal gate's `git diff origin/published HEAD --
        # out/frontier-models.html` stays: it compares pages, not captures.)
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
        # before the heal gate's ref fetch.
        self.assertLess(run.index("git checkout -- data/"),
                        run.index("refs/heads/published"))

    def test_the_payload_staging_restores_heads_page_when_the_capture_did_not_move(self):
        # Issue #94, second half: on a heal run the suite's rebuild is now
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
        # the fixed add list, the measured base commit, the window files
        # (unless this hour retires them -- shipping what a removal commits
        # away would resurrect it), and the differ's message when one ran.
        run = flattened(step(self.wf, "Stage the publish payload")["run"])

        for piece in ("data/aa-raw-models.json",
                      "data/aa-raw-coding-agents.json",
                      "data/captured-at.txt",
                      "out/frontier-models.html",
                      "data/aa-disagreement-snapshot.json",
                      "data/aa-route-disagreement.txt",
                      '[ "$RETIRE" = "true" ]',
                      "commit-msg.txt"):
            self.assertIn(piece, run)

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

    def test_the_publish_step_updates_the_published_ref_after_a_successful_upload(self):
        # The ref records the last successfully published state, so the heal
        # check has something to compare against. It must move only after
        # the upload succeeded, in the same step -- the first refs-API
        # command is the GET probe that decides create-vs-update.
        run = flattened(hub_step(self.wf, "Publish to docs-hub")["run"])

        self.assertLess(
            run.index("curl -sS"), run.index("cat /tmp/publish-response.json"))
        self.assertLess(
            run.index("curl -sS"),
            run.index('gh api "repos/$REPO/git/refs/heads/published"'))

    def test_the_published_ref_moves_through_the_refs_api(self):
        # Issue 77: the checkout is shallow (actions/checkout's default
        # depth-1), so a local `git push` behind the ref update cannot walk
        # enough ancestry to prove the update is a fast-forward and was
        # rejected "(fetch first)" on every publishing run -- even though it
        # was one. The refs API runs the check server-side, where the full
        # graph lives: a 404 on GET means CREATE (POST needs no fast-forward
        # proof), otherwise PATCH, whose default non-forced update IS
        # GitHub's fast-forward check. The step must document that a
        # non-forced PATCH is the point, so a future reader does not "fix"
        # the 422 by adding force.
        raw = hub_step(self.wf, "Publish to docs-hub")["run"]
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
        # API owns this ref now: no step in either job may git-push to it.
        # (The heal gate's `git fetch` of the same ref only reads it; the
        # prose may still name the retired mechanism.)
        for job in self.wf["jobs"].values():
            for s in job["steps"]:
                raw = s.get("run", "")
                if "refs/heads/published" in flattened(raw):
                    self.assertNotIn("git push", commands(raw))

    def test_the_publish_step_aborts_when_a_newer_run_already_published(self):
        # Issue 74: two overlapping runs can both reach this step, and if
        # the OLDER run's upload lands after the newer run's, the hub ends
        # up serving the older page while the `published` ref records the
        # newer commit — an inversion the heal gate's ref comparison cannot
        # see. Immediately before the upload the step fresh-fetches the ref
        # (anonymous, same shape as the heal gate) and, when the tip is not
        # this run's own page commit (`tip`, the publish job's record; the
        # tie above has already conceded when it is not main's tip), asks
        # the compare API, whose status names the TIP side relative to the
        # BASE side. Only a tip that is AHEAD (a newer run already
        # published) aborts: green, exit 0, no upload, no ref move.
        # `behind` is the normal heal and publishes; a failed or
        # unrankable answer retries once and then publishes anyway behind a
        # warning, because availability of publish beats the residual
        # seconds-wide window. The newest run NEVER aborts, so within any
        # overlap the newest page always wins.
        run = flattened(hub_step(self.wf, "Publish to docs-hub")["run"])

        # The gate stands between the step's start and the upload: the
        # anonymous ref fetch and the compare call precede the upload, and
        # the abort leaves through exit 0 before anything is uploaded.
        self.assertLess(run.index("fetch --depth=1 origin"),
                        run.index("https://docs.nitjsefni.eu/api/publish"))
        self.assertLess(
            run.index("refs/heads/published:refs/remotes/origin/published"),
            run.index("https://docs.nitjsefni.eu/api/publish"))
        self.assertLess(run.index("repos/$REPO/compare/"),
                        run.index("https://docs.nitjsefni.eu/api/publish"))
        self.assertLess(run.index("exit 0"), run.index("https://docs.nitjsefni.eu/api/publish"))
        # The gate reads the status field, breaks its retry loop only on a
        # real ranking, and aborts on ahead alone. Two attempts total, then a
        # warning and a publish anyway.
        self.assertIn("--jq .status", run)
        self.assertIn("ahead|behind|identical) break", run)
        self.assertIn('"$status" = ahead', run)
        self.assertIn("for _ in 1 2", run)
        self.assertIn("WARNING: the compare API", run)
        self.assertIn("already published", run)

    def test_the_unchanged_path_also_checks_the_hubs_live_page(self):
        # Issue 74: the ref comparison cannot see an upload that landed AFTER
        # the published ref moved — the ref agrees with HEAD while the HUB
        # serves the older page. On the unchanged path the gate therefore
        # also fetches the hub's live page (the public /d/ route serves
        # the stored bytes verbatim, proven byte-identical to the
        # committed page (2026-09-29)) and compares it byte-for-byte
        # against HEAD's page. Divergence sets hub_stale, as does a
        # failed fetch: same stance as the ref fetch above, an extra
        # republish costs one hub version, and a real outage fails red
        # at the publish step.
        run = flattened(step(self.wf, "Did anything move?")["run"])

        # The check stands on the unchanged path, after the ref check, and
        # feeds the same proceed decision.
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
        # bundle may carry two commits (the retirement rides along), so
        # tip^ would name the retirement commit.
        self.assertIn('base.txt")" =', run)

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


class RouteDisagreementPublishTests(unittest.TestCase):
    """Issue #118, amending #100: the capture's route-disagreement refusal
    (exit 3) no longer green-skips the hour -- it publishes the disputed
    capture. fetch_aa.py writes the disagreement snapshot, the Capture step
    writes the window stamp and FALLS THROUGH to the rendered gate, and the
    hour proceeds exactly like a moved-capture one. Since #143 the window
    files and the retirement travel to the writer as payload, not pushes
    from the capture step. There is NO time bound on a disputed window: the
    page's banner is the visible alarm. Pins on mechanism words and ordering
    over the flattened blocks, never line numbers, in this file's style.
    """

    def setUp(self):
        self.wf = load()
        self.step = step(self.wf, "Capture the leaderboard")
        self.block = flattened(self.step["run"])
        self.header = WORKFLOW.read_text(
            encoding="utf-8").split("\njobs:", 1)[0]

    def test_the_fetch_runs_behind_an_rc_trap_so_the_step_can_classify_it(self):
        # The capture's stderr is parked in a file because every branch
        # below needs it: the stamp carries it, the red paths re-emit it.
        # alert_after is GONE: the 3 h red bound retired with #118.
        for piece in ("set +e",
                      "python3 scripts/fetch_aa.py 2> /tmp/fetch-err.txt",
                      "rc=$?",
                      "set -e",
                      "stamp=data/aa-route-disagreement.txt",
                      "now=$(date -u +%s)"):
            self.assertIn(piece, self.block)
        self.assertNotIn("alert_after", self.block)

    def test_the_capture_step_holds_no_push_credentials(self):
        # #143 and #133: the capture step pushes nothing, and since the
        # commit step's fetches went anonymous, NO step before the hub job
        # holds a credential at all. The deploy key lives only in the push
        # job; the docs-hub key and the job token live only in the hub.
        self.assertNotIn("GH_TOKEN", self.step.get("env", {}))
        commit = pub_step(self.wf, "Commit the capture")
        self.assertNotIn("GH_TOKEN", commit.get("env", {}))
        self.assertNotIn("MASTER_PUSH_DEPLOY_KEY", commit.get("env", {}))
        push = self.wf["jobs"]["push"]
        push_step = step_in(self.wf, "push", "Push the tested tree to main")
        self.assertEqual(push.get("environment"), "main-push")
        self.assertEqual(push_step["env"]["MASTER_PUSH_DEPLOY_KEY"],
                         "${{ secrets.MASTER_PUSH_DEPLOY_KEY }}")
        self.assertNotIn("GH_TOKEN", push_step.get("env", {}))
        hub = hub_step(self.wf, "Publish to docs-hub")
        self.assertEqual(hub["env"]["DOCS_HUB_API_KEY"],
                         "${{ secrets.DOCS_HUB_API_KEY }}")
        self.assertEqual(hub["env"]["GH_TOKEN"], "${{ github.token }}")
        self.assertNotIn("MASTER_PUSH_DEPLOY_KEY", hub.get("env", {}))

    def test_the_three_exit_colours_are_classified_in_order(self):
        # Recovery (rc 0) stands first, then the disputed publish (rc 3),
        # then the designed red re-raise for everything else.
        self.assertLess(self.block.index('[ "$rc" -eq 0 ]'),
                        self.block.index('[ "$rc" -eq 3 ]'))
        self.assertLess(self.block.index('[ "$rc" -eq 3 ]'),
                        self.block.index('exit "$rc"'))
        self.assertIn("cat /tmp/fetch-err.txt >&2", self.block)

    def test_an_exit_three_refusal_publishes_and_falls_through(self):
        # captured=true: a disputed capture RAN. The stamp is written before
        # the fall-through, the summary names the disputed publish, and the
        # branch holds no exit of its own -- the rendered gate decides moved
        # vs unchanged downstream, exactly as for a moved capture.
        idx_open = self.block.index('[ "$rc" -eq 3 ]')
        idx_true = self.block.index('echo "captured=true"', idx_open)
        idx_stamp = self.block.index('> "$stamp"', idx_true)
        idx_summary = self.block.index("building and publishing the disputed capture",
                                       idx_stamp)
        # The branch ENDS at its own green exit: a disputed hour must exit 0
        # and reach the rendered gate -- without it, control falls to the
        # trailing red handler and exits 3, the exact hold-and-fail this
        # branch exists to replace (found by review, fixed 2026-10-02).
        idx_exit = self.block.index("exit 0", idx_summary)
        idx_fi = self.block.index(" fi", idx_exit)
        between = self.block[idx_summary:idx_exit]
        self.assertNotIn("exit 1", between)
        self.assertLess(idx_true, idx_stamp)
        self.assertIn("issue #118", self.block[idx_summary:idx_summary + 200])
        # The exit is the branch's last word before its closing fi.
        self.assertLess(idx_exit, idx_fi)

    def test_the_stamp_is_written_only_when_absent_and_keeps_the_window_start(self):
        # The banner names ONE window across hours: an existing stamp's
        # first line is preserved, only the diagnostic body refreshes.
        idx_f = self.block.index('if [ ! -f "$stamp" ]; then')
        idx_keep = self.block.index('head -n 1 "$stamp"', idx_f)
        self.assertLess(idx_f, idx_keep)

    def test_a_refusal_without_a_snapshot_is_red(self):
        # fetch_aa exiting 3 without its snapshot is a broken refusal, not
        # a publishable disputed hour: red with the capture's own stderr.
        idx_guard = self.block.index(
            "fetch_aa exited 3 without writing the disagreement snapshot")
        self.assertLess(
            idx_guard, self.block.index("exit 1", idx_guard))

    def test_the_disputed_hour_is_not_committed_in_the_capture_step(self):
        # #100 committed the stamp in this step so a later data/ restore
        # could not lose the window. #118 moved the commit DOWN: the
        # rendered gate decides moved vs unchanged first, and only what the
        # suite passed is committed. #143 moves the commit itself to the
        # write job: the capture step writes no commit here, and the
        # conditional adds live in the publish job's commit step.
        self.assertNotIn("git add data/aa-disagreement-snapshot.json",
                         self.block)
        commit = flattened(pub_step(self.wf, "Commit the capture")["run"])
        self.assertIn(
            "[ ! -f data/aa-disagreement-snapshot.json ] || "
            "git add data/aa-disagreement-snapshot.json", commit)
        self.assertIn(
            "[ ! -f data/aa-route-disagreement.txt ] || "
            "git add data/aa-route-disagreement.txt", commit)

    def test_a_recovered_capture_retires_the_stamp_and_the_snapshot(self):
        # rc == 0 with either window file tracked: remove BOTH from the
        # tree (so the rendered gate builds a clean page), mark the hour
        # retiring, and let the write job commit the removal -- a push lost
        # to the race concedes silently, and the next successful capture
        # retires the stamp again.
        self.assertIn('git ls-files --error-unmatch "$stamp"', self.block)
        self.assertIn(
            "git ls-files --error-unmatch data/aa-disagreement-snapshot.json",
            self.block)
        self.assertIn("git rm -q --ignore-unmatch", self.block)
        self.assertIn('echo "retire=true"', self.block)
        idx_rm = self.block.index("git rm -q --ignore-unmatch")
        self.assertLess(idx_rm, self.block.index('echo "retire=true"'))
        # The retirement commit itself is the write job's: not a word of it
        # lives in this step.
        self.assertNotIn("Route agreement restored", self.block)
        commit = flattened(pub_step(self.wf, "Commit the capture")["run"])
        self.assertIn("Route agreement restored; resume captures (issue #100)",
                      commit)
        self.assertIn("xargs git rm -q --ignore-unmatch", commit)

    def test_both_stamp_paths_ride_the_push_bundle(self):
        # The retirement commit rides the bundle with the data commit: it
        # lands when the push job lands, and a push lost to the race
        # concedes silently for the retirement too -- the next successful
        # capture retires the stamp again. Only the commit step's retire
        # slice is examined: it must hold the retirement commit and none of
        # the push machinery.
        commit = flattened(pub_step(self.wf, "Commit the capture")["run"])
        idx_ret = commit.index("xargs git rm -q --ignore-unmatch")
        idx_data = commit.index("cp -a")
        retire = commit[idx_ret:idx_data]

        self.assertIn("git commit -q -m "
                      "'Route agreement restored; resume captures "
                      "(issue #100)'", retire)
        self.assertNotIn("git push", retire)
        self.assertNotIn("HEAD:main", retire)

    def test_no_time_bound_remains_on_the_disagreement(self):
        # The banner is the alarm now: no stamp age, no red alarm wording.
        # The only corrupt-stamp red left names the BANNER's window start --
        # a non-numeric first line would misname the window, so the refresh
        # path validates it and reds (issue #118 review, 2026-10-02).
        self.assertNotIn("3*3600", self.block)
        self.assertNotIn("older than 3 h", self.block)
        self.assertIn("stamp is corrupt", self.block)
        idx_case = self.block.index("''|*[!0-9]*)")
        self.assertLess(idx_case,
                        self.block.index("exit 1 ;;", idx_case))
        self.assertLess(self.block.index('start="$(head -n 1 "$stamp")"'),
                        idx_case)

    def test_the_header_documents_the_disputed_publish(self):
        # The file's contract lives in its header; a reader must find the
        # exit-3 semantics there, not reconstruct them from the step.
        self.assertIn("EXIT 3 IS THE DISPUTED PUBLISH", self.header)
        self.assertIn("issue #118", self.header)
        self.assertIn("data/aa-disagreement-snapshot.json", self.header)
        self.assertIn("NO time bound", self.header)

    def test_the_commit_step_messages_the_disputed_publish(self):
        # A commit that adds the disagreement snapshot says so in its
        # subject and carries the capture's own divergence diagnostic from
        # the stamp -- never the differ's rendering, which compares the
        # last-good captures a window does not touch.
        run = flattened(pub_step(self.wf, "Commit the capture")["run"])
        self.assertIn(
            "git diff --cached --name-only | grep -q "
            "'^data/aa-disagreement-snapshot\\.json$'", run)
        self.assertIn(
            "Publish disputed capture: AA routes disagree (issue #118)", run)
        self.assertLess(
            run.index("sed -n '2,$p' data/aa-route-disagreement.txt"),
            run.index("git commit -F"))

    def test_every_message_branch_writes_the_file_the_commit_reads(self):
        # Review C1/I3 on PR #151: the differ branch of the message
        # selection appended its trailer to the payload copy while
        # `git commit -F` read the RUNNER_TEMP file -- nothing wrote it on
        # an ordinary moved-capture hour, and the workflow's primary
        # publishing path died at the commit, exit 128, with every
        # structural pin green. The pin follows the dataflow: all three
        # branches leave the commit's file written, no branch appends to
        # the payload copy, and the commit reads exactly that path.
        run = flattened(pub_step(self.wf, "Commit the capture")["run"])
        msg = '"${RUNNER_TEMP}/commit-msg.txt"'

        # The disputed branch writes it directly...
        idx_disputed = run.index("Publish disputed capture: AA routes disagree")
        self.assertLess(run.index(f"> {msg}", idx_disputed),
                        run.index("elif [ -f"))
        # ...the differ branch routes the payload message into it before
        # the trailer append...
        idx_differ = run.index('elif [ -f "${PAYLOAD}/commit-msg.txt" ]; then')
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

    def test_the_hub_ties_the_upload_and_the_ref_to_one_commit(self):
        # The ref must never name a page the hub does not serve, and the
        # tie is ENFORCED, not asserted: the upload and the ref move run
        # only when the payload page's own commit (`tip`, recorded by the
        # publish job) is still main's tip. When main has moved past it, a
        # newer run owns the tip and its hub job publishes - this run
        # concedes green before anything is uploaded or moved. The #74
        # gate then compares the published ref against that same `tip`.
        run = flattened(hub_step(self.wf, "Publish to docs-hub")["run"])

        idx_target = run.index('target="$(git -C "${scratch}" rev-parse FETCH_HEAD)"')
        idx_mine = run.index('mine="$(cat "${RUNNER_TEMP}/push-data/tip.txt")"')
        # The target is fetched before the tip is read: the tie compares a
        # fresh main against the page's own commit.
        self.assertLess(idx_target, idx_mine)
        idx_tie = run.index('[ "$mine" != "$target" ]; then')
        idx_concede = run.index("Lost the race")
        # The tie's concede leaves GREEN through its own exit 0 before the
        # #74 gate: a superseded hour must neither publish nor go red.
        idx_exit = run.index("exit 0", idx_concede)
        idx_gate = run.index("refs/heads/published:refs/remotes/origin/published")
        self.assertLess(idx_exit, idx_gate)
        idx_upload = run.index("https://docs.nitjsefni.eu/api/publish")
        idx_ref = run.index('-f sha="$mine"')
        self.assertLess(idx_mine, idx_tie)
        self.assertLess(idx_tie, idx_concede)
        self.assertLess(idx_concede, idx_gate)
        self.assertLess(idx_gate, idx_upload)
        self.assertLess(idx_upload, idx_ref)
        # The ref move names `mine`, the page's own commit.
        self.assertNotIn('-f sha="$target"', run)

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

    def test_the_ref_move_only_names_a_commit_on_mains_history(self):
        # Issue #152's gate is structural now: the ref target is main's tip
        # fresh-fetched AFTER the push job's turn (the landed tip IS main's
        # tip on a landing; the concession path publishes nothing), so it
        # cannot leave main's history, and the tie above ties the ref to
        # the page's own commit: the ref moves to `mine` (the publish
        # job's recorded tip), only while `mine` is still main's tip. The
        # pin holds the shape: target read from FETCH_HEAD, the tie's
        # concede before the #74 gate, the gate before the upload, and the
        # upload before a refs-API call naming `$mine`, never `$target`.
        raw = hub_step(self.wf, "Publish to docs-hub")["run"]
        run = flattened(raw)

        idx_target = run.index('target="$(git -C "${scratch}" rev-parse FETCH_HEAD)"')
        idx_concede = run.index("Lost the race")
        idx_upload = run.index("https://docs.nitjsefni.eu/api/publish")
        idx_get = run.index('gh api "repos/$REPO/git/refs/heads/published"',
                            idx_upload)
        self.assertLess(idx_target, idx_concede)
        self.assertLess(idx_concede, idx_upload)
        self.assertLess(idx_upload, idx_get)
        self.assertIn("Lost the race", run)


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
