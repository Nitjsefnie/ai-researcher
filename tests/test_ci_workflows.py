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
WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))

# `uses: github/codeql-action/<step>@<40-hex sha>  # vX.Y.Z`
_PIN = re.compile(
    r"uses:\s*github/codeql-action/(?P<step>\S+)@(?P<sha>[0-9a-f]{40})"
    r"(?:\s+#\s*(?P<comment>\S+))?"
)


def _pins(workflow: str):
    return _PIN.findall(workflow)


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


def test_codeql_action_pin_comments_are_immutable_release_tags():
    pins = _pins(CODEQL_WORKFLOW.read_text(encoding="utf-8"))
    assert len(pins) >= 2
    for pin in pins:
        comment = pin[2]
        # a floating major tag (# v4) decays when upstream re-points it, so
        # each comment must name an immutable vX.Y.Z release tag
        assert re.fullmatch(r"v\d+\.\d+\.\d+", comment), (
            f"{comment!r} is not an immutable release tag"
        )
    comments = {pin[2] for pin in pins}
    assert len(comments) == 1, (
        f"pin comments disagree across steps: {sorted(comments)}"
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


def test_every_job_declares_timeout_minutes():
    # Issue #52: a hung job fails in its declared ceiling instead of holding
    # GitHub's 6-hour default. The invariant rides on the whole catalogue —
    # a new workflow or job starts with it, and dropping the declaration
    # from an existing job fails here rather than in a 6-hour hang.
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (workflow.get("jobs") or {}).items():
            assert "timeout-minutes" in job, (
                f"{path.name}: job {name!r} declares no timeout-minutes"
            )
