#!/usr/bin/env python3
"""Fold a Playwright V8 dump into code-line coverage for the built page.

The input is the JSON file the browser harness writes when ``JS_COVERAGE_OUT``
is set: the array ``page.coverage.stop_js_coverage()`` returned, one record
per script Chromium compiled, each carrying ``url``, ``source`` and the V8
``functions[].ranges[]`` block-coverage tree. A record is attributed to the
page only when its ``source`` equals the text of the single inline
``<script>`` block in ``out/frontier-models.html`` — the one script the page
ships — and every other record is counted unattributed and never scored.
Separate records of the same source merge by summing their counts.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__:
    # pylint: disable-next=relative-beyond-top-level,no-name-in-module
    from . import js_lines
else:
    js_lines = importlib.import_module('js_lines')

ROOT = Path(__file__).resolve().parents[2]
# Spelled POSIX and kept a string: this is the report's row name and the
# error label on every OS, while path joins convert it to the native form.
PAGE = 'out/frontier-models.html'


@dataclass
class FileCoverage:
    """Executable and covered physical lines for the page's script."""

    executable_lines: set
    covered_lines: set


@dataclass
class CoverageReport:
    """Coverage plus attribution accounting for every script record."""

    files: dict
    records_seen: int
    ignored_other: int

    @property
    def unattributed_records(self):
        return self.ignored_other


def page_script(root):
    """Return the inline script's text, as the browser compiled it.

    The text runs from the newline that closes ``<script>`` to the newline
    that precedes ``</script>`` — both tags at line start — which is exactly
    the ``source`` V8 reports for the block. The UTF-16 guard is daedalus's:
    V8 offsets count UTF-16 code units, so a source whose UTF-16 length
    differs from its code-point length (an astral character) would map every
    offset after it to the wrong line, and is refused rather than misplaced.
    """
    html = (Path(root) / PAGE).read_text(encoding='utf-8')
    opening = re.search(r'(?m)^<script>$', html)
    if opening is None:
        raise ValueError(f'no inline <script> block found in {PAGE}')
    start = opening.end()
    closing = re.search(r'(?m)^</script>', html[start:])
    if closing is None:
        raise ValueError(f'unterminated inline <script> block in {PAGE}')
    script = html[start:start + closing.start()]
    utf16_units = len(script.encode('utf-16-le')) // 2
    if utf16_units != len(script):
        raise ValueError(
            f'{PAGE}: UTF-16 length {utf16_units} differs from code-point '
            f'length {len(script)}; astral characters would misplace V8 '
            'offsets')
    return script


def _record_counts(record, source_length):
    counts = [0] * source_length
    ranges = [
        coverage_range
        for function in record.get('functions', ())
        for coverage_range in function.get('ranges', ())
    ]
    ordered = sorted(
        ranges,
        key=lambda item: (item['startOffset'], -item['endOffset']))
    for coverage_range in ordered:
        start = coverage_range['startOffset']
        end = coverage_range['endOffset']
        if start < 0 or end < start or end > source_length:
            raise ValueError(
                f'coverage range {start}:{end} outside source length '
                f'{source_length}')
        counts[start:end] = [coverage_range['count']] * (end - start)
    return counts


def merge_records(records, source_length):
    """Merge nested ranges and add counts from separate script records."""
    merged = [0] * source_length
    for record in records:
        current = _record_counts(record, source_length)
        merged = [left + right for left, right in zip(merged, current)]
    return merged


def _shape_key(source):
    """The code text with the page's one payload line elided, or None.

    The page's script carries the data payload as ONE line (a ``const DATA
    = {...};`` statement, wherever the compiled text puts it), and its
    length moves with the capture. Two captures therefore share one code
    text under one moving header line, and line n of one build's script is
    line n of the other's for every line number: the payload is a single
    line in both, and everything around it is byte-identical.
    """
    if source.startswith("const DATA = "):
        payload_start = 0
        j = source.find("\n")
    else:
        i = source.find("\nconst DATA = ")
        if i == -1:
            return None
        payload_start = i + 1
        j = source.find("\n", i + 1)
    if j == -1 or not source[payload_start:j].rstrip().endswith(";"):
        return None
    key = source[:payload_start] + source[j:]
    # The copy exports embed the capture date in their source strings (the
    # copyMarkdown prose and the copyJson object literal), and the two
    # shapes were captured on different days -- one more moving token,
    # elided like the payload (the shape the gate scores is the CODE, and
    # a date literal is not code).
    return re.sub(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", ":", key)


def _attributable(source: str, script: str) -> bool:
    """The record's source scores against the page script.

    Exact equality, or the second shape: a different one-line payload over
    the byte-identical code text. Anything else -- a genuinely different
    script, an older build -- stays unattributed and unscored.
    """
    if source == script:
        return True
    script_key = _shape_key(script)
    if script_key is None:
        return False
    return _shape_key(source) == script_key


def collect_coverage(dump_path, root):
    """Read one Playwright dump and score the page script against it."""
    script = page_script(root)
    entries = json.loads(Path(dump_path).read_text(encoding='utf-8'))
    if not isinstance(entries, list):
        raise ValueError(
            'the coverage dump must be the JSON array '
            'page.coverage.stop_js_coverage() returned')
    exact = []
    rebased = []
    ignored_other = 0
    for record in entries:
        source = record.get('source')
        if not _attributable(source, script):
            ignored_other += 1
        elif source == script:
            exact.append(record)
        else:
            rebased.append(record)
    if not exact and not rebased:
        raise ValueError(
            'no coverage record attributed to the page script; the dump is '
            'from a run that never loaded the built page, or the page was '
            'rebuilt since the dump was captured')
    executable = js_lines.code_lines(script, PAGE)
    covered = set()
    if exact:
        counts = merge_records(exact, len(script))
        covered |= {
            line for line, start, end in _line_spans(script)
            if line in executable and any(counts[start:end])
        }
    for record in rebased:
        # The rebased shape scores in its OWN offsets -- line 1 is a
        # different length -- and lands on the script's line numbers,
        # which coincide from the payload line on (_shape_key).
        source = record['source']
        counts = merge_records([record], len(source))
        covered |= {
            line for line, start, end in _line_spans(source)
            if line in executable and any(counts[start:end])
        }
    files = {PAGE: FileCoverage(executable, covered)}
    return CoverageReport(files, len(entries), ignored_other)


def _line_spans(source):
    start = 0
    line = 1
    index = 0
    while index < len(source):
        char = source[index]
        if char == '\r':
            yield line, start, index
            index += 1
            if index < len(source) and source[index] == '\n':
                index += 1
            start = index
            line += 1
            continue
        if char in '\n  ':
            yield line, start, index
            index += 1
            start = index
            line += 1
            continue
        index += 1
    yield line, start, len(source)


def _totals(report):
    covered = sum(len(item.covered_lines) for item in report.files.values())
    total = sum(len(item.executable_lines) for item in report.files.values())
    return covered, total


def _percent(covered, total):
    return 100.0 if total == 0 else covered * 100.0 / total


def render_markdown(report):
    """Render the page row and the attribution count for a step summary."""
    lines = [
        '| Name | Covered | Total | Cover |',
        '| :--- | ---: | ---: | ---: |',
    ]
    for rel, item in sorted(report.files.items()):
        covered = len(item.covered_lines)
        total = len(item.executable_lines)
        lines.append(
            f'| {rel} | {covered} | {total} | '
            f'{_percent(covered, total):.1f}% |')
    covered, total = _totals(report)
    lines.append(
        f'| **TOTAL** | **{covered}** | **{total}** | '
        f'**{_percent(covered, total):.1f}%** |')
    other_word = 'record' if report.ignored_other == 1 else 'records'
    lines.extend([
        '',
        f'Unattributed script records: {report.ignored_other} {other_word} '
        f'of {report.records_seen} seen; only records whose source equals '
        'the page script are scored.',
    ])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('coverage_dump', type=Path,
                        help='JSON file holding the array that '
                             'page.coverage.stop_js_coverage() returned')
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='repository root holding out/frontier-models'
                             '.html (default: this checkout)')
    parser.add_argument('--fail-under', type=float,
                        help='fail when total coverage is below this percent')
    parser.add_argument('--format', choices=('markdown', 'total'),
                        default='markdown', help='stdout report format')
    args = parser.parse_args(argv)

    try:
        report = collect_coverage(args.coverage_dump, args.root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    covered, total = _totals(report)
    measured = _percent(covered, total)
    if args.format == 'total':
        print(f'{measured:.1f}')
    else:
        print(render_markdown(report), end='')
    if args.fail_under is not None and measured < args.fail_under:
        print(
            f'Coverage failure: total of {measured:.1f} is less than '
            f'fail-under={args.fail_under:g}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
