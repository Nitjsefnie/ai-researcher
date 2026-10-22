"""Valgrind's resolver and cache/mirror lifecycle with no real installs."""
import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'ci'))

# Observed with apt-get -s and an empty dpkg status file on Debian.
TRANSCRIPT = '''Reading package lists...
Building dependency tree...
Reading state information...
The following additional packages will be installed:
  gcc-14-base libc6 libc6-dbg libgcc-s1
Suggested packages:
  glibc-doc debconf | debconf-2.0 libc-l10n locales
Recommended packages:
  libidn2-0 gdb python3
The following NEW packages will be installed:
  gcc-14-base libc6 libc6-dbg libgcc-s1 valgrind
0 upgraded, 5 newly installed, 0 to remove and 0 not upgraded.
Inst gcc-14-base (14.2.0-19 Debian:13.7/stable [amd64])
Inst libgcc-s1 (14.2.0-19 Debian:13.7/stable [amd64]) []
Inst libc6 (2.41-12+deb13u4 Debian:13.7/stable [amd64])
Inst libc6-dbg (2.41-12+deb13u4 Debian:13.7/stable [amd64])
Inst valgrind (1:3.24.0-3 Debian:13.7/stable [amd64])
Conf gcc-14-base (14.2.0-19 Debian:13.7/stable [amd64])
Conf libgcc-s1 (14.2.0-19 Debian:13.7/stable [amd64])
Conf libc6 (2.41-12+deb13u4 Debian:13.7/stable [amd64])
Conf libc6-dbg (2.41-12+deb13u4 Debian:13.7/stable [amd64])
Conf valgrind (1:3.24.0-3 Debian:13.7/stable [amd64])
'''
RESOLVED = ['gcc-14-base=14.2.0-19', 'libc6-dbg=2.41-12+deb13u4',
            'libc6=2.41-12+deb13u4', 'libgcc-s1=14.2.0-19', 'valgrind=1:3.24.0-3']


@pytest.fixture(name='installer')
def fixture_installer():
    return importlib.import_module('install_valgrind')


@pytest.mark.parametrize('transcript, expected', [
    (TRANSCRIPT, RESOLVED),
    ('0 upgraded, 0 newly installed, 1 reinstalled, 0 to remove and 16 not upgraded.\n'
     'Inst valgrind [1:3.24.0-3] (1:3.24.0-3 Debian:13.7/stable [amd64])\n',
     ['valgrind=1:3.24.0-3']),
    ('1 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n'
     'Inst libc6:amd64 [2.40] (2.41 Debian:13.7/stable [amd64])\n'
     'Inst valgrind (1:3.24.0-3 Debian:13.7/stable [amd64])\n',
     ['libc6:amd64=2.41', 'valgrind=1:3.24.0-3']),
])
def test_resolver_parses_simulation_and_validates_command(
        installer, monkeypatch, transcript, expected):
    def run(command, **kwargs):
        assert command == ['apt-get', '-s', 'install', '--no-install-recommends', 'valgrind']
        assert kwargs['encoding'] == 'utf-8'
        assert kwargs['capture_output'] is True
        assert kwargs['env']['LC_ALL'] == 'C'
        return SimpleNamespace(returncode=0, stdout=transcript, stderr='')

    monkeypatch.setattr(installer.subprocess, 'run', run)
    assert installer.dependency_packages() == expected


@pytest.mark.parametrize('output, code', [
    (TRANSCRIPT.replace('5 newly installed', '6 newly installed'), 0),
    (TRANSCRIPT.replace('Inst libc6 (', 'Inst libc6 ? ('), 0),
    (TRANSCRIPT.replace('Inst libc6 (', 'Inst --evil ('), 0),
    (TRANSCRIPT.replace('0 upgraded, 5 newly installed, 0 to remove and 0 not upgraded.\n', ''), 0),
    ('0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n', 0),
    (TRANSCRIPT, 100),
])
def test_resolver_rejects_incomplete_unparseable_or_failed_simulation(
        installer, monkeypatch, output, code):
    monkeypatch.setattr(installer.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=code, stdout=output, stderr='apt error'))
    with pytest.raises(ValueError, match='simulation'):
        installer.dependency_packages()


def test_key_tracks_sorted_names_and_versions(installer):
    expected = hashlib.sha256(json.dumps(RESOLVED).encode('utf-8')).hexdigest()
    assert installer.dependency_key(list(reversed(RESOLVED))) == expected
    assert installer.dependency_key(RESOLVED[:-1] + ['valgrind=2']) != expected


@pytest.fixture(name='environment')
def fixture_environment(installer, tmp_path, monkeypatch):
    cache, archives = tmp_path / 'cache', tmp_path / 'archives'
    archives.mkdir()
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setattr(installer.apt_deb_cache, 'APT_ARCHIVES', archives)
    state = SimpleNamespace(present=False, install_code=0, update_code=0,
                            cache_code=0, incomplete=False, calls=[], configs=[])
    monkeypatch.setattr(installer.shutil, 'which', lambda _: '/bin/valgrind' if state.present else None)
    monkeypatch.setattr(installer.apt_deb_cache, 'configure_apt_acquire',
                        lambda: state.configs.append(True))

    def run(command, **kwargs):
        state.calls.append(command)
        if '-s' in command:
            return SimpleNamespace(returncode=0, stdout=TRANSCRIPT, stderr='')
        if 'cp' in command:
            for source in command[3:-1]:
                shutil.copyfile(source, archives / Path(source).name)
        if 'update' in command:
            return SimpleNamespace(returncode=state.update_code)
        if 'install' in command:
            code = state.cache_code if '--no-download' in command else state.install_code
            if code == 0:
                state.present = True
                for item in RESOLVED[:-1] if state.incomplete else RESOLVED:
                    name, version = item.split('=', 1)
                    version = version.replace(':', '%3a')
                    (archives / f'{name}_{version}_amd64.deb').write_bytes(name.encode('utf-8'))
            return SimpleNamespace(returncode=code)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(installer.subprocess, 'run', run)
    return SimpleNamespace(cache=cache, archives=archives, output=output, state=state)


def test_present_guard_has_no_outputs_or_subprocesses(installer, environment):
    env = environment
    env.state.present = True
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert env.state.calls == []
    assert not env.output.exists()
    assert not env.cache.exists()


def test_miss_backfills_and_updated_warm_hit_installs_offline(installer, environment, capsys):
    env = environment
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert env.state.calls[0] == ['sudo', 'apt-get', 'update']
    assert '-s' in env.state.calls[1]
    assert env.state.calls[2] == [
        'sudo', 'apt-get', 'install', '-y', '--no-install-recommends', *RESOLVED]
    assert env.state.configs == [True]
    assert sorted(path.name for path in env.cache.glob('*.deb')) == sorted(
        path.name for path in env.archives.glob('*.deb'))
    assert (env.cache / 'valgrind_1%3a3.24.0-3_amd64.deb').read_bytes() == b'valgrind'
    assert 'cache-changed=true' in env.output.read_text(encoding='utf-8')
    env.output.write_text('', encoding='utf-8')
    env.state.present = False
    env.state.calls.clear()
    env.state.configs.clear()
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert len(env.state.calls) == 4
    assert env.state.calls[0] == ['sudo', 'apt-get', 'update']
    assert 'cp' in env.state.calls[2]
    assert env.state.calls[3] == ['sudo', 'apt-get', 'install', '-y',
                                  '--no-install-recommends', '--no-download', *RESOLVED]
    assert env.state.configs == [True]
    assert 'cache-changed' not in env.output.read_text(encoding='utf-8')
    assert 'cache' in capsys.readouterr().out


@pytest.mark.parametrize('failure', ['resolver', 'empty', 'cache-install', 'partial',
                                     'corrupt', 'cache-directory', 'output'])
def test_cache_failures_degrade_to_mirror(installer, environment, monkeypatch,
                                          capsys, failure):
    env = environment
    if failure in ('cache-install', 'partial', 'corrupt'):
        assert installer.main(['--deps-cache', str(env.cache)]) == 0
        env.state.present = False
        env.output.write_text('', encoding='utf-8')
        if failure == 'cache-install':
            env.state.cache_code = 100
        elif failure == 'partial':
            (env.cache / 'valgrind_1%3a3.24.0-3_amd64.deb').unlink()
        else:
            (env.cache / 'cache-key').write_bytes(b'\xff')
    elif failure == 'cache-directory':
        env.cache.write_bytes(b'not a directory')
    elif failure == 'output':
        monkeypatch.setenv('GITHUB_OUTPUT', str(env.output / 'missing' / 'output'))
    else:
        def resolve():
            if failure == 'resolver':
                raise OSError('simulation unavailable')
            return []

        monkeypatch.setattr(installer, 'dependency_packages', resolve)
    env.state.calls.clear()
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert env.state.calls[0] == ['sudo', 'apt-get', 'update']
    targets = ['valgrind'] if failure in ('resolver', 'empty') else RESOLVED
    assert env.state.calls[-1] == [
        'sudo', 'apt-get', 'install', '-y', '--no-install-recommends', *targets]
    if failure not in ('partial',):
        assert capsys.readouterr().err


@pytest.mark.parametrize('failure', ['incomplete', 'copy'])
def test_incomplete_or_failed_backfill_does_not_signal_repair(
        installer, environment, monkeypatch, failure):
    env = environment
    if failure == 'incomplete':
        env.state.incomplete = True
    else:
        def fail(*args):
            raise OSError('cache full')

        monkeypatch.setattr(installer.apt_deb_cache.shutil, 'copyfile', fail)
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert not (env.cache / 'cache-key').exists()
    assert 'cache-changed' not in env.output.read_text(encoding='utf-8')


@pytest.mark.parametrize('failure', ['update', 'install', 'spawn', 'no-binary'])
def test_nonzero_only_when_valgrind_remains_absent(
        installer, environment, monkeypatch, failure):
    env = environment
    if failure == 'update':
        env.state.update_code = 100
    elif failure == 'install':
        env.state.install_code = 100
    elif failure == 'no-binary':
        monkeypatch.setattr(installer.shutil, 'which', lambda _: None)
    else:
        def fail(*args, **kwargs):
            raise OSError('sudo unavailable')

        monkeypatch.setattr(installer.subprocess, 'run', fail)
    assert installer.main(['--deps-cache', str(env.cache)]) != 0
    assert not (env.cache / 'cache-key').exists()
    if failure == 'update':
        assert env.state.calls == [['sudo', 'apt-get', 'update']]
        assert not env.output.exists()


def test_failed_mirror_with_binary_present_exits_zero_without_publishing_repair(
        installer, environment, monkeypatch):
    env = environment
    run = installer.subprocess.run

    def incomplete_install(command, **kwargs):
        result = run(command, **kwargs)
        if command[:3] == ['sudo', 'apt-get', 'install']:
            return SimpleNamespace(returncode=100)
        return result

    monkeypatch.setattr(installer.subprocess, 'run', incomplete_install)
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert not (env.cache / 'cache-key').exists()
    assert 'cache-changed' not in env.output.read_text(encoding='utf-8')


def test_update_drift_repairs_new_identity_then_restores_it(
        installer, environment, monkeypatch):
    env = environment
    state = env.state
    candidate = '1'
    installs = []

    def run(command, **kwargs):
        nonlocal candidate
        state.calls.append(command)
        if 'update' in command:
            candidate = '2'
        elif '-s' in command:
            return SimpleNamespace(
                returncode=0, stderr='', stdout=(
                    '0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.\n'
                    f'Inst valgrind ({candidate} Debian:13.7/stable [amd64])\n'))
        elif 'cp' in command:
            for source in command[3:-1]:
                shutil.copyfile(source, env.archives / Path(source).name)
        elif 'install' in command:
            installs.append(command)
            if '--no-download' in command:
                assert (env.archives / f'valgrind_{candidate}_amd64.deb').is_file()
            else:
                (env.archives / f'valgrind_{candidate}_amd64.deb').write_bytes(b'new version')
            state.present = True
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(installer.subprocess, 'run', run)
    new_key = hashlib.sha256(json.dumps(['valgrind=2']).encode('utf-8')).hexdigest()
    for warm in (False, True):
        candidate = '1'
        state.present = False
        state.calls.clear()
        env.output.write_text('', encoding='utf-8')
        assert installer.main(['--deps-cache', str(env.cache)]) == 0
        assert (env.cache / 'cache-key').read_text(encoding='utf-8') == new_key
        outputs = env.output.read_text(encoding='utf-8').splitlines()
        assert f'cache-key={new_key}' in outputs
        assert ('cache-changed=true' in outputs) != warm
        assert state.calls[0] == ['sudo', 'apt-get', 'update']
        assert '-s' in state.calls[1]
        assert installs[-1][-1] == 'valgrind=2'
        assert ('--no-download' in installs[-1]) == warm


def test_version_mismatch_in_backfill_is_loud_and_never_published(
        installer, environment, monkeypatch, capsys):
    env = environment
    run = installer.subprocess.run

    def wrong_version(command, **kwargs):
        result = run(command, **kwargs)
        if command[:3] == ['sudo', 'apt-get', 'install']:
            archive = env.archives / 'valgrind_1%3a3.24.0-3_amd64.deb'
            archive.rename(env.archives / 'valgrind_2_amd64.deb')
        return result

    monkeypatch.setattr(installer.subprocess, 'run', wrong_version)
    assert installer.main(['--deps-cache', str(env.cache)]) == 0
    assert not (env.cache / 'cache-key').exists()
    assert 'cache-changed' not in env.output.read_text(encoding='utf-8')
    assert 'backfill' in capsys.readouterr().err
