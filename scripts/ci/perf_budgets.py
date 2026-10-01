#!/usr/bin/env python3
"""Measure the page's reader journeys against performance budgets (issue #109).

Two halves. The pure half -- budgets-document validation and the gate --
is importable from anywhere: stdlib-only at import time, playwright is
imported lazily inside the measure path only, so the no-playwright CI
matrix can import the module. The measure half builds the page to a TEMP
output (build.OUT is patched aside exactly like the fixture tests in
tests/test_browser.py; out/frontier-models.html is never written) and
drives headless Chromium through playwright, browser discovery mirroring
tests/test_browser.py: CHROMIUM_PATH, else /usr/bin/chromium when it
exists, else playwright's own download.

Measurement JSON (``--measure [--out FILE]``, schema_version 1):

    {
      "schema_version": 1,
      "page":   {"output": "frontier-models.html", "sha256": "<hex>"},
      "bytes":  {"raw": <int>, "gzip": <int>},
      "journeys": {
        "load":    {"dom_nodes_mutated": <int>, "long_task_count": <int>,
                    "wall_ms_median": <float>},
        "filter":  {...}, "sort": {...}, "hover": {...}
      }
    }

- bytes.raw / bytes.gzip: the built page's size raw and gzip -9 (mtime
  zeroed, so the byte count is deterministic).
- dom_nodes_mutated: total added+removed nodes over childList mutation
  records in the journey window. The observer is installed from an init
  script added to the page context BEFORE navigation, so the load window
  covers the entire initial script run.
- long_task_count: main-thread tasks longer than 50 ms during the window
  (PerformanceObserver 'longtask'); takeRecords() is drained at read
  time so nothing still queued escapes the count. Interaction journeys
  count only tasks starting inside the interaction span -- from the
  counter reset to the page clock taken after the last event -- so a
  background task landing outside it cannot pollute the count; the load
  journey is bounded at the settle moment (the bound is read from the
  page clock immediately after settle). Chromium runs with
  --js-flags=--expose-gc and every window is preceded by a forced
  garbage collection, so the load's garbage is collected at a
  deterministic place instead of lazily, inside whichever window it
  happens to land in.
- wall_ms_median: REPORT-ONLY, never budgeted; median of 3 fresh-page
  runs. load: Python-side goto -> settled; filter/sort: performance.now
  around the click, page-side; hover: the summed pointermove listener
  windows (capture-phase entry, end-of-task microtask exit), page-side.

"Settled" is the browser suite's readiness signal
(document.getElementById('count').textContent !== '—'), but render()
sets #count part-way through its synchronous run, so settle alone does
not bound the load window: the budgetable counters are read only after a
fixed quiet beat following settle, once the initial render has fully
completed and longtask delivery has flushed.

Journeys:
- load: a warm-up navigation, then the measured navigation -> settled.
- filter: click #fSup (Hide superseded) once.
- sort: click #tbl th[data-k='ii'] once.
- hover: hover #svg-intelligence circle.pt first, then further points
  until the tooltip names a model different from the first point's
  (nearestAt may resolve a neighbour's centre onto the first point);
  fails loudly when the chart carries fewer than two points or no point
  resolves elsewhere. The run does the identical two-hover sequence
  TWICE -- an unmeasured warm-up pass (first-touch scroll, first tooltip
  build, one-time layout) and then the measured pass -- so the window
  holds the tooltip's build-and-rebuild cost and not the page's
  first-touch costs.

Budgets document (.github/perf-budgets.json, ``--budgets PATH``):

    {
      "schema_version": 1,
      "bytes":  {"raw": <int>, "gzip": <int>},
      "journeys": {"load": {"dom_nodes_mutated": <int>,
                            "long_task_count": <int>}, ...}
    }

Every budget is an integer maximum: bools, float spellings, negatives
and non-finite numbers refused, unknown or missing fields refused,
duplicate JSON keys refused, schema_version must be 1. wall_ms_median is
conspicuously absent -- it is measured, never budgeted. gate() returns
one finding line per exceeded budget naming the path and both values (a
measured value EQUAL to its budget passes); a measurement missing a
budgeted journey is a loud error, never a pass.

Exit codes: --measure 0 on success (failures raise); --check 0 when
every budget is met, 1 when at least one is exceeded, 2 when the budgets
document is missing or invalid, 3 when the measure path itself fails
(the browser is missing or crashes, any exception escapes the
measurement) — a broken harness must never read as a budget breach.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import importlib
import io
import json
import math
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUDGETS = ROOT / '.github' / 'perf-budgets.json'
SCHEMA_VERSION = 1
PAGE_NAME = 'frontier-models.html'
JOURNEYS = ('load', 'filter', 'sort', 'hover')
JOURNEY_METRICS = ('dom_nodes_mutated', 'long_task_count')
BYTES_METRICS = ('raw', 'gzip')
# The browser suite's readiness signal (tests/test_browser.py), verbatim.
SETTLED = "document.getElementById('count').textContent !== '—'"
MEASURE_RUNS = 3
# render() sets #count part-way through its synchronous run, so settle
# alone does not bound the load window; a fixed quiet beat after settle
# does -- the page is quiescent outside interactions.
SETTLE_QUIET_MS = 250
INTERACTION_QUIET_MS = 150
VIEWPORT = {'width': 1280, 'height': 900}
_INF = float('inf')

_TOP_LEVEL_FIELDS = ('schema_version', 'bytes', 'journeys')
_BYTES_FIELDS = BYTES_METRICS
_JOURNEY_FIELDS = JOURNEY_METRICS


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
            text, parse_constant=_reject_constant,
            object_pairs_hook=_object_pairs)
    except UnicodeDecodeError as error:
        raise ValueError(f'invalid budgets JSON: {error}') from None
    except json.JSONDecodeError as error:
        raise ValueError(f'invalid budgets JSON: {error}') from None


def _integer(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be an integer')
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'{name} must be finite')
        raise ValueError(f'{name} must be an integer')
    else:
        raise ValueError(f'{name} must be a JSON number')
    if number < 0:
        raise ValueError(f'{name} must not be negative')
    return number


def _required_fields(value, expected, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    for field in expected:
        if field not in value:
            raise ValueError(f'missing field: {name}.{field}')
    for field in value:
        if field not in expected:
            raise ValueError(f'unknown field: {field}')


def validate_budgets(data):
    """Validate a decoded budgets document; return it normalised."""
    _required_fields(data, _TOP_LEVEL_FIELDS, 'budgets')
    if _integer(data['schema_version'], 'schema_version') != SCHEMA_VERSION:
        raise ValueError(
            f'unsupported schema_version: {data["schema_version"]}')
    bytes_section = data['bytes']
    _required_fields(bytes_section, _BYTES_FIELDS, 'bytes')
    normalised_bytes = {
        metric: _integer(bytes_section[metric], f'bytes.{metric}')
        for metric in _BYTES_FIELDS
    }
    journeys_section = data['journeys']
    for journey in JOURNEYS:
        if journey not in journeys_section:
            raise ValueError(f'missing journey: {journey}')
    for journey in journeys_section:
        if journey not in JOURNEYS:
            raise ValueError(f'unknown journey: {journey}')
    normalised_journeys = {}
    for journey in JOURNEYS:
        record = journeys_section[journey]
        prefix = f'journeys.{journey}'
        _required_fields(record, _JOURNEY_FIELDS, prefix)
        normalised_journeys[journey] = {
            metric: _integer(record[metric], f'{prefix}.{metric}')
            for metric in _JOURNEY_FIELDS
        }
    return {
        'schema_version': SCHEMA_VERSION,
        'bytes': normalised_bytes,
        'journeys': normalised_journeys,
    }


def load_budgets(path=BUDGETS):
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as error:
        raise ValueError(f'cannot read budgets: {error}') from None
    return validate_budgets(_decode(raw))


def gate(budgets, measurement):
    """Findings for a measurement against budgets; [] when all are met.

    A measured value EQUAL to its budget passes -- budgets are maxima.
    A measurement missing a budgeted journey (or the bytes section) is a
    loud error, never a pass.
    """
    if not isinstance(measurement, dict):
        raise ValueError('measurement must be an object')
    bytes_section = measurement.get('bytes')
    if not isinstance(bytes_section, dict):
        raise ValueError('measurement is missing section: bytes')
    findings = []
    for metric in BYTES_METRICS:
        measured = bytes_section[metric]
        budgeted = budgets['bytes'][metric]
        if measured > budgeted:
            findings.append(
                f'bytes.{metric}: head {measured} exceeds base {budgeted}')
    journeys_section = measurement.get('journeys')
    if not isinstance(journeys_section, dict):
        raise ValueError('measurement is missing section: journeys')
    for journey in JOURNEYS:
        if journey not in journeys_section:
            raise ValueError(f'measurement is missing journey: {journey}')
        record = journeys_section[journey]
        for metric in JOURNEY_METRICS:
            measured = record[metric]
            budgeted = budgets['journeys'][journey][metric]
            if measured > budgeted:
                findings.append(
                    f'journeys.{journey}.{metric}: head {measured} '
                    f'exceeds base {budgeted}')
    return findings


def _load_build():
    """Import build.py from the repo root this script lives in."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if 'build' in sys.modules:
        return sys.modules['build']
    return importlib.import_module('build')


build = _load_build()

# --- the measure path: only the code below touches playwright ---------------


_INIT_SCRIPT = """\
window.__perf = {added: 0, removed: 0, tasks: [], spans: [], entry: null};
new MutationObserver((mutations) => {
  for (const m of mutations) {
    if (m.type === 'childList') {
      window.__perf.added += m.addedNodes.length;
      window.__perf.removed += m.removedNodes.length;
    }
  }
}).observe(document, {childList: true, subtree: true});
const taskObserver = new PerformanceObserver((list) => {
  for (const e of list.getEntries()) {
    if (e.duration > 50) {
      window.__perf.tasks.push({d: e.duration, s: e.startTime});
    }
  }
});
taskObserver.observe({type: 'longtask', buffered: true});
window.__perfObs = taskObserver;
document.addEventListener('pointermove', () => {
  const entry = performance.now();
  Promise.resolve().then(() => {
    const exit = performance.now();
    if (window.__perf.entry !== null) {
      window.__perf.spans.push(exit - window.__perf.entry);
    }
    window.__perf.entry = null;
  });
  window.__perf.entry = entry;
}, {capture: true});
"""

_JS_READ = """() => {
  const p = window.__perf;
  if (window.__perfObs) {
    for (const e of window.__perfObs.takeRecords()) {
      if (e.duration > 50) p.tasks.push({d: e.duration, s: e.startTime});
    }
  }
  return {added: p.added, removed: p.removed, tasks: p.tasks,
          spans: p.spans};
}"""

_JS_RESET = """() => {
  window.__perf.added = 0;
  window.__perf.removed = 0;
  window.__perf.tasks = [];
  window.__perf.spans = [];
  return performance.now();
}"""

_JS_CLICK = """(selector) => {
  const t0 = performance.now();
  document.querySelector(selector).click();
  return {ms: performance.now() - t0, tEnd: performance.now()};
}"""

_JS_NOW = "() => performance.now()"

# Chromium is launched with --js-flags=--expose-gc so the harness can
# place the load's garbage collection BEFORE a measured window instead
# of leaving it to land lazily -- and nondeterministically -- inside one.
_JS_GC = "() => { if (window.gc) { window.gc(); window.gc(); } }"

_TOOLTIP_NAME = '#tip-intelligence .tname'
HOVER_POINTS = '#svg-intelligence circle.pt'


def _chromium_executable():
    candidate = os.environ.get('CHROMIUM_PATH') or '/usr/bin/chromium'
    return Path(candidate) if Path(candidate).exists() else None


def _new_page(browser):
    page = browser.new_page(viewport=VIEWPORT)
    page.context.add_init_script(_INIT_SCRIPT)
    return page


def _read_counters(page, t0=-1.0, t_end=_INF):
    """Counters, with long tasks filtered to the window [t0, t_end].

    The default window is unbounded; the load journey passes [0, settle].
    Interaction journeys pass the reset time and the page clock taken
    right after the last event, so a background task landing in the
    post-interaction quiet beat cannot pollute the count.
    """
    read = page.evaluate(_JS_READ)
    tasks = [t for t in read['tasks'] if t0 <= t['s'] <= t_end]
    return {'added': read['added'], 'removed': read['removed'],
            'tasks': tasks, 'spans': read['spans']}


def _run_load(browser, uri):
    """One load run: a warm-up navigation, then the measured navigation.

    The warm-up absorbs the browser process's cold first-touch costs
    (allocators, font shaping, code caches) so consecutive runs see the
    same page work. The long-task window is [0, settle]: the initial
    render task starts and ends before the readiness signal, and
    everything a quiescent page does afterwards (lazy GC included) sits
    outside the journey. The bound is read from the page clock
    immediately after settle.
    """
    page = _new_page(browser)
    page.goto(uri)
    page.wait_for_function(SETTLED)
    page.wait_for_timeout(SETTLE_QUIET_MS)
    page.evaluate(_JS_GC)
    start = time.perf_counter()
    page.goto(uri)
    page.wait_for_function(SETTLED)
    settle_bound = page.evaluate(_JS_NOW)
    wall_ms = (time.perf_counter() - start) * 1000.0
    page.wait_for_timeout(SETTLE_QUIET_MS)
    read = _read_counters(page, 0.0, settle_bound)
    page.close()
    return wall_ms, read


def _settled_page(browser, uri):
    """A page settled, garbage-collected, and quiet."""
    page = _new_page(browser)
    page.goto(uri)
    page.wait_for_function(SETTLED)
    page.wait_for_timeout(SETTLE_QUIET_MS)
    page.evaluate(_JS_GC)
    return page


def _journey_page(browser, uri):
    """(page, t0): a settled page whose counters were just reset."""
    page = _settled_page(browser, uri)
    return page, page.evaluate(_JS_RESET)


def _run_click(browser, uri, selector):
    """One click-journey run; returns (dom_nodes_mutated, long_tasks, ms)."""
    page, t0 = _journey_page(browser, uri)
    click = page.evaluate(_JS_CLICK, selector)
    page.wait_for_timeout(INTERACTION_QUIET_MS)
    read = _read_counters(page, t0, click['tEnd'])
    page.close()
    mutated = read['added'] + read['removed']
    return mutated, len(read['tasks']), click['ms']


def _hover_pair(page):
    """Hover the first point, then the first point the tooltip names
    differently; return the page clock taken after the last hover."""
    points = page.locator(HOVER_POINTS)
    count = points.count()
    if count < 2:
        raise RuntimeError(
            f'{HOVER_POINTS} matched {count} points -- the hover journey '
            'needs two; the chart rendered empty or degenerate')
    points.first.hover()
    first_name = page.locator(_TOOLTIP_NAME).inner_text()
    if not first_name:
        raise RuntimeError('the tooltip named no model after the first hover')
    for index in range(1, count):
        points.nth(index).hover()
        if page.locator(_TOOLTIP_NAME).inner_text() != first_name:
            return page.evaluate(_JS_NOW)
    raise RuntimeError(
        'every point on #svg-intelligence resolves the tooltip to '
        f'{first_name!r} -- no second point could be hovered')


def _run_hover(browser, uri):
    """One hover journey: a warm-up pass (first-touch scroll, first
    tooltip build, one-time layout -- unmeasured), then the measured
    pass over the identical two hovers. Returns
    (dom_nodes_mutated, long_tasks, ms)."""
    page = _settled_page(browser, uri)
    try:
        _hover_pair(page)  # warm-up: absorbs the pass's first-touch costs
        t0 = page.evaluate(_JS_RESET)
        t_end = _hover_pair(page)
        page.wait_for_timeout(INTERACTION_QUIET_MS)
        read = _read_counters(page, t0, t_end)
    finally:
        page.close()
    mutated = read['added'] + read['removed']
    return mutated, len(read['tasks']), float(sum(read['spans']))


def _journey_record(metrics, walls):
    """{"dom_nodes_mutated": int, "long_task_count": int,
    "wall_ms_median": float} from run 1's counters and the median wall."""
    mutated, long_tasks = metrics
    return {
        'dom_nodes_mutated': mutated,
        'long_task_count': long_tasks,
        'wall_ms_median': float(statistics.median(walls)),
    }


def _build_page(build_module, output):
    """Run build.main() to `output` (stamp-less) and return the page bytes.

    build.OUT is patched aside for the build only -- the repo's
    out/frontier-models.html is never written -- and AA_SOURCE_COMMIT is
    removed so the measured page is the canonical stamp-less build.
    """
    old_out = build_module.OUT
    had_stamp = 'AA_SOURCE_COMMIT' in os.environ
    saved_stamp = os.environ.get('AA_SOURCE_COMMIT')
    build_module.OUT = output
    try:
        if had_stamp:
            del os.environ['AA_SOURCE_COMMIT']
        with contextlib.redirect_stdout(io.StringIO()):
            build_module.main()
    finally:
        build_module.OUT = old_out
        if had_stamp and saved_stamp is not None:
            os.environ['AA_SOURCE_COMMIT'] = saved_stamp
    return output.read_bytes()


def measure_journeys(browser, uri):
    """Every journey's record, measured against an already-open browser.

    The same protocol measure() uses -- MEASURE_RUNS fresh-page runs per
    journey, budgetable metrics from run 1, walls the median (report
    only). `browser` must be launched the way measure() launches its own
    (``--js-flags=--expose-gc`` included): the journeys place the load's
    garbage collection through window.gc(), which the flag is what
    provides.
    """
    load_walls = []
    load_read = None
    for _ in range(MEASURE_RUNS):
        wall_ms, read = _run_load(browser, uri)
        load_walls.append(wall_ms)
        if load_read is None:
            load_read = read
    if load_read is None:
        raise RuntimeError('the load journey measured no run')
    return {
        'load': _journey_record(
            (load_read['added'] + load_read['removed'],
             len(load_read['tasks'])), load_walls),
        'filter': _click_journey(browser, uri, '#fSup'),
        'sort': _click_journey(browser, uri, "#tbl th[data-k='ii']"),
        'hover': _hover_journey(browser, uri),
    }


def measure():
    """Build the page to a temp output and measure every journey."""
    build_module = _load_build()
    with tempfile.TemporaryDirectory(
            prefix='.perf-budgets-', dir=build_module.ROOT) as tmp:
        output = Path(tmp) / PAGE_NAME
        raw = _build_page(build_module, output)
        gzip_len = len(gzip.compress(raw, 9, mtime=0))
        uri = output.as_uri()
        # Deliberately lazy: the only playwright import in the module, so
        # the no-playwright CI matrix can import the pure half.
        # pylint: disable-next=import-outside-toplevel
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=_chromium_executable(),
                headless=True,
                args=['--no-sandbox', '--js-flags=--expose-gc'])
            try:
                journeys = measure_journeys(browser, uri)
            finally:
                browser.close()
    return {
        'schema_version': SCHEMA_VERSION,
        'page': {'output': PAGE_NAME,
                 'sha256': hashlib.sha256(raw).hexdigest()},
        'bytes': {'raw': len(raw), 'gzip': gzip_len},
        'journeys': journeys,
    }


def _click_journey(browser, uri, selector):
    metrics = None
    walls = []
    for _ in range(MEASURE_RUNS):
        run = _run_click(browser, uri, selector)
        if metrics is None:
            metrics = (run[0], run[1])
        walls.append(run[2])
    return _journey_record(metrics, walls)


def _hover_journey(browser, uri):
    metrics = None
    walls = []
    for _ in range(MEASURE_RUNS):
        run = _run_hover(browser, uri)
        if metrics is None:
            metrics = (run[0], run[1])
        walls.append(run[2])
    return _journey_record(metrics, walls)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--measure', action='store_true',
                       help='build the page to a temp output and measure '
                            'every journey; prints the measurement JSON')
    modes.add_argument('--check', action='store_true',
                       help='measure and gate against the budgets document')
    parser.add_argument('--out', type=Path, default=None,
                        help='also write the measurement JSON to FILE')
    parser.add_argument('--budgets', type=Path, default=BUDGETS,
                        help='budgets document (default: %(default)s)')
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.measure:
        text = json.dumps(measure(), indent=2, sort_keys=True,
                          allow_nan=False) + '\n'
        if args.out is not None:
            args.out.write_text(text, encoding='utf-8')
        sys.stdout.write(text)
        return 0
    try:
        budgets = load_budgets(args.budgets)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    try:
        findings = gate(budgets, measure())
    except Exception as error:  # pylint: disable=broad-except
        # Deliberately broad: whatever escapes the measure path (a missing
        # playwright, a crashed browser, a degenerate chart) is a broken
        # HARNESS, and its exit code must not collide with "exceeded" --
        # CI would otherwise read a broken gate as a budget breach.
        print(f'measurement failed: {error}', file=sys.stderr)
        return 3
    if findings:
        for line in findings:
            print(line, file=sys.stderr)
        return 1
    print('perf budgets met')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
