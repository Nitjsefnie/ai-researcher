#!/usr/bin/env python3
"""Install valgrind from cached apt archives, falling back to the mirror."""
import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__:
    from . import apt_deb_cache
else:
    apt_deb_cache = importlib.import_module('apt_deb_cache')


def dependency_packages() -> list[str]:
    """Resolve name=version pairs; reject partial or changed apt output."""
    result = subprocess.run(
        ['apt-get', '-s', 'install', '--no-install-recommends', 'valgrind'],
        capture_output=True, encoding='utf-8', check=False,
        env={**os.environ, 'LC_ALL': 'C'})
    packages = []
    summaries = []
    for line in result.stdout.splitlines():
        summary = re.fullmatch(
            r'(\d+) upgraded, (\d+) newly installed, (?:(\d+) reinstalled, )?'
            r'\d+ to remove and \d+ not upgraded\.', line)
        if summary:
            summaries.append(sum(int(count or 0) for count in summary.groups()))
        if not line.startswith('Inst '):
            continue
        match = re.fullmatch(
            r'Inst ([a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?)'
            r'(?: \[[^\]]+\])? \(([^\s()]+) [^)]*\)(?: .*)?', line)
        if match is None:
            raise ValueError(f'apt simulation has an unparseable install: {line}')
        packages.append(f'{match[1]}={match[2]}')
    if result.returncode != 0 or not packages or summaries != [len(packages)]:
        raise ValueError('apt simulation failed, returned no packages, or its '
                         f'summary disagrees with Inst rows: {result.stderr or result.stdout}')
    return sorted(set(packages))


def dependency_key(resolved: list[str]) -> str:
    """Package versions, independent of apt's display order, identify a cache."""
    return hashlib.sha256(json.dumps(sorted(resolved)).encode('utf-8')).hexdigest()


def main(argv=None) -> int:
    """Cache failures degrade; only an absent valgrind fails the step."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deps-cache', type=Path,
                        default=Path.home() / '.cache' / 'ai-researcher-valgrind-debs',
                        help='Directory holding cached apt dependency debs')
    args = parser.parse_args(argv)
    if shutil.which('valgrind'):
        print('valgrind is already present; skipping installation')
        return 0

    packages: set[str] = set()
    key = ''
    try:
        resolved = dependency_packages()
        if not resolved:
            raise ValueError('apt simulation returned no packages')
        key = dependency_key(resolved)
        print(f'apt-deb cache key: {key}', flush=True)
        apt_deb_cache.emit_output('cache-key', key)
        packages = {item.split('=', 1)[0].split(':', 1)[0] for item in resolved}
        args.deps_cache.mkdir(parents=True, exist_ok=True)
        cached = apt_deb_cache.cached_debs(args.deps_cache, packages, key)
        if cached:
            if apt_deb_cache.restore_install(cached, resolved) and shutil.which('valgrind'):
                print('valgrind installed from the apt-deb cache')
                return 0
            print('apt-deb cache install failed; using the valgrind mirror fallback',
                  file=sys.stderr, flush=True)
    except (OSError, UnicodeError, ValueError) as error:
        print(f'apt-deb cache unavailable ({error}); using the valgrind mirror fallback',
              file=sys.stderr, flush=True)

    apt_deb_cache.configure_apt_acquire()
    mirror_succeeded = False
    try:
        result = subprocess.run(['sudo', 'apt-get', 'update'], check=False)
        if result.returncode == 0:
            result = subprocess.run(
                ['sudo', 'apt-get', 'install', '-y', '--no-install-recommends', 'valgrind'],
                check=False)
        mirror_succeeded = result.returncode == 0
        if result.returncode != 0:
            print(f'valgrind mirror install exited {result.returncode}', file=sys.stderr)
    except OSError as error:
        print(f'valgrind mirror install unavailable ({error})', file=sys.stderr)
    if not shutil.which('valgrind'):
        print('valgrind is still absent after installation', file=sys.stderr)
        return 1

    if mirror_succeeded and packages and key:
        try:
            if apt_deb_cache.backfill(args.deps_cache, packages, key):
                apt_deb_cache.emit_output('cache-changed', 'true')
        except OSError as error:
            print(f'apt-deb cache backfill unavailable ({error})', file=sys.stderr, flush=True)
    print('valgrind installed through the mirror fallback')
    return 0


if __name__ == '__main__':
    sys.exit(main())
