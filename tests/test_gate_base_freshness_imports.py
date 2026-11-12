"""The head-freshness gate follows what gate scripts import or run (issue #401).

Each fixture is a bare origin and a clone sitting on a `pr` branch; main then
moves one file, and the gate must go red exactly when a gate script reaches it.
"""
import contextlib
import importlib
import io
import os
import subprocess
import sys

import pytest

from test_gate_base_freshness import ROOT, _commit, _config, _git, _load, _stub_workflow

GATE = ROOT / 'scripts/ci/gate_base_freshness.py'


def _suites(command):
    return ('name: tests\non: push\njobs:\n  suites:\n    steps:\n'
            f'      - run: {command}\n')


def _repo(tmp_path, command, files):
    """A pushed fixture whose `suites` job runs `command`, checked out on `pr`."""
    repo = tmp_path / 'repo'
    _git(tmp_path, 'init', '-b', 'main', str(repo))
    _config(repo)
    _commit(repo, 'base: seed the fixture', {
        'README.md': '# fixture\n',
        'notes.py': '# imported by nothing\n',
        '.github/workflows/actionlint.yml':
            'name: actionlint\non: push\njobs:\n  actionlint:\n'
            '    steps:\n      - run: cat README.md\n',
        '.github/workflows/tests.yml': _suites(command),
        '.github/workflows/gates.yml': _stub_workflow(),
        **files,
    })
    origin = tmp_path / 'origin.git'
    _git(tmp_path, 'clone', '--bare', str(repo), str(origin))
    _git(repo, 'remote', 'add', 'origin', str(origin))
    _git(repo, 'push', '-u', 'origin', 'main')
    _git(repo, 'checkout', '-b', 'pr')
    return repo


def _main_appends_a_comment(repo, path):
    """On main, append a comment line to `path`, push, and return to `pr`."""
    _git(repo, 'checkout', 'main')
    text = (repo / path).read_text(encoding='utf-8')
    _commit(repo, f'chore: touch {path}', {path: text + '# touched on main\n'})
    _git(repo, 'push', 'origin', 'main')
    _git(repo, 'checkout', 'pr')


def _run_gate(repo):
    env = {**os.environ, 'GITHUB_EVENT_NAME': 'pull_request'}
    return subprocess.run([sys.executable, str(GATE), '--root', str(repo)],
                          check=False, capture_output=True, text=True, env=env)


def _verdict(repo, monkeypatch):
    """The gate's (exit code, stdout), run in process so its lines are measured."""
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = _load().check(repo)
    return code, buffer.getvalue()


def _assert_red_naming(verdict, path):
    code, out = verdict
    assert code == 1, out
    assert f'chore: touch {path}' in out, out
    assert f'    {path}\n' in out, out


# The issue's chain: the page job's script imports build, which imports page_format.
PAGE_CHAIN = {
    'scripts/ci/check_committed_page.py':
        'import sys\nsys.path.insert(0, "..")\nimport build\n',
    'build.py': 'import json\nimport page_format\n',
    'page_format.py': 'FORMAT = 1\n',
}


def test_a_main_commit_to_a_module_a_gate_script_imports_is_stale(tmp_path):
    repo = _repo(tmp_path, 'python3 scripts/ci/check_committed_page.py', PAGE_CHAIN)
    _main_appends_a_comment(repo, 'build.py')
    done = _run_gate(repo)
    _assert_red_naming((done.returncode, done.stdout + done.stderr), 'build.py')


def test_a_module_reached_only_through_a_second_hop_is_stale(tmp_path, monkeypatch):
    repo = _repo(tmp_path, 'python3 scripts/ci/check_committed_page.py', PAGE_CHAIN)
    _main_appends_a_comment(repo, 'page_format.py')
    _assert_red_naming(_verdict(repo, monkeypatch), 'page_format.py')


def test_a_main_commit_to_a_file_no_gate_reaches_stays_fresh(tmp_path, monkeypatch):
    repo = _repo(tmp_path, 'python3 scripts/ci/check_committed_page.py', PAGE_CHAIN)
    _main_appends_a_comment(repo, 'notes.py')
    code, out = _verdict(repo, monkeypatch)
    assert code == 0, out
    assert 'carries every commit on main' in out


# (gate script, its source, the module it reaches): one spelling or search root each.
SPELLINGS = {
    'plain import, own directory': ('tools/gate.py', 'import helper\n', 'tools/helper.py'),
    'plain import, repository root': (
        'scripts/ci/gate.py', 'import helper\n', 'helper.py'),
    'from-import, scripts/': (
        'scripts/ci/gate.py', 'from helper import thing\n', 'scripts/helper.py'),
    'plain import, scripts/ci/ from a test': (
        'tests/test_gate.py', 'import helper\n', 'scripts/ci/helper.py'),
    'dotted package import': (
        'scripts/ci/gate.py', 'from pkg.helper import thing\n', 'pkg/helper.py'),
    'package import': ('scripts/ci/gate.py', 'import pkg\n', 'pkg/__init__.py'),
    'parent package of a dotted import': (
        'scripts/ci/gate.py', 'import pkg.helper\n', 'pkg/__init__.py'),
    'relative from-import': (
        'scripts/ci/gate.py', 'if __package__:\n    from . import helper\n',
        'scripts/ci/helper.py'),
    'two-level relative from-import': (
        'tools/sub/gate.py', 'from .. import helper\n', 'tools/helper.py'),
    'importlib.import_module literal': (
        'scripts/ci/gate.py',
        'import importlib\nhelper = importlib.import_module("helper")\n',
        'scripts/ci/helper.py'),
    'bare import_module literal': (
        'scripts/ci/gate.py',
        'from importlib import import_module\nhelper = import_module("helper")\n',
        'scripts/ci/helper.py'),
    'path string literal it runs': (
        'scripts/ci/gate.py', 'TARGETS = (("helper", ("tools/helper.py",)),)\n',
        'tools/helper.py'),
}


@pytest.mark.parametrize('gate, source, helper', SPELLINGS.values(), ids=SPELLINGS)
def test_every_import_spelling_makes_the_reached_module_stale(tmp_path, monkeypatch, gate, source, helper):
    repo = _repo(tmp_path, f'python3 {gate}', {
        'pkg/helper.py': 'thing = 1\n', 'tools/sub/__init__.py': '', 'tools/__init__.py': '',
        gate: source, helper: 'thing = 1\n'})
    _main_appends_a_comment(repo, helper)
    _assert_red_naming(_verdict(repo, monkeypatch), helper)


def test_a_literal_naming_a_file_it_does_not_run_adds_nothing(tmp_path, monkeypatch):
    """Only a `.py` literal counts: a gate naming a document does not run it."""
    repo = _repo(tmp_path, 'python3 scripts/ci/gate.py', {
        'scripts/ci/gate.py': 'DOC = "notes.md"\nimport importlib\n'
                              'importlib.import_module(DOC)\n',
        'notes.md': '# notes\n'})
    _main_appends_a_comment(repo, 'notes.md')
    code, out = _verdict(repo, monkeypatch)
    assert code == 0, out


def test_a_tests_path_literal_reaches_nothing(tmp_path, monkeypatch):
    """A test's `.py` literal is an expectation: the pin naming every reached file must not reach them itself."""
    repo = _repo(tmp_path, 'python3 tests/test_pin.py', {
        'tests/test_pin.py': 'PIN = ("tools/tool.py",)\n', 'tools/tool.py': 'TOOL = 1\n'})
    _main_appends_a_comment(repo, 'tools/tool.py')
    code, out = _verdict(repo, monkeypatch)
    assert code == 0, out


def test_an_unparseable_gate_script_is_a_refusal_naming_it(tmp_path):
    repo = _repo(tmp_path, 'python3 scripts/ci/gate.py',
                 {'scripts/ci/gate.py': 'import helper\ndef broken(:\n'})
    module = _load()
    with pytest.raises(module.GateError, match='cannot parse scripts/ci/gate.py'):
        module.gate_paths(repo)
    done = _run_gate(repo)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert 'cannot parse scripts/ci/gate.py' in done.stderr, done.stderr


def test_an_undecodable_gate_script_is_a_refusal_naming_it(tmp_path):
    repo = _repo(tmp_path, 'python3 scripts/ci/gate.py', {'scripts/ci/gate.py': '# gate\n'})
    (repo / 'scripts/ci/gate.py').write_bytes(b'# not UTF-8: \xff\n')
    _git(repo, 'commit', '-qam', 'ci: an undecodable gate script')
    module = _load()
    with pytest.raises(module.GateError, match=r'cannot read scripts/ci/gate\.py: .* not UTF-8'):
        module.gate_paths(repo)


def test_undecodable_git_output_is_a_refusal_naming_the_command(tmp_path):
    """Every git call decodes in one place: undecodable output refuses, never answers None."""
    repo = _repo(tmp_path, 'python3 scripts/ci/gate.py', {'scripts/ci/gate.py': '# gate\n'})
    _git(repo, 'checkout', '-q', 'main')
    (repo / 'scripts/ci/gate.py').write_text('# moved\n', encoding='utf-8', newline='\n')
    _git(repo, 'commit', '-qam', 'chore: touch the gate \u00ff')
    # The repository's own setting makes git write the subject as Latin-1: 0xff, not UTF-8.
    _git(repo, 'config', 'i18n.logOutputEncoding', 'ISO-8859-1')
    module = _load()
    with pytest.raises(module.GateError, match=r'cannot read the subject: `git .* log .* not UTF-8'):
        module.git(repo, 'log', '-1', '--format=%s', what='read the subject')
    with pytest.raises(module.GateError, match=r'cannot list what main holds .* not UTF-8'):
        module.stale_commits(repo, 'pr', 'main', ['scripts/ci/gate.py'])


def test_the_ancestry_answer_and_the_listing_refusal_read_through_the_shared_decoder(tmp_path):
    repo = _repo(tmp_path, 'python3 scripts/ci/gate.py', {'scripts/ci/gate.py': '# gate\n'})
    _main_appends_a_comment(repo, 'scripts/ci/gate.py')
    module = _load()
    assert module.head_is_mains_history(repo, 'pr', 'main') is True
    assert module.head_is_mains_history(repo, 'main', 'pr') is False
    with pytest.raises(module.GateError, match=r'cannot list what main holds .* exited 128'):
        module.stale_commits(repo, 'not-a-ref', 'main', ['scripts/ci/gate.py'])


def test_the_gate_decodes_utf8_whatever_the_locale_codec(tmp_path):
    """Windows' cp1252 default, stood in for by an uncoerced C locale with UTF-8 mode off.

    The gate script and the main commit's subject carry U+201D, whose UTF-8 bytes
    end in 0x9d: undefined in cp1252, outside ASCII.
    """
    env = {**os.environ, 'GITHUB_EVENT_NAME': 'pull_request', 'PYTHONUTF8': '0',
           'PYTHONCOERCECLOCALE': '0', 'LC_ALL': 'C', 'PYTHONIOENCODING': 'utf-8'}
    probe = subprocess.run([sys.executable, '-c', 'import locale; print(locale.getencoding())'],
                           check=True, capture_output=True, text=True, env=env).stdout.strip()
    if probe.lower().replace('-', '') == 'utf8':
        assert sys.platform == 'darwin', f'the forced locale codec is {probe}, so this control would be vacuous'
        pytest.skip('this platform keeps a UTF-8 locale codec under LC_ALL=C')
    repo = _repo(tmp_path, 'python3 scripts/ci/gate.py', {
        'scripts/ci/gate.py': '# “quoted” — not ASCII\nimport helper\n',
        'scripts/ci/helper.py': 'thing = 1\n'})
    _git(repo, 'checkout', 'main')
    (repo / 'scripts/ci/helper.py').write_text('thing = 2\n', encoding='utf-8', newline='\n')
    _git(repo, 'commit', '-qam', 'chore: touch the “helper”')  # -q: no subject on this suite's own text-mode pipe
    _git(repo, 'push', 'origin', 'main')
    _git(repo, 'checkout', 'pr')
    done = subprocess.run([sys.executable, str(GATE), '--root', str(repo)], check=False,
                          capture_output=True, encoding='utf-8', env=env)
    assert done.returncode == 1, (done.stdout, done.stderr)
    assert 'chore: touch the “helper”' in done.stdout, (done.stdout, done.stderr)
    assert '    scripts/ci/helper.py\n' in done.stdout, done.stdout


def test_the_gate_imports_its_sibling_as_a_package_too():
    """Imported as `scripts.ci.gate_base_freshness`, the gate takes its sibling relatively."""
    module = importlib.import_module('scripts.ci.gate_base_freshness')
    assert module.gate_script_reach.__name__ == 'scripts.ci.gate_script_reach'
