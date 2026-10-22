"""Tripwires for the workflow catalogue.

The codeql-action coupling (issue #45) and the job-ceiling invariant
(issue #52) live here: contracts that span the workflows directory, not one
file's step gating. github/codeql-action/init and
github/codeql-action/analyze must run the same
version inside one workflow run: the action records its version at init and
refuses a later step at a different one — "Loaded a configuration file for
version 'X', but running version 'Y'" — which fails every CodeQL run of the
tree at SARIF processing. Dependabot names the two subpaths as separate
dependencies, so ungrouped it files one half-bump per pin and every
action-pin bump went red (12 of 13 failed codeql push runs were on
dependabot/* branches). The dependabot.yml groups block keeps the pins in one
atomic PR; these tests are the in-tree layer that fails if a single-pin bump
ever lands, and that fails loudly if the group is ever removed. The ceiling
tripwire pins that every job across .github/workflows/*.yml declares
timeout-minutes, so a new job cannot silently hold GitHub's 6-hour default.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

CODEQL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "codeql.yml"
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"
PR_GATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-gate.yml"
TESTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))

# `uses: github/codeql-action/<step>@<40-hex sha>  # vX.Y.Z`
_PIN = re.compile(
    r"uses:\s*(?P<action>[^\s@]+)@(?P<revision>\S+)"
    r"(?:\s+#\s*(?P<comment>\S+))?"
)

# The template contract the pinned gate enforces, mirrored for the pin below.
# Upstream pr-gate's template_rules (scripts/ci/pr_body.py at
# 441f855e54f4f6c98709152f2d2542031dc82f03) refuses a consumer template in
# which any `##` section lacks a Required/Conditional/Optional-tagged
# instruction comment between its heading and the next: every pull-request
# run of the gate then dies on the refusal (exit 1) instead of gating
# anything. The two regexes are copied from that file so this test judges
# the same shapes the gate does, and the workflow's SHA pin freezes the
# parser they mirror. Like test_gate_base_freshness.py's upstream mirroring,
# the duplicated lines are kept as written and duplicate-code stays scoped
# to this block.
_TEMPLATE_HEADING = re.compile(r"^##[ \t]+(?P<text>.+?)[ \t]*$", re.MULTILINE)
_TEMPLATE_TAG = re.compile(
    r"<!--\s*(?P<tag>required|conditional|optional)\b", re.IGNORECASE)


def _pins(workflow: str, prefix: str = "github/codeql-action/"):
    return [(action.removeprefix(prefix), revision, comment)
            for action, revision, comment in _PIN.findall(workflow)
            if action.startswith(prefix)]


def _uses_references(workflow_text: str) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "uses" and isinstance(child, str):
                    action, _, revision = child.partition("@")
                    if action and revision:
                        references.append((action, revision))
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(yaml.safe_load(workflow_text) or {})
    return references


def test_action_revisions_agree_across_workflows():
    def composed_references(node):
        pairs = set()
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value or []:
                if (isinstance(key, yaml.ScalarNode) and key.value == "uses"
                        and isinstance(value, yaml.ScalarNode)
                        and value.tag == "tag:yaml.org,2002:str"):
                    action, _, revision = value.value.partition("@")
                    if action and revision:
                        pairs.add((action, revision))
                pairs.update(composed_references(value))
        elif isinstance(node, yaml.SequenceNode):
            for value in node.value or []:
                pairs.update(composed_references(value))
        return pairs

    references: dict[str, list[tuple[str, str]]] = {}
    for path in WORKFLOWS:
        workflow = path.read_text(encoding="utf-8")
        pairs = _uses_references(workflow)
        assert set(pairs) == composed_references(yaml.compose(workflow)), (
            f"{path.name}: parsed uses references disagree with the YAML tree")
        for action, revision in pairs:
            references.setdefault(action, []).append((path.name, revision))
    for action, occurrences in references.items():
        first_path, expected = occurrences[0]
        for path, actual in occurrences[1:]:
            assert actual == expected, (
                f"{action}: {path} uses {actual}, but {first_path} uses {expected}")


def test_codeql_action_pins_share_one_sha():
    pins = _pins(CODEQL_WORKFLOW.read_text(encoding="utf-8"))
    steps = {pin[0] for pin in pins}
    # the oracle must be live: a refactor that renames the steps or the
    # workflow must not silence this file into a vacuous pass
    assert {"init", "analyze"} <= steps, f"missing pins: {sorted(steps)}"
    shas = {pin[1] for pin in pins}
    assert len(shas) == 1, (
        "codeql-action pins disagree — init and analyze must run the same "
        "version or every CodeQL run fails at SARIF processing: "
        f"{sorted(shas)}"
    )


def test_dependabot_groups_action_updates_into_one_pr():
    text = DEPENDABOT.read_text(encoding="utf-8")
    entries = text.split("package-ecosystem:")
    actions = [e for e in entries if e.lstrip().startswith("github-actions")]
    assert len(actions) == 1, (
        "expected exactly one github-actions update entry"
    )
    assert re.search(r"^ {4}groups:", actions[0], re.M), (
        "the github-actions entry must group its updates — ungrouped, "
        "Dependabot files one half-bump PR per codeql-action pin"
    )
    # the group only bundles VERSION updates; flipped to security-updates it
    # never applies to the regular weekly bump and the half-bumps return
    assert re.search(r"^ {8}applies-to: version-updates$", actions[0], re.M), (
        "the group must apply to version-updates"
    )
    assert re.search(r'^\s+- "\*"$', actions[0], re.M), (
        "the group must match every action so init and analyze move together"
    )


def test_hash_pinned_requirements_name_each_version_only_once():
    """A comment match hides hashes from Dependabot's bump (issue #300)."""
    candidates = [
        path for path in REPO_ROOT.glob("requirements*.txt")
        if "--hash=sha256:" in path.read_text(encoding="utf-8")
    ]
    assert candidates, "no hash-pinned requirements files found"
    declaration = (
        r"(?<![\w.\-])(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
        r"(?![\w.\-])\s*(?:\[\s*[A-Za-z0-9._-]+"
        r"(?:\s*,\s*[A-Za-z0-9._-]+)*\s*\])?\s*==\s*[0-9][^\s\\]*")
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        pinned = list(re.finditer(
            rf"^[ \t]*{declaration}[ \t]*\\\r?\n[ \t]*--hash=",
            text, re.MULTILINE))
        assert pinned, f"{path.name}: no hash-carrying declaration found"
        names = [match.group("name").lower()
                 for match in re.finditer(declaration, text)]
        for match in pinned:
            name = match.group("name").lower()
            assert names.count(name) == 1, (
                f"{path.name}: a shadow declaration for {name}, possibly in a "
                "comment with different spacing, can be matched first by "
                "Dependabot's declaration scan; that match carries no hashes, "
                "so the bump leaves the old digests behind and the "
                "--require-hashes install fails")


def test_every_job_declares_timeout_minutes():
    # Issue #52: a hung job fails in its declared ceiling instead of holding
    # GitHub's 6-hour default. The invariant rides on the whole catalogue —
    # a new workflow or job starts with it, and dropping the declaration
    # from an existing job fails here rather than in a 6-hour hang.
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (workflow.get("jobs") or {}).items():
            if "steps" not in job:
                # A reusable-workflow call carries no steps and no
                # timeout-minutes of its own -- GitHub's schema has
                # neither on a `uses:` job. The ceiling that governs its
                # runtime is the callee's, and the callee's jobs are
                # pinned by this same loop over their own file.
                continue
            assert "timeout-minutes" in job, (
                f"{path.name}: job {name!r} declares no timeout-minutes"
            )


def test_coverage_job_installs_chromium_through_the_digest_gate():
    # Issue #51: reverting this step to a bare `playwright install` unwires the digest gate.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    [chromium] = [s for s in workflow["jobs"]["coverage"]["steps"]
                  if s.get("name") == "Install Chromium for playwright"]
    assert chromium["run"] == "python3 scripts/ci/install_chromium.py"


def test_chromium_debs_cache_is_restore_only_in_coverage_and_shared():
    tests = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    refresh = yaml.safe_load((REPO_ROOT / ".github" / "workflows" /
                              "refresh.yml").read_text(encoding="utf-8"))
    steps = tests["jobs"]["coverage"]["steps"]
    [cache] = [entry for entry in steps
               if entry.get("name") == "Cache Chromium dependency debs"]
    assert cache["uses"].split("@", 1)[0] == "actions/cache/restore"
    [producer] = [entry for entry in refresh["jobs"]["refresh"]["steps"]
                  if entry.get("name") == cache["name"]]
    for field in ("path", "key", "restore-keys"):
        assert cache["with"][field] == producer["with"][field]
    chromium = next(entry for entry in steps
                    if entry.get("name") == "Install Chromium for playwright")
    assert steps.index(cache) < steps.index(chromium)
    assert "if" not in cache


def test_instruction_budgets_gate_runs_only_in_the_coverage_job():
    # Issue #110: the instruction-count gate needs valgrind and four
    # callgrind runs, so it must never appear in a matrix cell (three
    # OSes would triple the install and the cells' 20-minute ceiling is
    # standing). Its only CI surface is the coverage job, conditional on
    # the pytest step like every gate there, invoking the gate script.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    for name, job in workflow["jobs"].items():
        named = [s for s in job.get("steps", [])
                 if s.get("name") == "Instruction budgets gate"]
        if name != "coverage":
            assert not named, (
                f"{name} must not run the instruction budgets gate")
            continue
        [gate] = named
        assert "instruction_budgets.py" in gate["run"], gate["run"]
        assert gate.get("if") is not None and "pytest" in gate["if"], (
            "the gate is conditional on the pytest step, like every gate "
            "in this job")


def test_page_job_runs_the_committed_page_check():
    # Issue #105: the page job invokes the committed-page check through
    # its script and requests only contents: read. Check the invocation
    # and the job's declared permissions at this CI surface.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["page"]
    [check] = [s for s in job["steps"]
               if s.get("name") == "Check the committed page"]
    assert check["run"] == "python3 scripts/ci/check_committed_page.py"
    assert job["permissions"] == {"contents": "read"}


def test_no_job_in_tests_workflow_holds_contents_write():
    # Issues #134 and #133 part 2b: the coverage job runs the suite,
    # installs unhashed third-party dependencies and downloads a browser,
    # so nothing here may hold contents: write. The raise leaves `coverage`
    # as the ratchet-data artifact for the top-level ratchet-push workflow,
    # whose own job is the writer; this workflow declares no writer at all.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    assert workflow.get("permissions") == {"contents": "read"}, (
        "the workflow-level floor must stay contents: read — a job "
        "without its own permissions block inherits it, so raising the "
        "default raises every job at once")
    jobs = workflow["jobs"]
    for name, job in jobs.items():
        contents = (job.get("permissions") or {}).get("contents")
        assert contents != "write", (
            f"{name} holds contents: write; the ratchet raise lands "
            "through the top-level ratchet-push workflow")


def test_diff_coverage_job_is_pull_request_only_and_read_only():
    # Issue #126: the patch-coverage job runs the diff against the exact
    # tree coverage measured, on pull requests only, and holds read-only
    # credentials — the rendered comment travels as an artifact to the
    # trusted workflow_run poster, so this job never needs conversation
    # write.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["diff-coverage"]
    assert "pull_request" in job["if"], job["if"]
    assert "needs.coverage.result == 'success'" in job["if"], job["if"]
    # YAML reads the scalar `needs: coverage` as a string, not a list.
    assert job["needs"] in ("coverage", ["coverage"]), job["needs"]
    assert job["permissions"] == {"contents": "read"}


def test_no_job_that_checks_out_the_tree_holds_conversation_write():
    # Issue #126: a job that checks out the tree never carries a
    # conversation-write token. The only writers are the coverage poster,
    # the claim action (issue #161; Nitjsefnie-Actions/claim#153 — a /claim on
    # a pull request 403s without the grant), and the pr-gate admission
    # action (issue #166 — it comments on, closes and reopens pull requests
    # through the API and reads the template at the base SHA; no checkout).
    # Every job in the catalogue with an actions/checkout step is
    # scanned, so a future job cannot quietly grow pull-requests: write.
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (workflow.get("jobs") or {}).items():
            checks_out = any(
                "uses" in step and step["uses"].startswith("actions/checkout@")
                for step in job.get("steps", []))
            requested = (job.get("permissions")
                         or workflow.get("permissions") or {})
            pull_write = requested.get("pull-requests") == "write"
            if checks_out:
                assert not pull_write, (
                    f"{path.name}: job {name!r} checks out the tree and "
                    "holds pull-requests: write")
            elif pull_write:
                assert path.name in (
                    "claim.yml", "coverage-comment.yml", "pr-gate.yml",
                ), (
                    f"{path.name}: job {name!r} holds pull-requests: write "
                    "but only the coverage poster, the claim action and the "
                    "pr-gate action may")


def test_coverage_comment_workflow_never_executes_the_tree():
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "coverage-comment.yml")
        .read_text(encoding="utf-8"))
    # The trusted half: triggered only by the ci-gate workflow completing
    # (tests.yml is a workflow_call callee since #133 and produces no run
    # of its own on a pull request; the run carrying the
    # diff-coverage-comment artifact is ci-gate's), filtered to its
    # pull_request runs, and it checks out nothing — the only thing
    # crossing from the pull request is the TEXT of a comment.
    assert list(workflow[True]) == ["workflow_run"], workflow.get("on")
    assert workflow[True]["workflow_run"]["workflows"] == ["ci gate"]
    [job] = workflow["jobs"].values()
    assert "github.event.workflow_run.event == 'pull_request'" in job["if"]
    # The write lives at workflow level: the single job inherits it.
    assert workflow["permissions"] == {
        "pull-requests": "write", "actions": "read", "checks": "write"}


def test_coverage_job_is_unconditional_in_tests_workflow():
    # The comment workflow keys its missing-artifact verdict on the RUN
    # conclusion plus the tests leg's own conclusion (the mark-missing
    # step reads the run's jobs list): a successful run whose tests leg
    # skipped is ci-gate's narrowing and goes neutral; every other
    # missing-artifact shape stays a failure. The coverage JOB itself
    # stays unconditional inside its callee — the narrowing lives on the
    # caller's leg conditions — and this pin fails if a skip condition
    # ever lands on the coverage job itself, which would move the
    # decision the mark-missing step cannot see.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    assert "if" not in workflow["jobs"]["coverage"], (
        "the coverage job grew a skip condition; the comment workflow's "
        "mark-missing step reads the tests leg's conclusion, not this "
        "job's")


def test_the_comment_artifact_name_spans_both_workflows():
    # One artifact carries the rendered comment from the producer to the
    # poster; the two sides name it independently, so the shared literal is
    # pinned across the pair rather than per file.
    tests = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    comment = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "coverage-comment.yml")
        .read_text(encoding="utf-8"))
    [upload] = [s for s in tests["jobs"]["diff-coverage"]["steps"]
                if s.get("name") == "Upload the comment for the trusted "
                                    "commenter"]
    [download] = [s for s in comment["jobs"]["comment"]["steps"]
                  if s.get("name") == "Download the comment artifact"]
    assert upload["with"]["name"] == download["with"]["name"]


def test_coverage_job_collects_its_measured_subprocesses():
    # The patch-coverage reporter's CLI contract tests run the script as a
    # real child interpreter, which the outer collector cannot trace. The
    # job must therefore start child collectors (COVERAGE_PROCESS_START
    # naming the committed children config), keep one absolute data file
    # (children parallel-suffix it in place), and combine the sidecars
    # before any report reads a total — dropping any leg shrinks the
    # measured CLI and the ratchet reads a false regression.
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    coverage = workflow["jobs"]["coverage"]
    assert coverage["env"]["COVERAGE_FILE"] == (
        "${{ github.workspace }}/.coverage")
    [run_tests] = [s for s in coverage["steps"]
                   if s.get("name") == "Run tests"]
    assert run_tests["env"]["COVERAGE_MEASURE_CHILDREN_RC"] == (
        "${{ github.workspace }}/.github/coverage-children.rc")
    [summary] = [s for s in coverage["steps"]
                 if s.get("name") == "Coverage summary"]
    combine_first = summary["run"].splitlines()
    # The combine line precedes the first report in the same step.
    combine_at = next(i for i, line in enumerate(combine_first)
                      if "coverage combine" in line)
    report_at = next(i for i, line in enumerate(combine_first)
                     if "coverage report" in line)
    assert combine_at < report_at
    # The children config bounds what a child records to the reporter.
    rc = (REPO_ROOT / ".github" / "coverage-children.rc").read_text(
        encoding="utf-8")
    assert "[run]" in rc and "include = */scripts/ci/diff_coverage.py" in rc
    assert "parallel = True" in rc


def test_pr_gate_template_satisfies_the_gate_contract():
    # Issue #166: the gate reads this template at the pull request's base
    # SHA, so a template the parser refuses turns every pull-request run of
    # the gate into an exit-1 refusal — the gate's first act must never be
    # failing on every PR. Judged with the parser shapes copied at the top
    # of this file: every `##` section carries a tagged instruction comment,
    # names are unique (upstream keys its rules by casefolded name, so a
    # duplicate would silently shadow), the two content-audited sections sit
    # under the audited keys, and Footer is optional (a pull request no AI
    # model touched drops it) and defined last — the gate's footer rule
    # accepts it only as the body's final section.
    template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
        encoding="utf-8")
    headings = list(_TEMPLATE_HEADING.finditer(template))
    assert headings, "template defines no sections"
    rules = {}
    for index, heading in enumerate(headings):
        name = " ".join(heading.group("text").split())
        end = (headings[index + 1].start()
               if index + 1 < len(headings) else len(template))
        tag = _TEMPLATE_TAG.search(template[heading.end():end])
        assert tag is not None, (
            f'template section "{name}" carries no Required/Conditional/'
            'Optional-tagged instruction comment')
        assert name.casefold() not in rules, (
            f'template section "{name}" is defined twice')
        rules[name.casefold()] = (tag.group("tag").casefold(), index)
    assert "footer" in rules, sorted(rules)
    assert "bugs discovered" in rules, sorted(rules)
    assert rules["footer"][0] == "optional", rules["footer"]
    assert rules["footer"][1] == len(rules) - 1, rules["footer"]


def test_valgrind_cache_is_restore_only_before_the_instruction_gate():
    workflow = yaml.safe_load(TESTS_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["coverage"]["steps"]
    [cache] = [entry for entry in steps
               if entry.get("name") == "Cache valgrind dependency debs"]
    assert cache["uses"].split("@", 1)[0] == "actions/cache/restore"
    assert not [entry for entry in steps
                if entry.get("uses", "").split("@", 1)[0] == "actions/cache/save"]
    [gate] = [entry for entry in steps if entry.get("name") == "Instruction budgets gate"]
    assert steps.index(cache) < steps.index(gate)
    assert cache["if"] == gate["if"]
    lines = gate["run"].splitlines()
    assert lines == ["python3 scripts/ci/install_valgrind.py", "set -o pipefail",
                     'python3 scripts/ci/instruction_budgets.py | tee -a "$GITHUB_STEP_SUMMARY"']


def test_refresh_valgrind_cache_saves_only_after_a_gated_repair():
    workflow = yaml.safe_load((REPO_ROOT / '.github' / 'workflows' /
                               'refresh.yml').read_text(encoding='utf-8'))
    steps = workflow['jobs']['refresh']['steps']
    [restore] = [entry for entry in steps if entry.get('name') == 'Cache valgrind dependency debs']
    [install] = [entry for entry in steps if entry.get('name') == 'Install valgrind']
    [save] = [entry for entry in steps if entry.get('name') == 'Save valgrind dependency debs']
    assert restore['uses'].split('@', 1)[0] == 'actions/cache/restore'
    assert save['uses'].split('@', 1)[0] == 'actions/cache/save'
    assert install['id'] == 'valgrind'
    assert install['run'] == 'python3 scripts/ci/install_valgrind.py'
    assert install['if'] == "steps.capture.outputs.proceed == 'true'"
    assert restore['if'] == install['if']
    assert save['if'] == f"{install['if']} && steps.valgrind.outputs.cache-changed == 'true'"
    capture = next(entry for entry in steps if entry.get('name') == 'Capture the leaderboard')
    assert steps.index(capture) < steps.index(restore) < steps.index(install) < steps.index(save)
