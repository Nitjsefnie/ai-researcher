#!/usr/bin/env python3
"""Read, validate, and atomically publish CI threshold state.

``--check`` validates the document's structure AND its history: the
working-tree copy is judged against the copy committed at HEAD with the
same never-lower rule the pull-request guard applies, so a lowered
document that keeps the calibration gap cannot slip a direct push past
``--check`` on its own.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

if __package__:
    # pylint: disable-next=relative-beyond-top-level,no-name-in-module
    from . import check_ratchets
else:
    check_ratchets = importlib.import_module('check_ratchets')

THRESHOLDS = (Path(__file__).resolve().parents[2]
              / '.github' / 'ci-thresholds.json')
# The fixed gap between a recorded measured value and its floor, and the
# hysteresis a new measurement must clear before the floor moves: both
# yardstick values, not tunables.
CALIBRATION_GAP = Decimal('1.5')
_SCHEMA_VERSION = 1
# Every coverage language the ratchet gates: python from the pytest run over
# the repo, javascript from the browser suite over the page's inline script.
COVERAGE_LANGUAGES = ('python', 'javascript')
_TOP_LEVEL_FIELDS = ('schema_version', 'coverage')
_COVERAGE_FIELDS = ('measured', 'floor')
_FIELD_LABELS = {
    'thresholds': 'field: {field}',
    'coverage': 'coverage language: {field}',
}


def _reject_constant(value):
    raise ValueError(f'non-finite JSON number: {value}')


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _decode(raw):
    try:
        text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        return json.loads(
            text, parse_float=Decimal, parse_int=Decimal,
            parse_constant=_reject_constant, object_pairs_hook=_object_pairs)
    except UnicodeDecodeError as error:
        raise ValueError(f'invalid thresholds JSON: {error}') from None
    except json.JSONDecodeError as error:
        raise ValueError(f'invalid thresholds JSON: {error}') from None


def _number(value, name):
    if isinstance(value, bool) or not isinstance(
            value, (int, float, Decimal)):
        raise ValueError(f'{name} must be a JSON number')
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{name} must be a JSON number') from None
    if not result.is_finite():
        raise ValueError(f'{name} must be finite')
    return result


def _required_fields(value, expected, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    label = _FIELD_LABELS.get(name, f'field: {name}.{{field}}')
    for field in expected:
        if field not in value:
            raise ValueError(f'missing {label.format(field=field)}')
    expected_set = set(expected)
    for field in value:
        if field not in expected_set:
            raise ValueError(f'unknown {label.format(field=field)}')


def coverage_value(value, name):
    result = _number(value, name)
    if result < 0 or result > 100:
        raise ValueError(f'{name} must be between 0.0 and 100.0')
    exponent = result.as_tuple().exponent
    # The canonical spelling of a coverage number carries exactly one
    # decimal place (92.0, never 92 or 92.00): it is what the ratchet
    # writes and what coverage --precision=1 measures.
    if not isinstance(exponent, int) or exponent != -1:
        raise ValueError(f'{name} must have exactly one decimal place')
    return result


def normalise(data):
    _required_fields(data, _TOP_LEVEL_FIELDS, 'thresholds')
    schema = _number(data['schema_version'], 'schema_version')
    if schema != _SCHEMA_VERSION or schema != schema.to_integral_value():
        raise ValueError(
            f'unsupported schema_version: {data["schema_version"]}')

    coverage_data = data['coverage']
    _required_fields(coverage_data, COVERAGE_LANGUAGES, 'coverage')
    normalised_coverage = {}
    for language in COVERAGE_LANGUAGES:
        record = coverage_data[language]
        prefix = f'coverage.{language}'
        _required_fields(record, _COVERAGE_FIELDS, prefix)
        measured = coverage_value(
            record['measured'], f'{prefix}.measured')
        floor = coverage_value(record['floor'], f'{prefix}.floor')
        if floor >= measured:
            raise ValueError(f'{prefix}.floor must be below measured')
        if measured - floor != CALIBRATION_GAP:
            raise ValueError(f'{prefix} calibration gap must be 1.5')
        normalised_coverage[language] = {
            'measured': measured,
            'floor': floor,
        }

    return {
        'schema_version': _SCHEMA_VERSION,
        'coverage': normalised_coverage,
    }


def load(path=THRESHOLDS):
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as error:
        raise ValueError(f'cannot read thresholds: {error}') from None
    return normalise(_decode(raw))


def coverage(data, language):
    if language not in COVERAGE_LANGUAGES:
        raise ValueError(f'unknown coverage language: {language}')
    normalised = normalise(data)
    record = normalised['coverage'][language]
    return record['measured'], record['floor']


def _json_ready(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _render(data):
    normalised = normalise(data)
    ready = _json_ready(normalised)
    text = json.dumps(
        ready, ensure_ascii=True, indent=2, sort_keys=True,
        allow_nan=False) + '\n'
    encoded = text.encode('utf-8')
    if normalise(_decode(encoded)) != normalised:
        raise ValueError('serialized thresholds failed validation')
    return encoded


def _remove_temp(path):
    try:
        Path(path).unlink()
    except OSError:
        # Cleanup must not hide the publication failure that prompted it.
        pass


def write(path, data):
    """Validate and atomically replace ``path`` with canonical JSON bytes."""
    target = Path(path)
    payload = _render(data)
    mode = None
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        # A new destination keeps mkstemp's restrictive default mode.
        pass
    parent = target.parent
    fd, temporary = tempfile.mkstemp(
        prefix=f'.{target.name}.', suffix='.tmp', dir=str(parent))
    temporary_path = Path(temporary)
    open_fd = fd
    replaced = False
    try:
        with os.fdopen(fd, 'wb') as handle:
            open_fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary_path, mode)
        os.replace(temporary_path, target)
        replaced = True
    finally:
        if open_fd is not None:
            try:
                os.close(open_fd)
            except OSError:
                # Preserve the primary failure when redundant close fails.
                pass
        if not replaced:
            _remove_temp(temporary_path)


def _toplevel(directory):
    """The work-tree root containing ``directory``, or None when unanchored.

    A file outside any repository has no committed copy to be lowered
    against, so the history component is skipped and the structural check
    alone judges the document.
    """
    try:
        result = subprocess.run(
            ['git', '-C', str(directory), 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, check=False)
    except OSError:
        return None  # git is missing: no history to compare against
    if result.returncode != 0:
        return None  # not a repository (or a broken one)
    return Path(result.stdout.strip())


def _never_lower_findings(path, working):
    """Findings for a working-tree document below the copy at HEAD.

    Reuses the guard's relaxation logic so the two tools cannot drift:
    the same leaves, the same directions, the same implied-floor rule.
    The history component is skipped — and never-lower holds — when the
    file sits outside any repository, when HEAD is unborn, or when no
    copy of the file is committed at HEAD, because a first document
    cannot be lowered. A committed copy that cannot be read raises: with
    it unreadable never-lower cannot be certified, so the check fails
    closed.
    """
    target = Path(path)
    top = _toplevel(target.parent)
    if top is None:
        return []
    # Both sides resolved: git reports the real path of the toplevel, so a
    # file reached through a symlinked directory (macOS /tmp, say) must be
    # resolved the same way or the relative path would not start where the
    # repository does.
    relpath = Path(os.path.relpath(
        os.path.realpath(target), os.path.realpath(top))).as_posix()
    if relpath.startswith('..'):
        return []  # outside the work tree: no committable path to compare
    try:
        commit = check_ratchets.resolve_commit(top, 'HEAD')
    except ValueError:
        return []  # unborn HEAD: no committed copy exists yet
    try:
        committed = check_ratchets.read_document(top, commit, relpath)
    except ValueError as error:
        raise ValueError(
            f'cannot certify never-lower for {relpath}: {error}') from None
    if committed is None:
        return []
    return check_ratchets.coverage_relaxations(
        committed, working, document=relpath)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true',
                       help='validate the threshold document: structure, '
                            'and that no value sits below its committed '
                            'copy at HEAD')
    modes.add_argument('--coverage-floor', choices=COVERAGE_LANGUAGES,
                       help='print one language floor')
    modes.add_argument('--coverage-measured', choices=COVERAGE_LANGUAGES,
                       help='print one language measured value')
    parser.add_argument('--thresholds', type=Path, default=THRESHOLDS)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        data = load(args.thresholds)
        if args.coverage_floor:
            _measured, floor = coverage(data, args.coverage_floor)
            print(f'{floor:.1f}')
        elif args.coverage_measured:
            measured, _floor = coverage(data, args.coverage_measured)
            print(f'{measured:.1f}')
        else:
            findings = _never_lower_findings(args.thresholds, data)
            if findings:
                for line in findings:
                    print(line, file=sys.stderr)
                return 1
            print('thresholds valid')
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
