"""tests.yml keeps untrusted pull-request execution out of trusted contexts.

Code-scanning alerts #26 (actions/cache-poisoning/poisonable-step) and #27
(actions/untrusted-checkout/medium) on .github/workflows/tests.yml both
flowed from two surfaces, and this file pins each shut:

- the ``workflow_dispatch`` trigger. The cache-poisoning query
  (CachePoisoningViaPoisonableStep.ql) requires an externally triggerable
  event with default-branch cache-write access
  (``Event.isExternallyTriggerable`` plus
  ``hasDefaultBranchCacheWriteAccess``) and named workflow_dispatch in the
  alert message, so the trigger is what armed the finding;
- the "Ratchet documents" step's fetch of ``refs/pull/<number>/head``. The
  untrusted-checkout query (``GitMutableRefCheckout``) reads a ``git fetch``
  whose command or in-scope env carries the pull-request number — and its
  ``containsPullRequestNumber`` heuristics match the env name ``PR_NUMBER``
  itself, not only the expression it held.

The analyser reads the workflow text, so the pins read it too: either
surface re-arming goes red here rather than in the next default-branch
analysis, which is hours away and closes nothing.
"""
from pathlib import Path

import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'tests.yml'


def _document():
    # BaseLoader keeps every scalar a string, so the ``on:`` key survives as
    # 'on' instead of the boolean True a YAML 1.1 resolver makes of it.
    return yaml.load(WORKFLOW.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)


def _steps():
    for job in _document()['jobs'].values():
        for step in job.get('steps') or []:
            yield step


def test_no_externally_triggerable_default_branch_write_trigger():
    """tests.yml declares no dispatch trigger, and push names main only.

    workflow_dispatch is what the cache-poisoning query keys on: an event
    both externally triggerable and default-branch cache-write capable.
    repository_dispatch would read the same way to the analyser and is
    refused with it. push stays, scoped to main so the only
    default-branch-context runs carry main's own reviewed code, and
    pull_request stays so the suite still runs on changes — a pull_request
    run holds no default-branch cache write, which is exactly why the
    untrusted-code execution it does is out of the query's model.
    """
    triggers = _document()['on']
    assert triggers is not None
    for absent in ('workflow_dispatch', 'repository_dispatch'):
        assert absent not in triggers, sorted(triggers)
    assert triggers['push']['branches'] == ['main']
    assert 'pull_request' in triggers, sorted(triggers)


def test_no_step_fetches_or_checks_out_a_pr_controlled_ref():
    """No step that runs git/gh checkout commands touches a PR-controlled ref.

    The untrusted-checkout query's sources are textual — a fetch/pull/
    pr-checkout command or the env expression feeding it naming the PR
    number, a head ref, or a head SHA. Every step whose run text carries
    such a command is read here (its env values with it), and none may
    carry one of those names in any spelling the heuristics key on.
    """
    command = re.compile(
        r'\bgit\b[^\n]*?\b(?:fetch|pull|checkout)\b'
        r'|\b(?:gh|hub)\b[^\n]*?\bpr\s+checkout\b')
    forbidden = ('refs/pull', 'pr_number', 'pull_request.number',
                 'head_ref', 'head.sha', 'merge_commit_sha')
    flagged = []
    for step in _steps():
        env = step.get('env') or {}
        text = ' '.join(
            [step.get('run', '') or '']
            + [str(value) for value in env.values()])
        if not text or not command.search(text):
            continue
        lowered = text.lower()
        for name in forbidden:
            if name in lowered:
                flagged.append((step.get('name'), name))
    assert not flagged, flagged


def test_ratchet_documents_fetches_the_event_sha():
    """The shallow-history completion fetch is the event's own commit.

    On a pull request the checkout is the event's merge commit, whose first
    parent is the base tip and second parent the pull-request head, so one
    fetch of ``github.sha`` completes both sides for
    ``check_ratchets.py HEAD^1 HEAD^2`` — with no pull-request number and no
    ``refs/pull`` refspec anywhere in the step. The fetch the head-side
    guard needs is of trusted event provenance, which is the separation the
    two alerts turned on.
    """
    step = next(
        candidate for candidate in _steps()
        if candidate.get('name') == 'Ratchet documents')
    env = step['env']
    assert env['CI_SHA'] == '${{ github.sha }}'
    assert 'PR_NUMBER' not in env
    run = step['run']
    assert 'git fetch --unshallow origin "${CI_SHA}"' in run
    assert 'refs/pull' not in run
