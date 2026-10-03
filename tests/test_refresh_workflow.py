"""Structural pins on .github/workflows/refresh.yml.

The workflow publishes the live page hourly, and since issue #143 its write
side is a separate job: `refresh` (capture, rendered gate, rebuild, suite)
runs on a read-only token and leaves the commit payload as an artifact of its
own run; `publish` -- the workflow's only contents:write holder -- downloads
that artifact and commits and publishes it while running no repository code.
Its safety lives in the gating BETWEEN steps and BETWEEN jobs: what runs only
after the suite passed, what only when the commit actually landed, what heals
a stale publish. Those contracts are invisible to the Python suite until
something parses the YAML, so this file does -- structurally, on step shape
and on substrings that name the mechanism, never on line numbers or
whole-run-block equality that any reflow would break.
"""
import pathlib
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

    def test_workflow_permissions_floor_and_job_read_scope(self):
        # Issue #52 fold, narrowed by #143: the workflow-level floor is
        # contents: read, so a job added later without its own permissions
        # block inherits read instead of the repository default. The refresh
        # job DECLARES read: it runs the capture, third-party installs and
        # the suite, so nothing in it may ride a write token.
        self.assertEqual(self.wf.get("permissions"), {"contents": "read"})
        self.assertEqual(self.wf["jobs"]["refresh"]["permissions"],
                         {"contents": "read"})

    def test_only_the_publish_job_holds_contents_write(self):
        # Issue #143, the #134 tripwire applied here: the commit and the
        # docs-hub publish are the write side, and they run in the publish
        # job -- which consumes this same run's artifact, runs no repository
        # code, and is the only contents:write holder in the file.
        workflow = self.wf
        self.assertEqual(workflow.get("permissions"), {"contents": "read"})
        jobs = workflow["jobs"]
        assert "publish" in jobs, (
            "the data-only write job is missing from refresh.yml")
        for name, job in jobs.items():
            contents = (job.get("permissions") or {}).get("contents")
            if name == "publish":
                assert contents == "write", (
                    "publish is the workflow's only writer and must "
                    "declare it")
            else:
                assert contents != "write", (
                    f"{name} holds contents: write; only publish may")
        push = jobs["publish"]
        assert push["needs"] == "refresh", (
            "the payload is this run's own data: needs, not a workflow_run")
        assert not [s for s in push["steps"]
                    if s.get("uses", "").startswith("actions/checkout@")], (
            "publish runs no repository code: no checkout step")

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
        cond = self.wf["jobs"]["publish"]["if"]
        gate = pub_step(self.wf, "Publish to docs-hub")["if"]

        self.assertIn("needs.refresh.outputs.proceed == 'true'", cond)
        self.assertIn("steps.commit.outputs.publish == 'true'", gate)

    def test_the_publish_job_runs_no_repository_code(self):
        # The writer runs no checkout, no third-party install, no test
        # suite, and no script from the tree: its only inputs are the
        # artifact, git plumbing, and curl/jq/gh against the pinned hub
        # host. Anything executed here would ride the write token.
        for s in self.wf["jobs"]["publish"]["steps"]:
            run = s.get("run", "")
            self.assertNotIn("python3", commands(run))
            self.assertNotIn("pip", commands(run))

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
        run = flattened(pub_step(self.wf, "Publish to docs-hub")["run"])

        self.assertLess(
            run.index("curl -fSs"), run.index("cat /tmp/publish-response.json"))
        self.assertLess(
            run.index("curl -fSs"),
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
        raw = pub_step(self.wf, "Publish to docs-hub")["run"]
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
        # this run's own HEAD, asks the compare API, whose status names the
        # TIP side relative to the BASE side. Only a tip that is AHEAD (a
        # newer run already published) aborts: green, exit 0, no upload, no
        # ref move. `behind` is the normal heal and publishes; a failed or
        # unrankable answer retries once and then publishes anyway behind a
        # warning, because availability of publish beats the residual
        # seconds-wide window. The newest run NEVER aborts, so within any
        # overlap the newest page always wins.
        run = flattened(pub_step(self.wf, "Publish to docs-hub")["run"])

        # The gate stands between the step's start and the upload: the
        # anonymous ref fetch and the compare call precede the upload, and
        # the abort leaves through exit 0 before anything is uploaded.
        self.assertLess(run.index("git fetch --depth=1 origin"),
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

    def test_the_commit_step_concedes_a_lost_push_race_instead_of_dying_red(self):
        # Issue 46: two same-group runs raced the push to main and the loser
        # died red on a non-fast-forward rejection. The loser must fetch the
        # moved main, rebase, and either push again or concede -- green, with
        # publish=false, because the concurrent run's capture stands and
        # publishing it is that run's job. The scratch checkout makes the
        # data push's two attempts four `HEAD:main` spellings across the
        # step: two belong to the retirement push, two to the data push.
        run = flattened(pub_step(self.wf, "Commit the capture")["run"])

        self.assertIn("git fetch --quiet origin main", run)
        self.assertIn("git rebase origin/main", run)
        # A conflict is the concurrent capture arriving first; the loser
        # aborts, says so in the summary, and exits 0 without publishing.
        self.assertIn("git rebase --abort", run)
        self.assertLess(run.index("git rebase --abort"),
                        run.index('echo "publish=false"'))
        self.assertIn("lost the race", run.lower())
        self.assertLess(run.rindex('echo "publish=false"'),
                        run.rindex("exit 0"))
        # Exactly two attempts on each push: the original and the
        # post-rebase retry, which is the final one -- a second rejection
        # fails the run red rather than looping.
        self.assertEqual(run.count("HEAD:main"), 4)

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
        # #143: the capture step no longer pushes -- the retirement leaves
        # as payload -- so no token env sits here. The tokens live on the
        # write side only: the publish job's commit step (push to main) and
        # publish step (docs-hub key, published-ref API).
        self.assertNotIn("GH_TOKEN", self.step.get("env", {}))
        commit = pub_step(self.wf, "Commit the capture")
        self.assertEqual(commit["env"]["GH_TOKEN"], "${{ github.token }}")
        self.assertEqual(commit["env"]["REPO"], "${{ github.repository }}")
        publish = pub_step(self.wf, "Publish to docs-hub")
        self.assertEqual(publish["env"]["DOCS_HUB_API_KEY"],
                         "${{ secrets.DOCS_HUB_API_KEY }}")

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

    def test_both_stamp_paths_retry_the_push_race_then_concede(self):
        # The retirement push keeps its own two-attempt race handling, and
        # its failures concede SILENTLY -- no summary line, no publish
        # verdict of its own: the next successful capture retires again.
        # Only its slice of the commit step's run block is examined, so the
        # data push's louder contract (pinned separately) cannot satisfy it.
        commit = flattened(pub_step(self.wf, "Commit the capture")["run"])
        idx_ret = commit.index("Route agreement restored")
        idx_data = commit.index("cp -a")
        retire = commit[idx_ret:idx_data]

        self.assertIn("git fetch --quiet origin main", retire)
        self.assertIn("git rebase origin/main", retire)
        self.assertIn("git rebase --abort", retire)
        self.assertIn("push origin HEAD:main || true", retire)
        self.assertNotIn("publish=false", retire)

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
