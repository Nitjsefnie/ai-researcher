"""Shared apt archive cache contract, independent of either consumer."""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'ci'))


@pytest.fixture(name='cache_module')
def fixture_cache_module():
    return importlib.import_module('apt_deb_cache')


@pytest.mark.parametrize('marker, complete, hit', [
    ('identity', True, True), ('stale', True, False),
    (None, True, False), ('identity', False, False),
])
def test_hit_requires_marker_and_every_package(cache_module, tmp_path,
                                               marker, complete, hit):
    (tmp_path / 'liba_1_amd64.deb').write_bytes(b'a')
    (tmp_path / 'unrelated_1_amd64.deb').write_bytes(b'other')
    if complete:
        (tmp_path / 'valgrind_2_amd64.deb').write_bytes(b'v')
    if marker is not None:
        (tmp_path / 'cache-key').write_text(marker, encoding='utf-8')
    debs = cache_module.cached_debs(tmp_path, {'liba', 'valgrind'}, 'identity')
    assert bool(debs) == hit
    if hit:
        assert [path.name for path in debs] == [
            'liba_1_amd64.deb', 'valgrind_2_amd64.deb']


@pytest.mark.parametrize('copy_code, install_code, expected', [
    (0, 0, True), (1, 0, False), (0, 100, False),
])
def test_restore_copies_before_no_download_install(
        cache_module, tmp_path, monkeypatch, copy_code, install_code, expected):
    calls = []
    archive = tmp_path / 'valgrind_2_amd64.deb'

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=copy_code if 'cp' in command else install_code)

    monkeypatch.setattr(cache_module.subprocess, 'run', run)
    monkeypatch.setattr(cache_module, 'APT_ARCHIVES', tmp_path / 'archives')
    assert cache_module.restore_install([archive], ['valgrind']) == expected
    assert calls[0] == ['sudo', 'cp', '--', str(archive.resolve()),
                        str(tmp_path / 'archives')]
    assert calls[1:] == ([] if copy_code else [[
        'sudo', 'apt-get', 'install', '-y', '--no-install-recommends',
        '--no-download', 'valgrind']])


@pytest.mark.parametrize('complete', [True, False])
def test_backfill_marks_only_complete_package_sets(
        cache_module, tmp_path, monkeypatch, complete):
    archives, cache = tmp_path / 'archives', tmp_path / 'cache'
    archives.mkdir()
    cache.mkdir()
    (archives / 'valgrind_2_amd64.deb').write_bytes(b'v')
    (archives / 'other_2_amd64.deb').write_bytes(b'ignore')
    if complete:
        (archives / 'liba_1_amd64.deb').write_bytes(b'a')
    monkeypatch.setattr(cache_module, 'APT_ARCHIVES', archives)
    assert cache_module.backfill(cache, {'liba', 'valgrind'}, 'identity') == complete
    if complete:
        assert (cache / 'cache-key').read_text(encoding='utf-8') == 'identity'
        assert (cache / 'valgrind_2_amd64.deb').read_bytes() == b'v'
        assert (cache / 'liba_1_amd64.deb').read_bytes() == b'a'
        assert not (cache / 'other_2_amd64.deb').exists()
    else:
        assert not list(cache.iterdir())


def test_output_appends_without_clobbering(cache_module, tmp_path, monkeypatch):
    output = tmp_path / 'output'
    output.write_text('prior=value\n', encoding='utf-8')
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    cache_module.emit_output('cache-key', 'identity')
    cache_module.emit_output('cache-changed', 'true')
    assert output.read_text(encoding='utf-8') == (
        'prior=value\ncache-key=identity\ncache-changed=true\n')
    monkeypatch.delenv('GITHUB_OUTPUT')
    cache_module.emit_output('cache-changed', 'true')
    assert output.read_text(encoding='utf-8').count('cache-changed=') == 1


@pytest.mark.parametrize('filename, complete', [
    ('valgrind_2_amd64.deb', False),
    ('valgrind_1%3a2_amd64.deb', True),
    ('valgrind_1%3A2_amd64.deb', True),
    ('valgrind_1%3a3_amd64.deb', False),
    ('valgrind_broken.deb', False),
])
def test_exact_backfill_requires_every_resolved_version(
        cache_module, tmp_path, monkeypatch, filename, complete):
    archives, cache = tmp_path / 'archives', tmp_path / 'cache'
    archives.mkdir()
    cache.mkdir()
    for name in (filename, 'liba_3_amd64.deb', 'liba_4_amd64.deb', 'other_1_amd64.deb'):
        (archives / name).write_bytes(name.encode('utf-8'))
    monkeypatch.setattr(cache_module, 'APT_ARCHIVES', archives)
    assert cache_module.backfill(
        cache, {'liba', 'valgrind'}, 'identity',
        resolved={('liba', '3'), ('valgrind', '1:2')}) == complete
    if complete:
        assert sorted(path.name for path in cache.glob('*.deb')) == sorted([
            filename, 'liba_3_amd64.deb'])
        assert (cache / filename).read_bytes() == filename.encode('utf-8')
        assert (cache / 'cache-key').read_text(encoding='utf-8') == 'identity'
    else:
        assert not list(cache.iterdir())
