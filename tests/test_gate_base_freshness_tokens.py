"""Which run-text tokens expand to a directory in the gate-path set (issue #378).

A bare word names a tracked file or nothing; only a token containing `/`
expands to every tracked file beneath a directory.
"""
from test_gate_base_freshness import _commit, _config, _git, _load, _stub_workflow

FILES = ('Makefile', 'requirements-dev.txt', 'data/x.json', 'data/y.json',
         'a/b/c.txt', 'a/bc.txt')


def test_a_bare_word_naming_a_directory_does_not_expand():
    resolve = _load().resolve
    assert resolve('data', FILES) == ()
    assert resolve('a', FILES) == ()


def test_a_path_shaped_directory_token_expands():
    resolve = _load().resolve
    assert resolve('data/', FILES) == ('data/x.json', 'data/y.json')
    assert resolve('./data', FILES) == ('data/x.json', 'data/y.json')
    assert resolve('a/b', FILES) == ('a/b/c.txt',)


def test_a_bare_word_naming_a_root_file_still_resolves():
    resolve = _load().resolve
    assert resolve('Makefile', FILES) == ('Makefile',)
    assert resolve('requirements-dev.txt', FILES) == ('requirements-dev.txt',)


def _suites_workflow(run):
    return ('name: tests\non: push\njobs:\n  suites:\n    steps:\n'
            '      - run: |\n' + ''.join(f'          {line}\n' for line in run))


def _fixture_repo(tmp_path, files):
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed the fixture', {
        'README.md': '# fixture\n',
        'run_tests.py': 'print("suite runner")\n',
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n      - run: cat README.md\n',
        '.github/workflows/gates.yml': _stub_workflow(),
        **files,
    })
    return repo


def test_gate_paths_expand_a_directory_only_where_a_run_names_it_as_a_path(tmp_path):
    module = _load()
    repo = _fixture_repo(tmp_path, {
        'assets/x.json': '{}\n',
        '.github/workflows/tests.yml': _suites_workflow(
            ['# this REPLACES the assets the outer run read', 'python run_tests.py']),
    })
    derived = module.gate_paths(repo)
    assert 'run_tests.py' in derived, derived
    assert 'assets/x.json' not in derived, derived

    _commit(repo, 'ci: the suite reads assets/', {
        '.github/workflows/tests.yml': _suites_workflow(
            ['python run_tests.py assets/']),
    })
    assert 'assets/x.json' in module.gate_paths(repo)


def test_listed_directories_stay_in_whatever_the_comments_say(tmp_path):
    module = _load()
    repo = _fixture_repo(tmp_path, {
        'data/x.json': '{}\n',
        'out/page.html': '<p>page</p>\n',
        '.github/workflows/tests.yml': _suites_workflow(
            ['# coverage combine REPLACES the data',
             "grep -q 'read timed out' log || python run_tests.py"]),
    })
    derived = module.gate_paths(repo)
    assert {'data/x.json', 'out/page.html', 'run_tests.py'} <= set(derived), derived

    _commit(repo, 'ci: reword the comment and the pattern', {
        '.github/workflows/tests.yml': _suites_workflow(
            ['# coverage combine REPLACES the coverage file',
             "grep -q 'read timeout' log || python run_tests.py"]),
    })
    assert module.gate_paths(repo) == derived


def test_a_listed_directory_does_not_stand_in_for_workflows_naming_nothing(tmp_path):
    module = _load()
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    idle = ''.join(f'  {job}:\n    steps:\n      - run: echo done\n'
                   for job in module.REQUIRED_JOBS)
    _commit(repo, 'base: seed', {
        'data/x.json': '{}\n',
        '.github/workflows/gates.yml': 'name: gates\non: push\njobs:\n' + idle,
    })
    try:
        module.gate_paths(repo)
    except module.GateError as refusal:
        assert 'name no file in this tree' in str(refusal)
    else:
        raise AssertionError('a listed directory alone must not satisfy the refusal')
