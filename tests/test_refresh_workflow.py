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

    def test_workflow_permissions_floor_and_job_write_scope(self):
        # Issue #52 fold: the workflow-level floor is contents: read, so a
        # job added later without its own permissions block inherits read
        # instead of the repository default; the refresh job alone elevates
        # to write, where its two pushes happen.
        self.assertEqual(self.wf.get("permissions"), {"contents": "read"})
        self.assertEqual(self.wf["jobs"]["refresh"]["permissions"],
                         {"contents": "write"})

    def test_publish_requires_proceed_and_the_commit_steps_publish_output(self):
        # A commit step can finish green WITHOUT a publishable state (a lost
        # push race concedes with exit 0), so the publish step must read the
        # commit step's own verdict, not just the capture gate.
        gate = step(self.wf, "Publish to docs-hub")["if"]

        self.assertIn("steps.capture.outputs.proceed == 'true'", gate)
        self.assertIn("steps.commit.outputs.publish == 'true'", gate)

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
        # in the tree -- the commit step's `git add data/ ...` would stage
        # them on a later heal run. The restore widens from the stamp file to
        # the directory, which also restores captured-at.txt: the stamp still
        # moves only when the data moves, and a quiet fetch still leaves the
        # tree clean.
        run = flattened(step(self.wf, "Did anything move?")["run"])

        self.assertIn("git checkout -- data/", run)
        self.assertNotIn("git checkout -- data/captured-at.txt", run)
        # The restore stands on the unchanged path: after the gate's answer,
        # before the heal gate's ref fetch.
        self.assertLess(run.index("git checkout -- data/"),
                        run.index("refs/heads/published"))

    def test_the_commit_step_restores_heads_page_when_the_capture_did_not_move(self):
        # Issue #94, second half: on a heal run the suite's rebuild is now
        # stamped with THIS run's github.sha (issue #92's env fix), while
        # HEAD's committed page carries the previous tip's sha -- the commit
        # a page lands in always postdates the stamp it carries -- so
        # committing the rebuilt page would be stamp-only churn. The commit
        # step must restore HEAD's page before `git add` whenever the capture
        # did not change and the run is not forced; a forced run may commit
        # stamp churn, accepted because force is manual and rare.
        s = step(self.wf, "Commit the capture")
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
            run.index("git add data/"))

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

    def test_the_publish_step_aborts_when_a_newer_run_already_published(self):
        # Issue 74: two overlapping runs can both reach the publish step, and
        # if the OLDER run's upload lands after the newer run's, the hub ends
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
        run = flattened(step(self.wf, "Publish to docs-hub")["run"])

        # The gate stands between the step's start and the upload: the
        # anonymous ref fetch and the compare call precede publish_docs.py,
        # and the abort leaves through exit 0 before anything is uploaded.
        self.assertLess(run.index("git fetch --depth=1 origin"),
                        run.index("publish_docs.py"))
        self.assertLess(
            run.index("refs/heads/published:refs/remotes/origin/published"),
            run.index("publish_docs.py"))
        self.assertLess(run.index("repos/$REPO/compare/"),
                        run.index("publish_docs.py"))
        self.assertLess(run.index("exit 0"), run.index("publish_docs.py"))
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
        # also fetches the hub's live page (the public /d/ route serves the
        # stored bytes verbatim) and compares it byte-for-byte against HEAD's
        # committed page. Divergence sets hub_stale, and so does a failed
        # fetch — same stance as the ref fetch: an extra republish costs one
        # hub version, a real outage fails red at the publish step.
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


class RouteDisagreementSkipTests(unittest.TestCase):
    """Issue #100: the capture's route-disagreement refusal (exit 3) must not
    fail the hour while AA's cache-stagger window is young, but a window that
    outlasts three hours must fail red again. The Capture step is pinned
    here on mechanism words and ordering -- substrings, never line numbers
    or whole-block equality, in this file's existing style.

    The three-colour contract: exit 0 proceeds as before (retiring any stamp
    a skipped stretch left behind), exit 3 green-skips behind a committed
    stamp, every other code re-raises its own stderr and fails red exactly
    as before.
    """

    def setUp(self):
        self.wf = load()
        self.step = step(self.wf, "Capture the leaderboard")
        self.block = flattened(self.step["run"])

    def test_the_fetch_runs_behind_an_rc_trap_so_the_step_can_classify_it(self):
        # The capture's stderr is parked in a file because every branch
        # below needs it: the stamp carries it, the red paths re-emit it.
        for piece in ("set +e",
                      "python3 scripts/fetch_aa.py 2> /tmp/fetch-err.txt",
                      "rc=$?",
                      "set -e",
                      "stamp=data/aa-route-disagreement.txt",
                      "alert_after=$((3*3600))",
                      "now=$(date -u +%s)"):
            self.assertIn(piece, self.block)

    def test_the_capture_step_holds_the_push_credentials(self):
        # The stamp commit pushes from THIS step, so the token sits here --
        # the same explicit env the commit and publish steps carry.
        self.assertEqual(self.step.get("env", {}).get("GH_TOKEN"),
                         "${{ github.token }}")
        self.assertEqual(self.step.get("env", {}).get("REPO"),
                         "${{ github.repository }}")

    def test_the_three_exit_colours_are_classified_in_order(self):
        # Recovery (rc 0) stands first, then the skip (rc 3), then the
        # designed red re-raise for everything else.
        self.assertLess(self.block.index('[ "$rc" -eq 0 ]'),
                        self.block.index('[ "$rc" -eq 3 ]'))
        self.assertLess(self.block.index('[ "$rc" -eq 3 ]'),
                        self.block.index('exit "$rc"'))
        self.assertIn("cat /tmp/fetch-err.txt >&2", self.block)

    def test_a_first_refusal_writes_commits_and_pushes_the_stamp(self):
        # The stamp is the window's start epoch (line 1) plus the capture's
        # own diagnostic (line 2+); it is added by EXPLICIT path and pushed
        # inside this step, so no later data/ restore can see it
        # uncommitted.
        idx_write = self.block.index('> "$stamp"')
        idx_add = self.block.index("git add data/aa-route-disagreement.txt")
        idx_commit = self.block.index(
            "AA routes disagree; skipping this hour (issue #100)")
        idx_push = self.block.index("push_head || true")

        self.assertLess(idx_write, idx_add)
        self.assertLess(idx_add, idx_commit)
        self.assertLess(idx_commit, idx_push)
        # Both stamp contents, in order: the epoch, then the capture stderr.
        idx_epoch = self.block.index("echo \"$now\"")
        self.assertLess(idx_epoch,
                        self.block.index("cat /tmp/fetch-err.txt", idx_epoch))
        self.assertIn("} > \"$stamp\"", self.block)

    def test_a_young_window_skips_green_without_touching_anything(self):
        # The stamp-exists branch stands BEFORE the write (a fresh stamp is
        # never rewritten), and the skip is green: the branch's own summary
        # line exits 0 BEFORE the first-refusal write can run, so flipping
        # the skip's exit fails here rather than being satisfied by a later
        # branch's exit 0 (verified against that mutant).
        idx_f = self.block.index('[ -f "$stamp" ]')
        idx_summary = self.block.index(
            "skipping this hour; fails red past 3 h (issue #100)", idx_f)
        idx_green = self.block.index("exit 0", idx_summary)

        self.assertLess(idx_f, self.block.index('> "$stamp"'))
        self.assertIn("AA's routes disagree (window began", self.block)
        self.assertLess(idx_summary, idx_green)
        self.assertLess(idx_green, self.block.index('> "$stamp"'))

    def test_a_window_older_than_three_hours_fails_red(self):
        idx_compare = self.block.index('[ "$((now - start))" -gt "$alert_after" ]')
        idx_alarm = self.block.index("Re-read artificialanalysis.ai by hand")

        self.assertEqual(self.block.count("3*3600"), 1)
        # The alarm names the window start, re-emits the capture's own
        # stderr, and fails the step -- the exit 1 pinned HERE, after the
        # alarm's own words, so flipping the alarm green fails this pin even
        # though the corrupt branch still carries one.
        self.assertLess(idx_compare,
                        self.block.index('date -u -d "@$start"', idx_compare))
        self.assertLess(
            idx_alarm, self.block.index("cat /tmp/fetch-err.txt >&2",
                                        idx_alarm))
        self.assertLess(idx_alarm, self.block.index("exit 1", idx_alarm))

    def test_a_corrupt_stamp_fails_red_rather_than_skipping(self):
        # A stamp whose first line is empty or non-numeric cannot date the
        # window, so the alarm's premise is unprovable -- red, not a guess.
        # The pin runs case-pattern -> the corrupt echo -> that branch's OWN
        # `exit 1 ;;`: a bare pattern-before-any-exit-1 pin survives turning
        # this branch green, because the alarm's exit 1 sits later in the
        # block and satisfies it anyway (verified against that mutant).
        self.assertIn("start=$(head -n 1 \"$stamp\")", self.block)
        idx_case = self.block.index("''|*[!0-9]*")
        idx_echo = self.block.index("stamp is corrupt")

        self.assertLess(idx_case, idx_echo)
        self.assertLess(idx_echo, self.block.index("exit 1 ;;", idx_echo))

    def test_a_recovered_capture_retires_the_stamp_and_stays_green(self):
        # rc == 0 with a tracked stamp: delete, commit the retirement, push.
        # A push lost to the race concedes silently -- the next successful
        # capture retires the stamp again.
        self.assertIn('git ls-files --error-unmatch "$stamp"', self.block)
        self.assertIn("git rm -q", self.block)
        self.assertIn("Route agreement restored; resume captures (issue #100)",
                      self.block)
        idx_rm = self.block.index("git rm -q")
        self.assertLess(idx_rm, self.block.index(
            "Route agreement restored; resume captures (issue #100)"))
        self.assertIn("if push_head;", self.block)

    def test_both_stamp_paths_retry_the_push_race_then_concede(self):
        # The retry is one shared helper: push, and on a rejection fetch +
        # rebase + push once more, with a conflict conceding (return 1).
        # Both the stamp-write and the stamp-retire paths go through it, and
        # both pushes live ONLY inside the helper.
        self.assertIn("push_head () {", self.block)
        # The rebase carries the inline identity (this step never git-config's
        # the checkout), so the pin is on the rebase itself.
        self.assertIn("rebase origin/main", self.block)
        self.assertIn("git rebase --abort", self.block)
        self.assertEqual(self.block.count("HEAD:main"), 2)
        self.assertIn("push_head || true", self.block)
        self.assertIn("if push_head;", self.block)

    def test_the_header_documents_the_third_deliberate_failure_mode(self):
        # The file's contract lives in its header; a reader must find the
        # exit-3 semantics there, not reconstruct them from the step.
        raw = WORKFLOW.read_text(encoding="utf-8")
        head = raw.split("\njobs:", 1)[0]

        self.assertIn("EXIT 3 IS THE ONE DELIBERATE NON-RED", head)
        self.assertIn("issue #100", head)
        self.assertIn("data/aa-route-disagreement.txt", head)
        self.assertIn("older than 3 h", head)


class ForceOverrideTests(unittest.TestCase):
    """Issue #103: a `force: true` dispatch must not override a refused
    capture. Run 36746895412 dispatched force minutes after run 36746060709
    had stamped a live route-disagreement window: the Capture step
    green-skipped, but "Did anything move?" derived `proceed` from the force
    input alone, and the run rebuilt and published HEAD's stale captures as
    "AA capture unchanged". The Capture step now publishes its verdict as a
    `captured` step output, and the force term in the proceed decision --
    and the quiet line -- is gated on it. Pins on substrings and ordering
    over the flattened blocks, never line numbers, in this file's style.
    """

    def setUp(self):
        self.wf = load()
        self.capture_step = step(self.wf, "Capture the leaderboard")
        self.capture = flattened(self.capture_step["run"])
        self.moved = flattened(step(self.wf, "Did anything move?")["run"])
        self.header = WORKFLOW.read_text(
            encoding="utf-8").split("\njobs:", 1)[0]

    def test_the_capture_step_declares_the_id_the_force_gate_reads(self):
        # "Did anything move?" reads the Capture step's verdict through the
        # step id, so the id must be pinned to exactly the name the
        # expression spells.
        self.assertEqual(self.capture_step.get("id"), "fetch")

    def test_captured_is_set_on_every_green_path_before_its_exit(self):
        # Three green paths leave this step, and each must have declared
        # its verdict before exiting, or the force gate below reads an
        # empty output and honors force against a refused capture.
        #
        # rc == 0: captured=true, and it is the branch's FIRST statement --
        # the verdict exists even when there was no stamp to retire.
        # (The between-slice is comment-stripped, so this pin fails if any
        # executable statement precedes the echo.)
        raw = self.capture_step["run"]
        opener = 'if [ "$rc" -eq 0 ]; then'
        idx_open = raw.index(opener)
        idx_true = raw.index('echo "captured=true"', idx_open)
        between = raw[idx_open + len(opener):idx_true]
        self.assertEqual(commands(between), "")
        self.assertLess(idx_true, raw.index("exit 0", idx_true))

        # Both rc == 3 green paths set captured=false before they exit.
        self.assertEqual(self.capture.count('echo "captured=false"'), 2)

        # The young-window skip: the verdict precedes the path's summary
        # line and its exit 0, and the exit precedes the first-refusal
        # write (the skip must never fall through into it).
        idx_f = self.capture.index('[ -f "$stamp" ]')
        idx_false = self.capture.index('echo "captured=false"', idx_f)
        idx_summary = self.capture.index(
            "skipping this hour; fails red past 3 h (issue #100)", idx_false)
        self.assertLess(idx_false, idx_summary)
        idx_green = self.capture.index("exit 0", idx_summary)
        self.assertLess(idx_summary, idx_green)
        self.assertLess(idx_green, self.capture.index('> "$stamp"'))

        # The first refusal: the verdict precedes the stamp write, the
        # push, and the path's own summary + exit.
        idx_false2 = self.capture.index('echo "captured=false"',
                                        idx_false + 1)
        self.assertLess(idx_false2, self.capture.index('> "$stamp"'))
        self.assertLess(idx_false2, self.capture.index("push_head || true"))
        idx_summary2 = self.capture.index(
            "skipping this hour; fails red past 3 h (issue #100)", idx_false2)
        self.assertLess(idx_false2, idx_summary2)
        self.assertLess(idx_summary2, self.capture.index("exit 0",
                                                         idx_summary2))

    def test_the_captured_verdict_travels_through_env_not_template(self):
        # zizmor's template-injection audit fails any direct `${{ }}` into
        # `run:` text (issue #103's CI gate), so the Capture step's verdict
        # reaches this step's shell only through the env mapping -- never
        # interpolated inline, wherever the value actually comes from (our
        # own step output; the env form is the sanctioned convention).
        self.assertEqual(
            step(self.wf, "Did anything move?")["env"]["CAPTURED"],
            "${{ steps.fetch.outputs.captured }}")
        self.assertNotIn("steps.fetch.outputs.captured", self.moved)

    def test_force_alone_cannot_set_proceed_behind_a_refused_capture(self):
        # THE pin that fails on current main: the proceed decision gates
        # the force term on the Capture step's verdict. `!= "false"` (not
        # `= "true"`) keeps force honored whenever the verdict is absent --
        # the safe default for any run shape older than the output -- so
        # refused (false) is the only value that vetoes it, and the brace
        # group keeps that veto scoped to the force term alone (changed and
        # the heal flags are untouched by it). The verdict arrives as the
        # env var $CAPTURED, the zizmor-required form (see the env-mapping
        # pin above).
        self.assertIn(
            '{ [ "$CAPTURED" != "false" ] '
            "&& [ \"${{ inputs.force }}\" = 'true' ]; }",
            self.moved)

    def test_the_quiet_line_carries_the_same_refusal_guard(self):
        # A skipped hour's summary already carries the Capture step's own
        # skip line, so the quiet line must never additionally claim "AA
        # capture unchanged" -- a forced-and-refused hour used to wear that
        # label. Same guard, same `!= "false"` spelling, on the quiet
        # line's condition -- pinned with the flag it feeds, the substring
        # that distinguishes it from the proceed decision (whose guard is
        # followed by the force term, not live_stale). $CAPTURED is the
        # zizmor-required env form of the verdict (see the env-mapping pin).
        self.assertIn(
            '[ "$CAPTURED" != "false" ] && [ "$live_stale" = false ]',
            self.moved)

    def test_an_ignored_force_is_reported_in_the_summary(self):
        # The refused-and-forced hour must be explained, not silent: its
        # own summary line stands immediately before the proceed decision,
        # names force, names the refusal, and names the issue. The verdict
        # arrives as the env var $CAPTURED, the zizmor-required form (see
        # the env-mapping pin).
        self.assertIn(
            "[ \"$CAPTURED\" = false ] "
            "&& [ \"${{ inputs.force }}\" = 'true' ]; then "
            "echo 'Force dispatch ignored:",
            self.moved)
        self.assertIn("the capture was refused this hour", self.moved)
        self.assertIn("issue #103", self.moved)
        # It is the last word before the decision: nothing executes between
        # the summary and the proceed-if it explains.
        idx = self.moved.index('[ "$CAPTURED" = false ]')
        self.assertLess(idx, self.moved.index('[ "$changed" = true ]'))

    def test_the_header_documents_force_terminality_on_a_skipped_hour(self):
        # The file's contract lives in its header (same pin shape as
        # RouteDisagreementSkipTests's header test): the force-input
        # terminality of a green-skipped hour is stated where the exit-3
        # semantics are, not reconstructed from the steps.
        self.assertIn("issue #103", self.header)
        self.assertIn("force", self.header.lower())
        self.assertIn("terminal", self.header.lower())
        self.assertIn("3 h red bound", self.header)
