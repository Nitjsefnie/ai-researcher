"""The base-freshness gate: scripts/ci/gate_base_freshness.py.

The fixtures are real git repositories with a local bare origin, so the
fetch the gate performs is exercised against a filesystem remote — never
the network, and never against this repository or any of its worktrees:
their shared ``.git`` must never be made shallow or have its history move.

The fixture helpers deliberately mirror upstream pr-gate's suite, so a
finding in an unchanged port dedupes against the upstream tracker rather
than filed twice; the duplicated helper lines that mirror is made of are
kept as written, and duplicate-code stays scoped to this file.
"""
# pylint: disable=duplicate-code
import contextlib
import importlib.util
import io
import itertools
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gitignore  # noqa: E402  # pylint: disable=wrong-import-position

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _local_event_by_default(monkeypatch):
    """Run the gate as a LOCAL run unless a test names its event.

    The gate's verdict reads GITHUB_EVENT_NAME, and the suite runs inside CI
    where the runner sets it for real — push on a main push, pull_request on
    a PR. Left inherited, every fixture's expectation would depend on which
    workflow happened to run the suite: a red fixture asserted on a push run
    goes green there. Deleted by default, the whole suite judges every head
    as a local run — the strict comparison — and only the event tests below
    set the variable again.
    """
    monkeypatch.delenv('GITHUB_EVENT_NAME', raising=False)


def _load():
    path = ROOT / 'scripts/ci/gate_base_freshness.py'
    spec = importlib.util.spec_from_file_location('gate_base_freshness', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(root, *arguments):
    done = subprocess.run(
        ['git', '-C', str(root), *arguments], check=True,
        capture_output=True, text=True)
    return done.stdout


def _config(repo):
    # Identity by per-repo config, never by flags or environment: this
    # repository's discipline forbids -c user.name/-c user.email and
    # GIT_AUTHOR_*/GIT_COMMITTER_* on its own commits, and the fixtures
    # keep the same shape.
    _git(repo, 'config', 'user.name', 'fixture')
    _git(repo, 'config', 'user.email', 'fixture@example.com')
    _git(repo, 'config', 'commit.gpgsign', 'false')


def _commit(repo, subject, files):
    for relative, text in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
    _git(repo, 'add', '--', *files)
    _git(repo, 'commit', '-m', subject)


def _stub_workflow():
    """A workflow defining every merge-gate job the inline fixtures do not.

    REQUIRED_JOBS is wider here than upstream's two contexts, so a fixture
    repository must define all of them or gate_paths refuses. The stub jobs
    read README.md, a file the fixtures carry."""
    module = _load()
    covered = {'actionlint', 'suites'}
    jobs = '\n'.join(
        f'  {job}:\n    steps:\n      - run: cat README.md\n'
        for job in module.REQUIRED_JOBS if job not in covered)
    return 'name: gates\non: push\njobs:\n' + jobs


def _fixture(tmp_path):
    """origin (bare) + repo (a full clone whose origin is that bare repo)."""
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed the fixture', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\n'
            'on: push\n'
            'jobs:\n'
            '  actionlint:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
        '.github/workflows/tests.yml':
            'name: tests\n'
            'on: push\n'
            'jobs:\n'
            '  suites:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: python run_tests.py\n',
        '.github/workflows/gates.yml': _stub_workflow(),
        'run_tests.py': 'print("suite runner")\n',
        'README.md': '# fixture\n',
    })
    origin = tmp_path / 'origin.git'
    _git(tmp_path, 'clone', '--bare', str(repo), str(origin))
    _git(repo, 'remote', 'add', 'origin', str(origin))
    _git(repo, 'push', '-u', 'origin', 'main')
    return repo, origin


def _advance_main(tmp_path, origin, subject, files):
    """Push a commit to origin's main from a second clone."""
    other = tmp_path / 'other'
    _git(tmp_path, 'clone', str(origin), str(other))
    _config(other)
    _commit(other, subject, files)
    _git(other, 'push', 'origin', 'main')


def test_required_jobs_name_the_merge_gate_contexts(tmp_path):
    del tmp_path
    module = _load()
    assert module.REQUIRED_JOBS == ('actionlint', 'aggregate', 'analyze',
                                    'classify', 'coverage', 'lint', 'page',
                                    'pip-audit', 'pyright', 'suites')
    assert module.BASE_BRANCH == 'main'
    for name, path in (('actionlint', 'actionlint.yml'),
                       ('aggregate', 'ci-gate.yml'),
                       ('analyze', 'codeql.yml'),
                       ('classify', 'ci-gate.yml'),
                       ('coverage', 'tests.yml'),
                       ('lint', 'lint.yml'),
                       ('page', 'tests.yml'),
                       ('pip-audit', 'audit.yml'),
                       ('pyright', 'types.yml'),
                       ('suites', 'tests.yml')):
        jobs = yaml.load(
            (ROOT / '.github/workflows' / path).read_text(encoding='utf-8'),
            Loader=yaml.BaseLoader)['jobs']
        assert name in jobs, f'{path} must define the merge-gate job {name!r}'


# The route-disagreement window's files (issue #118) used to be hand-named
# here, and the hand list is exactly what failed (issue #198): it named the
# snapshot and the stamp but not the last-agreeing record #192's re-land
# added, so the first real heal (c98e1bf1) reded main and froze the hourly
# refresh. The set is derived instead from the same source the pipeline
# commits from -- the refresh workflow's commit-step adds, parsed exactly as
# tests/test_gitignore.py parses them -- so the next window file joins the
# pin with no second edit. The window files proper are the parsed add paths
# that are not in CORE_PIN: a path the gate reads windowless is already
# pinned unconditionally, so its tracked-ness cannot move the derived set.
def window_paths():
    """The refresh add paths whose tracked-ness can move the derived set."""
    paths = [p for p in test_gitignore.added_paths() if p not in CORE_PIN]
    assert paths, (
        'no window paths parsed from the refresh commit step; the pin would '
        'silently narrow to CORE_PIN alone')
    return paths


def pin_expected_paths(tracked):
    """The windowless pin widened by exactly the window files tracked.

    CORE_PIN is the windowless derived set; every refresh add path HEAD
    tracks joins it. The tracked-filter is the same one the derivation
    itself applies (resolve() admits tracked names only), so the two halves
    agree in every window state the pipeline can commit -- including the
    healed hour, where the pre-#198 hand list did not.
    """
    return sorted(set(CORE_PIN)
                  | {p for p in test_gitignore.added_paths() if p in tracked})


# The derived set on this repository's HEAD, pinned as the windowless
# expectation (CORE_PIN below): a required job naming a new file forces this
# pin to change in the same commit, says nothing else may move.
def test_gate_paths_on_this_repository(tmp_path):
    del tmp_path
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--print-paths'], cwd=str(ROOT), check=True, capture_output=True,
        text=True)
    derived = done.stdout.splitlines()
    # The window's state is read where the derivation reads it: HEAD's tree
    # (tracked_files runs `git ls-tree HEAD`), never the working directory --
    # a working-tree-only stamp is no gate input, and the derivation would
    # not see it either.
    tracked = _load().tracked_files(ROOT)
    expected = pin_expected_paths(tracked)
    moving = [p for p in window_paths() if p in tracked]
    assert derived == expected, (
        'the derived gate-path set moved against its pin (window files '
        f'tracked: {moving}):\n{done.stdout}')


def test_the_pin_expectation_admits_every_window_combination():
    """The committed reproduction of the healed-hour red (issue #198).

    Runs OUTSIDE a live window: `tracked` is synthesized, never this
    repository's tree. Every tracked/untracked combination of the window
    files the pipeline can commit must leave the expectation equal to the
    tracked set it describes. The pre-#198 pin fails exactly here: its hand
    list knew the snapshot and the stamp but not the last-agreeing record,
    so the healed combinations left the record out of the expectation while
    the derivation -- which reaches every tracked data/ file -- had it.
    """
    window = window_paths()
    for size in range(len(window) + 1):
        for combo in itertools.combinations(window, size):
            tracked = frozenset(CORE_PIN) | set(combo)
            assert set(pin_expected_paths(tracked)) == tracked, (
                'the pin does not admit the window combination '
                f'{combo!r}: expected {pin_expected_paths(tracked)!r}')
    # And the negative half: a tracked file the pipeline cannot commit --
    # no refresh add carries it, and CORE_PIN does not name it -- joins no
    # expectation. The real-repo pin fails on such a movement, because the
    # derivation follows every file a gate job names; the expectation
    # builder is the side that must refuse.
    stranger = 'scripts/ci/not-a-window-file.py'
    assert stranger not in pin_expected_paths(frozenset(CORE_PIN) | {stranger})


# The windowless derived set -- the pin itself. Frozen so a required job
# naming a new file forces a same-commit pin change; only the window files
# derived from the refresh commit step, and only while tracked, may join it
# without an edit.
CORE_PIN = (
    '.github/ci-thresholds.json',
    '.github/workflows/actionlint.yml',
    '.github/workflows/audit.yml',
    '.github/workflows/claim.yml',
    '.github/workflows/codeql.yml',
    '.github/workflows/ci-gate.yml',
    '.github/workflows/coverage-comment.yml',
    '.github/workflows/lint.yml',
    '.github/workflows/pr-gate.yml',
    '.github/workflows/ratchet-push.yml',
    '.github/workflows/refresh.yml',
    '.github/workflows/scorecard.yml',
    '.github/workflows/secrets.yml',
    '.github/workflows/tests.yml',
    '.github/workflows/types.yml',
    'data/aa-raw-coding-agents.json',
    'data/aa-raw-models.json',
    'data/captured-at.txt',
    'out/frontier-models.html',
    'requirements-dev.txt',
    'requirements-pip-audit.txt',
    'requirements-test.txt',
    'requirements-zizmor.txt',
    'scripts/ci/check_committed_page.py',
    'scripts/ci/aggregate_gate.py',
    'scripts/ci/check_ratchets.py',
    'scripts/ci/classify_changes.py',
    'scripts/ci/commit_scopes.py',
    'scripts/ci/gate_base_freshness.py',
    'scripts/ci/install_chromium.py',
    'scripts/ci/instruction_budgets.py',
    'scripts/ci/js_coverage.py',
    'scripts/ci/ratchet.py',
    'scripts/ci/thresholds.py',
    'tests/fixtures/issue-176/README.md',
    'tests/fixtures/issue-176/disagreement-snapshot.json',
    'tests/fixtures/issue-176/last-capture.json',
    'tests/fixtures/pipeline/aa-raw-coding-agents.json',
    'tests/fixtures/pipeline/aa-raw-models.json',
    'tests/fixtures/pipeline/captured-at.txt',
    'tests/test_browser.py',
    'tests/test_build.py',
    'tests/test_capture_gate.py',
    'tests/test_check_committed_page.py',
    'tests/test_ci_classify_verified_base.py',
    'tests/test_ci_gate_botdata.py',
    'tests/test_ci_gate_modules.py',
    'tests/test_ci_gate_output_wiring.py',
    'tests/test_checkout_clean.py',
    'tests/test_ci_context_separation.py',
    'tests/test_ci_install_chromium.py',
    'tests/test_ci_instruction_budgets.py',
    'tests/test_ci_perf_budgets.py',
    'tests/test_ci_ratchets.py',
    'tests/test_ci_thresholds.py',
    'tests/test_ci_workflows.py',
    'tests/test_commit_scopes.py',
    'tests/test_coverage_comment.py',
    'tests/test_diff_aa.py',
    'tests/test_diff_coverage.py',
    'tests/test_fetch_aa.py',
    'tests/test_gate_base_freshness.py',
    'tests/test_gitignore.py',
    'tests/test_workflow_ci_gate.py',
    'tests/test_js_coverage.py',
    'tests/test_publish_docs.py',
    'tests/test_ratchet_push_workflow.py',
    'tests/test_refresh_workflow.py',
    'tests/_workflowrun.py',
)


def test_the_window_files_enter_and_leave_the_derivation(tmp_path):
    """The committed reproduction of every window state (issues #118, #172,
    #198).

    The route-disagreement window's files (issue #118) enter the derivation
    exactly while they are tracked: named by the refresh workflow's run
    text, resolved against HEAD's tree. This fixture turns that mechanism
    through the states the pipeline commits -- windowless, the disputed
    hour, the healed hour (stamp + last-agreeing record, no snapshot: the
    shape c98e1bf1 put on main), the all-three hour, and the retirement --
    so the window-awareness stays proven after the live window on main has
    closed and the files have left the tree. Each state is checked BOTH
    ways: the derivation must see exactly the tracked window files, and the
    pin's expectation -- built the way the real pin builds it, a windowless
    base plus the tracked window files -- must equal the derivation. On the
    pre-#198 pin the healed arm fails: the hand list did not know the
    record. The data/ directory written here is the fixture repository's,
    never this repository's.
    """
    module = _load()
    window = window_paths()
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed the window fixture', {
        'README.md': '# fixture\n',
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: cat README.md ' + ' '.join(window) + '\n',
        '.github/workflows/gates.yml': _stub_workflow(),
    })

    # Before the window: the run text names every window file, but resolve()
    # admits only tracked names, so none is in the derived set -- even with
    # all of them sitting untracked on the working disk: the derivation reads
    # HEAD's tree, never the working directory.
    (repo / 'data').mkdir(parents=True, exist_ok=True)
    for path in window:
        (repo / path).write_text('1767225600\n', encoding='utf-8',
                                 newline='\n')
    base = module.gate_paths(repo)
    assert not any(p in base for p in window), base

    def assert_state(why, tracked_window):
        """The two halves per state: the derivation must see exactly the
        tracked window files, and the pin's expectation -- a windowless base
        plus the tracked window files -- must equal it."""
        tracked = module.tracked_files(repo)
        derived = module.gate_paths(repo)
        expected = sorted(set(base) | {p for p in window if p in tracked})
        assert set(derived) == set(expected), (why, sorted(derived), expected)
        for path in tracked_window:
            assert path in derived, (why, path)

    # The disputed hour opens: the snapshot and the stamp are committed --
    # both derived, both expected. Today's parse order puts the snapshot at
    # window[0], the stamp at window[1], the record at window[2]; the walk's
    # mechanics do not depend on which file sits in which slot.
    _commit(repo, 'ci: the disagreement window opens (issue #118)', {
        window[0]: '{}\n',
        window[1]: '1767225600\n',
    })
    assert_state('disputed hour', window[:2])

    # The healed hour (#192's re-land): the snapshot leaves the tree, the
    # last-agreeing record joins -- the shape c98e1bf1 committed and the
    # pre-#198 hand list did not know.
    _git(repo, 'rm', '-q', window[0])
    _commit(repo, 'ci: the hour heals the stale route (issues #176, #189)', {
        window[2]: '{"captured_at": 1767225600}\n',
    })
    assert_state('healed hour', window[2:])

    # The window reopens disputed on top of a healed hour: the snapshot
    # returns while the stamp and the record stay. No state transition may
    # assume an ordering.
    _commit(repo, 'ci: the routes disagree again (issue #118)', {
        window[0]: '{}\n',
    })
    assert_state('all three tracked', window)

    # The routes agree: the whole set leaves together, and the derivation
    # and the expectation return to the windowless base.
    _git(repo, 'rm', '-q', *window)
    _git(repo, 'commit', '-m', 'ci: the window retires (issue #118)')
    assert_state('retired', [])


def test_the_pin_fails_when_a_gate_names_a_file_the_pipeline_cannot_commit(tmp_path):
    """The pin's teeth beyond the window files (issue #198).

    The window-aware widening follows ONE source -- the refresh workflow's
    commit-step adds -- and must follow no other. A gate job naming a new
    tracked file that no add carries grows the derivation but not the
    expectation: the pin fails, naming the movement. This is the proof that
    deriving the window set did not soften the pin: every movement the
    pipeline cannot explain stays a failure.
    """
    module = _load()
    window = window_paths()
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed the teeth fixture', {
        'README.md': '# fixture\n',
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: cat README.md ' + ' '.join(window) + '\n',
        '.github/workflows/gates.yml': _stub_workflow(),
    })
    base = module.gate_paths(repo)

    # A gate job names a new tracked file no refresh add carries.
    _commit(repo, 'ci: a gate reads a file the pipeline cannot commit', {
        'scripts/ci/fixture-gate-read.py': '# read by the suites job\n',
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: cat README.md scripts/ci/fixture-gate-read.py\n',
    })
    tracked = module.tracked_files(repo)
    derived = module.gate_paths(repo)
    expected = sorted(set(base) | {p for p in window if p in tracked})
    assert 'scripts/ci/fixture-gate-read.py' in derived, derived
    assert derived != expected, (
        'the derivation moved without any window file moving; the pin '
        'must fail on this movement')


def test_green_when_the_head_carries_every_gate_commit(tmp_path):
    repo, _ = _fixture(tmp_path)
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert 'carries every commit on main' in done.stdout
    assert 'BY NAME' in done.stdout


def test_red_when_main_advances_a_gate_file(tmp_path):
    repo, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'ci: move the gate the head already read', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\n'
            'on: push\n'
            'jobs:\n'
            '  actionlint:\n'
            '    runs-on: changed\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
    })
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert 'main holds 1 commit this head does not' in done.stdout
    assert 'ci: move the gate the head already read' in done.stdout
    assert '.github/workflows/actionlint.yml' in done.stdout
    assert 'Rebase onto main' in done.stdout


def test_a_push_head_main_has_passed_passes(tmp_path):
    """A push run whose head main has passed passes the gate (issue #195).

    The refresh workflow lands gate-read files (data/, out/) hourly, so main
    has usually moved past a main-push head by the time the step runs — while
    the run is still executing, not only between runs (issue #196, closed a
    duplicate). The gate's only view of time is the fetch its check performs,
    so this fixture advances main on a gate-read file and THEN runs the gate,
    exactly where the step's fetch lands it; an advance later in the run
    cannot reach a step that has already fetched.
    """
    repo, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'ci: move a gate file after the push landed', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\n'
            'on: push\n'
            'jobs:\n'
            '  actionlint:\n'
            '    runs-on: changed\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
    })
    monkeypatch_env = os.environ.copy()
    monkeypatch_env['GITHUB_EVENT_NAME'] = 'push'
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True,
        env=monkeypatch_env)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert "part of main's own history" in done.stdout
    assert 'holds 1 commit it does not' in done.stdout
    assert 'Rebase' not in done.stdout
    assert 'BY NAME' in done.stdout, (
        'the push verdict still derives the gate-path set, so its refusals '
        'stay universal')


def test_a_push_head_outside_mains_history_is_judged_strictly(tmp_path):
    """A pushed head outside main's history is judged like any other head.

    The push event alone is not the pass: an ordinary feature-branch push is
    diverged from main, nothing about landing it in main's history is vacuous,
    and the ancestor arm would be a false green if the event alone relaxed the
    comparison.
    """
    repo, origin = _fixture(tmp_path)
    _commit(repo, 'ci: the diverged push head', {
        '.github/workflows/tests.yml':
            'name: tests\n'
            'on: push\n'
            'jobs:\n'
            '  suites:\n'
            '    runs-on: diverged\n'
            '    steps:\n'
            '      - run: python run_tests.py\n',
    })
    _advance_main(tmp_path, origin, 'ci: move a gate file past the diverged push', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\n'
            'on: push\n'
            'jobs:\n'
            '  actionlint:\n'
            '    runs-on: changed\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
    })
    monkeypatch_env = os.environ.copy()
    monkeypatch_env['GITHUB_EVENT_NAME'] = 'push'
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True,
        env=monkeypatch_env)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert 'main holds 1 commit this head does not' in done.stdout
    assert 'Rebase onto main' in done.stdout


def test_a_pull_request_head_keeps_the_strict_gate(tmp_path):
    """A pull_request event keeps the comparison exactly as before.

    The arm is the event's, not the ancestry's alone: a PR head that is an
    ancestor of main — every fixture head is — still fails when main has
    moved on a gate-read file, because a PR can still rebase and the run's
    checks are meant to read the files main reads.
    """
    repo, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'ci: move a gate file under an open pull request', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\n'
            'on: push\n'
            'jobs:\n'
            '  actionlint:\n'
            '    runs-on: changed\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
    })
    monkeypatch_env = os.environ.copy()
    monkeypatch_env['GITHUB_EVENT_NAME'] = 'pull_request'
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True,
        env=monkeypatch_env)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert 'main holds 1 commit this head does not' in done.stdout
    assert 'Rebase onto main' in done.stdout
    assert "part of main's own history" not in done.stdout


def test_an_unset_event_keeps_the_strict_gate(tmp_path):
    """An absent GITHUB_EVENT_NAME — a local run — keeps the strict gate.

    The arm is named by the event, never by the ancestry alone: absent
    evidence of the event, nothing relaxes by accident.
    """
    repo, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'ci: move a gate file under a local run', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\n'
            'on: push\n'
            'jobs:\n'
            '  actionlint:\n'
            '    runs-on: changed\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
    })
    assert 'GITHUB_EVENT_NAME' not in os.environ
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert 'Rebase onto main' in done.stdout
    assert "part of main's own history" not in done.stdout


def test_the_ancestry_refusal_names_the_attempt():
    """A merge-base that cannot run is a refusal, not a `no`.

    `git merge-base --is-ancestor` is three-valued — 0 ancestor, 1 not, past
    that an error — and an error must not read as "not an ancestor": the
    strict comparison that follows would judge a head whose ancestry was
    never established.
    """
    module = _load()
    try:
        module.head_is_mains_history(ROOT, 'HEAD', 'not-a-ref')
    except module.GateError as refusal:
        assert 'cannot tell whether' in str(refusal)
        assert 'exited' in str(refusal)
    else:
        raise AssertionError('an unanswerable ancestry must refuse, not pass')


def test_green_when_main_advances_a_non_gate_file(tmp_path):
    repo, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'fix: a file no required check reads by name', {
        '.pylintrc': '[MESSAGES CONTROL]\ndisable=\n',
    })
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(repo)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert 'carries every commit on main' in done.stdout


def test_red_names_a_merge_commit(tmp_path):
    _, origin = _fixture(tmp_path)
    # The stale clone is taken BEFORE the merge lands on origin: its own
    # fetch_base is what brings the merge into view, which is the situation
    # the check exists to answer.
    behind = tmp_path / 'behind'
    _git(tmp_path, 'clone', str(origin), str(behind))
    _config(behind)
    side = tmp_path / 'side'
    _git(tmp_path, 'clone', str(origin), str(side))
    _config(side)
    _commit(side, 'ci: the side parent', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    runs-on: side\n    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n'})
    # adv diverges BEFORE the side push, so the pull must merge: origin's
    # main then carries a real merge commit for the stale listing to name.
    adv = tmp_path / 'adv'
    _git(tmp_path, 'clone', str(origin), str(adv))
    _config(adv)
    _commit(adv, 'ci: the second parent', {
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    steps:\n      - run: python run_tests.py\n'})
    _git(side, 'push', 'origin', 'main')
    _git(adv, 'pull', '--no-rebase', 'origin', 'main')
    _git(adv, 'push', 'origin', 'main')
    done = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/ci/gate_base_freshness.py'),
         '--root', str(behind)], check=False, capture_output=True, text=True)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert '(a merge commit, which git names no file for' in done.stdout
    assert 'ci: the side parent' in done.stdout
    assert 'ci: the second parent' in done.stdout


def test_refuses_when_a_required_job_is_missing(tmp_path):
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n      - run: cat README.md\n',
        'README.md': '# fixture\n',
    })
    module = _load()
    try:
        module.gate_paths(repo)
    except module.GateError as refusal:
        assert 'defines the merge-gate job' in str(refusal)
    else:
        raise AssertionError('a missing required job must refuse, not pass')


def test_refuses_shapes_it_cannot_read(tmp_path):
    del tmp_path
    module = _load()
    fixtures = {
        'a flow-mapping jobs:':
            'name: actionlint\n'
            'jobs: {actionlint: {runs-on: ubuntu-latest}}\n',
        'duplicate job names:':
            'name: actionlint\n'
            'jobs:\n'
            '  actionlint:\n'
            '    steps:\n'
            '      - run: cat README.md\n'
            '  actionlint:\n'
            '    steps:\n'
            '      - run: cat README.md\n',
        'a flow `steps:` value:':
            'name: actionlint\n'
            'jobs:\n'
            '  actionlint:\n'
            '    steps: [{run: cat README.md}]\n',
    }
    for why, text in fixtures.items():
        try:
            module.workflow_steps(text, 'fixture.yml')
        except module.WorkflowError:
            continue
        raise AssertionError(f'{why} must refuse, not parse')


def test_expressions_are_stripped_before_paths_are_taken(tmp_path):
    module = _load()
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed', {
        'run_tests.py': 'print("suite runner")\n',
        'matrix.python': 'not a path a step reads\n',
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n'
            '      - run: python -m pytest ${{ matrix.python }}\n',
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    steps:\n      - run: python run_tests.py\n',
        '.github/workflows/gates.yml': _stub_workflow(),
    })
    assert 'matrix.python' not in module.gate_paths(repo), (
        'the expression is stripped before the run text is scanned, so its '
        'identifiers never resolve to a tracked file')


def test_whole_tree_spelling_adds_no_paths(tmp_path):
    module = _load()
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    marker = ('      - run: git grep -nI -E '
              '"^(<{7}( |$)|>{7}( |$)|={7}$)" -- .\n')
    idle = '\n'.join(
        f'  {job}:\n    steps:\n      - run: echo done\n'
        for job in module.REQUIRED_JOBS
        if job not in ('actionlint', 'suites'))
    _commit(repo, 'base: seed', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            f'    steps:\n{marker}',
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            f'    steps:\n{marker}',
        '.github/workflows/gates.yml':
            'name: gates\non: push\njobs:\n' + idle,
    })
    try:
        module.gate_paths(repo)
    except module.GateError as refusal:
        assert 'name no file in this tree' in str(refusal)
    else:
        raise AssertionError('a set with no resolved file must refuse')


def test_a_shallow_clone_is_unshallowed_before_comparing(tmp_path):
    _, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'ci: main moved while the head was shallow', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    runs-on: changed\n    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n',
    })
    behind = tmp_path / 'behind'
    # --depth is ignored for plain-path clones, so the fixture clones over
    # file:// and stays a separate repository from this one throughout.
    _git(tmp_path, 'clone', '--depth', '1', origin.as_uri(), str(behind))
    _config(behind)
    assert _git(behind, 'rev-parse', '--is-shallow-repository').strip() == 'true'
    module = _load()
    module.fetch_base(behind)
    assert _git(behind, 'rev-parse', '--is-shallow-repository').strip() == 'false', (
        'the fetch must deepen a shallow checkout before the comparison')


def test_exit_codes_and_argv(tmp_path):
    repo, _ = _fixture(tmp_path)
    script = ROOT / 'scripts/ci/gate_base_freshness.py'
    unknown = subprocess.run(
        [sys.executable, str(script), '--root', str(repo), '--nonsense'],
        check=False, capture_output=True, text=True)
    assert unknown.returncode == 2
    assert 'usage' in unknown.stderr
    missing_value = subprocess.run(
        [sys.executable, str(script), '--root'], check=False,
        capture_output=True, text=True)
    assert missing_value.returncode == 2
    assert 'usage' in missing_value.stderr


def test_the_green_line_names_its_reach_limit(tmp_path):
    repo, _ = _fixture(tmp_path)
    module = _load()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.check(repo)
    assert code == 0
    out = buffer.getvalue()
    assert 'reading every tracked file' in out, out
    assert 'merge-marker step' in out, out
    assert 'named reach limit' in out, out
    assert 'BY NAME' in out, out


# --- in-process coverage of the parser and comparison helpers ---------------


def test_git_refusal_names_what_was_attempted(tmp_path):
    del tmp_path
    module = _load()
    try:
        module.git(ROOT, 'rev-parse', '--verify', 'definitely-not-a-ref^{commit}',
                   what='resolve the impossible')
    except module.GateError as refusal:
        assert 'cannot resolve the impossible' in str(refusal)
        assert 'exited' in str(refusal)
    else:
        raise AssertionError('a failing git call must refuse')


def test_block_scalar_run_text_is_read_verbatim(tmp_path):
    del tmp_path
    module = _load()
    text = ('name: actionlint\n'
            'jobs:\n'
            '  actionlint:\n'
            '    steps:\n'
            '      - name: a step\n'
            '        run: |\n'
            '          echo one\n'
            '          # a comment bash receives\n'
            '          grep README.md\n')
    steps = module.workflow_steps(text, 'w.yml')['actionlint']
    assert [step['run'] for step in steps] == [
        'echo one\n# a comment bash receives\ngrep README.md']


def test_uses_and_with_fields_are_read_and_skipped(tmp_path):
    del tmp_path
    module = _load()
    text = ('name: actionlint\n'
            'jobs:\n'
            '  actionlint:\n'
            '    strategy:\n'
            '      matrix: [a, b]\n'
            '    steps:\n'
            '      - uses: actions/checkout@1111111111111111111111111111111111111111 # v1\n'
            '        with:\n'
            '          fetch-depth: 0\n'
            '      - uses: ./\n')
    steps = module.workflow_steps(text, 'w.yml')['actionlint']
    assert steps[0]['uses'] == 'actions/checkout@1111111111111111111111111111111111111111'
    assert steps[1]['uses'] == './'


def test_resolve_arms(tmp_path):
    del tmp_path
    module = _load()
    files = ('action.yml', '.github/workflows/tests.yml',
             '.github/workflows/actionlint.yml')
    assert module.resolve('action.yml', files) == ('action.yml',)
    assert module.resolve('./action.yml', files) == ('action.yml',)
    assert module.resolve('action.yml/', files) == ('action.yml',)
    assert module.resolve('.github/workflows', files) == files[1:]
    assert module.resolve('absent.yml', files) == ()
    assert module.resolve('.', files) == ()


def test_candidates_strip_expressions(tmp_path):
    del tmp_path
    module = _load()
    # The strip removes the expression, so its identifiers never resolve to
    # a tracked file; the text around it is still scanned as-is.
    assert module.candidates('cat ${{ matrix.python }}/x.yml') == [
        'cat', '/x.yml']
    assert module.candidates('python run_tests.py') == [
        'python', 'run_tests.py']


def test_stale_commits_refuses_empty_and_oversized_paths(tmp_path):
    del tmp_path
    module = _load()
    try:
        module.stale_commits(ROOT, 'HEAD', 'origin/main', [])
    except module.GateError as refusal:
        assert 'empty' in str(refusal)
    else:
        raise AssertionError('an empty path set must refuse')
    # Sized against the real ceiling: the test never rewrites a module
    # constant, so the refusal is proven against the shipped byte limit.
    oversized = ['a' * (module.PATHSPECS_MAX_BYTES + 1)]
    try:
        module.stale_commits(ROOT, 'HEAD', 'origin/main', oversized)
    except module.GateError as refusal:
        assert 'bytes' in str(refusal)
    else:
        raise AssertionError('an oversized path set must refuse')


def test_gate_paths_refuses_a_tree_with_no_files(tmp_path):
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _git(repo, 'commit', '--allow-empty', '-m', 'base: an empty tree')
    module = _load()
    try:
        module.gate_paths(repo)
    except module.GateError as refusal:
        assert 'tracks no files' in str(refusal)
    else:
        raise AssertionError('an empty tree must refuse')


def test_check_reports_stale_commits_in_process(tmp_path):
    repo, origin = _fixture(tmp_path)
    _advance_main(tmp_path, origin, 'ci: a gate move the head lacks', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n'})
    module = _load()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.check(repo)
    assert code == 1
    out = buffer.getvalue()
    assert 'main holds 1 commit this head does not:' in out
    assert 'Rebase onto main and push again' in out
    assert '.github/workflows/actionlint.yml' in out


def test_main_returns_the_check_exit_code(tmp_path):
    repo, _ = _fixture(tmp_path)
    module = _load()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(['gate_base_freshness.py', '--root', str(repo)])
    assert code == 0
    assert 'carries every commit on main' in buffer.getvalue()


# --- parser arms: every refusal refuses, every loop control line runs -------


def test_every_tracked_workflow_parses(tmp_path):
    del tmp_path
    module = _load()
    for name in module.workflow_names(module.tracked_files(ROOT)):
        text = module.git(ROOT, 'cat-file', 'blob', f'HEAD:{name}',
                          what=f'read {name}')
        jobs = module.workflow_steps(text, name)
        assert jobs, name


def test_parser_refusal_arms(tmp_path):
    del tmp_path
    module = _load()
    cases = {
        'a job entry at the wrong indent':
            'name: w\njobs:\n   actionlint:\n',
        'a job key with an inline value':
            'name: w\njobs:\n  actionlint: {runs-on: ubuntu-latest}\n',
        'a job-level key at the wrong indent':
            'name: w\njobs:\n  actionlint:\n   runs-on: ubuntu-latest\n',
        'a step entry without a dash':
            'name: w\njobs:\n  actionlint:\n    steps:\n'
            '        run: echo\n',
        'a dash line that is not a key':
            'name: w\njobs:\n  actionlint:\n    steps:\n          - 123\n',
        'a step key at the wrong indent':
            'name: w\njobs:\n  actionlint:\n    steps:\n'
            '      - run: echo\n         x: 1\n',
    }
    for why, text in cases.items():
        try:
            module.workflow_steps(text, 'w.yml')
        except module.WorkflowError:
            continue
        raise AssertionError(f'{why} must refuse, not parse')


def test_a_plain_scalar_continuation_parses(tmp_path):
    # The one shape upstream refuses and this port models: a plain value
    # wrapped onto more-indented lines (the coverage gate in tests.yml wraps
    # its `if:` expression this way, and tests.yml is not this change's to
    # reformat). A continuation line carrying a mapping shape is NOT a
    # continuation — a plain scalar cannot carry colon-space — so the
    # wrong-indent refusal arm above keeps its teeth.
    del tmp_path
    module = _load()
    text = ('name: w\n'
            'jobs:\n'
            '  actionlint:\n'
            '    steps:\n'
            "      - if: ${{ !cancelled() && steps.a.outcome == 'success'\n"
            "                && steps.b.outcome == 'success' }}\n"
            '        run: echo done\n')
    steps = module.workflow_steps(text, 'w.yml')['actionlint']
    assert steps[0]['run'] == 'echo done'


def test_block_scalar_and_block_end_loop_arms(tmp_path):
    del tmp_path
    module = _load()
    text = ('name: w\n'
            'jobs:\n'
            '  actionlint:\n'
            '    # a comment inside the job block\n'
            '\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '      - run: |\n'
            '          echo one\n'
            '        name: renamed\n'
            'permissions:\n'
            '  contents: read\n')
    jobs = module.workflow_steps(text, 'w.yml')
    steps = jobs['actionlint']
    assert steps[0]['run'] == 'echo one'
    assert steps[0]['uses'] is None


def test_whole_action_use_takes_the_directory_whole(tmp_path):
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed', {
        'action.yml': 'name: the action\n',
        'README.md': '# fixture\n',
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n      - uses: ./\n',
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    steps:\n      - run: python run_tests.py\n',
        '.github/workflows/gates.yml': _stub_workflow(),
    })
    module = _load()
    assert 'README.md' in module.gate_paths(repo), (
        'uses: ./ reads the action directory whole, so every tracked file '
        'is a gate-read file')


def test_check_reports_a_merge_commit_in_process(tmp_path):
    _, origin = _fixture(tmp_path)
    behind = tmp_path / 'behind'
    _git(tmp_path, 'clone', str(origin), str(behind))
    _config(behind)
    side = tmp_path / 'side'
    _git(tmp_path, 'clone', str(origin), str(side))
    _config(side)
    _commit(side, 'ci: the side parent', {
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n'
            '      - run: ./actionlint -color .github/workflows/*.yml\n'})
    adv = tmp_path / 'adv'
    _git(tmp_path, 'clone', str(origin), str(adv))
    _config(adv)
    _commit(adv, 'ci: the second parent', {
        '.github/workflows/tests.yml':
            'name: tests\non: push\njobs:\n  suites:\n'
            '    steps:\n      - run: python run_tests.py\n'})
    _git(side, 'push', 'origin', 'main')
    _git(adv, 'pull', '--no-rebase', 'origin', 'main')
    _git(adv, 'push', 'origin', 'main')
    module = _load()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.check(behind)
    assert code == 1
    assert '(a merge commit, which git names no file for' in buffer.getvalue()


def test_main_handlers(tmp_path):
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    module = _load()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(['gate_base_freshness.py', '--root', str(repo)])
    assert code == 1
    saved_path = os.environ['PATH']
    try:
        os.environ['PATH'] = ''
        with contextlib.redirect_stderr(io.StringIO()):
            code = module.main(['gate_base_freshness.py', '--root', str(ROOT)])
        assert code == 1
    finally:
        os.environ['PATH'] = saved_path
