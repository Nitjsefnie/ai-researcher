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
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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
    assert module.REQUIRED_JOBS == ('actionlint', 'analyze', 'coverage',
                                    'lint', 'page', 'pip-audit', 'pyright',
                                    'suites')
    assert module.BASE_BRANCH == 'main'
    for name, path in (('actionlint', 'actionlint.yml'),
                       ('analyze', 'codeql.yml'),
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


# The route-disagreement window's files (issue #118): the one admitted
# exception to the pin below. They enter and leave the tree at AA's whim on
# the hourly capture, and while they are tracked the refresh workflow reads
# them by name, so the live derivation genuinely includes them -- a frozen
# twin of a live derivation cannot follow them without itself becoming
# window-aware (issue #172). Named here by hand, not parsed out of
# refresh.yml: the mechanism is issue #118's, these are exactly its two
# files, and a parser over the workflow's conditional adds would add
# machinery without adding teeth -- the pin still fails on every other
# movement of the set.
WINDOW_PATHS = (
    'data/aa-disagreement-snapshot.json',
    'data/aa-route-disagreement.txt',
)


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
    window = sorted(p for p in WINDOW_PATHS if p in _load().tracked_files(ROOT))
    expected = sorted(CORE_PIN + tuple(window))
    assert derived == expected, (
        'the derived gate-path set moved against its pin (window files '
        f'tracked: {window}):\n{done.stdout}')


# The windowless derived set -- the pin itself. Frozen so a required job
# naming a new file forces a same-commit pin change; only WINDOW_PATHS, and
# only while tracked, may join it without an edit.
CORE_PIN = (
    '.github/ci-thresholds.json',
    '.github/workflows/actionlint.yml',
    '.github/workflows/audit.yml',
    '.github/workflows/claim.yml',
    '.github/workflows/codeql.yml',
    '.github/workflows/coverage-comment.yml',
    '.github/workflows/lint.yml',
    '.github/workflows/pr-gate.yml',
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
    'scripts/ci/check_ratchets.py',
    'scripts/ci/commit_scopes.py',
    'scripts/ci/gate_base_freshness.py',
    'scripts/ci/install_chromium.py',
    'scripts/ci/instruction_budgets.py',
    'scripts/ci/js_coverage.py',
    'scripts/ci/ratchet.py',
    'scripts/ci/thresholds.py',
    'tests/fixtures/pipeline/aa-raw-coding-agents.json',
    'tests/fixtures/pipeline/aa-raw-models.json',
    'tests/fixtures/pipeline/captured-at.txt',
    'tests/test_browser.py',
    'tests/test_build.py',
    'tests/test_capture_gate.py',
    'tests/test_check_committed_page.py',
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
    'tests/test_js_coverage.py',
    'tests/test_publish_docs.py',
    'tests/test_refresh_workflow.py',
    'tests/_workflowrun.py',
)


def test_the_window_files_enter_and_leave_the_derivation(tmp_path):
    """The committed reproduction of the disputed state (issue #172).

    The route-disagreement window's files (issue #118) enter the derivation
    exactly while they are tracked: named by the refresh workflow's run
    text, resolved against HEAD's tree. This fixture turns that mechanism
    through all three states -- before the window, during it, at its
    retirement -- so the window-awareness stays proven after the live
    window on main has closed and the files have left the tree. The data/
    directory written here is the fixture repository's, never this
    repository's.
    """
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
            '      - run: cat README.md ' + ' '.join(WINDOW_PATHS) + '\n',
        '.github/workflows/gates.yml': _stub_workflow(),
    })
    module = _load()

    # Before the window: the run text names both files, but resolve()
    # admits only tracked names, so neither is in the derived set -- even
    # with one sitting untracked on the working disk: the derivation reads
    # HEAD's tree, never the working directory.
    (repo / 'data').mkdir(parents=True, exist_ok=True)
    (repo / WINDOW_PATHS[1]).write_text('1767225600\n', encoding='utf-8',
                                        newline='\n')
    before = module.gate_paths(repo)
    assert not any(p in before for p in WINDOW_PATHS), before

    # The window opens: commit the disputed state, both files are derived.
    _commit(repo, 'ci: the disagreement window opens (issue #118)', {
        'data/aa-disagreement-snapshot.json': '{}\n',
        'data/aa-route-disagreement.txt': '1767225600\n',
    })
    during = module.gate_paths(repo)
    assert all(p in during for p in WINDOW_PATHS), during

    # The window retires: the files leave the tree, the derivation follows.
    _git(repo, 'rm', '-q', *WINDOW_PATHS)
    _git(repo, 'commit', '-m', 'ci: the window retires (issue #118)')
    after = module.gate_paths(repo)
    assert not any(p in after for p in WINDOW_PATHS), after


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
