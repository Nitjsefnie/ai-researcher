#!/usr/bin/env python3
"""Build a standalone Hugging Face and OpenRouter rankings page from git history.

    build_rankings.py [--limit 10] [--repo .] [--commit HEAD] [--out out/trending-rankings.html]

Each list has its own window of changing commits. An explicit --fresh-hf or
--fresh-or file replaces its list's oldest column with a labelled snapshot
at the supplied fetch timestamp. --identity-page preserves landed labels and
fetch timestamps for lists without fresh inputs. With neither flag, only git
history is read.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
import json
import math
import pathlib
import subprocess


@dataclass(frozen=True)
class Snapshot:
    """A list's ranks and UTC timestamp identified by a commit or fresh label."""

    commit: str
    timestamp: str
    ranks: dict[str, int]


class SnapshotColumns(HTMLParser):
    """Group SVG points by numeric x position within each tracker section."""

    def __init__(self, document: bytes):
        super().__init__()
        self.section = ""
        self.in_svg = False
        self.groups: dict[str, dict[float, Snapshot]] = {}
        self.invalid: set[str] = set()
        self.feed(document.decode("utf-8", errors="replace"))

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "section":
            self.section = attributes.get("id", "")
        if tag == "svg":
            self.in_svg = True
        if (not self.section or not self.in_svg or tag != "circle"
                or "point" not in (attributes.get("class") or "").split()):
            return
        try:
            commit, timestamp, model = (attributes[key] for key in
                                        ("data-commit", "data-timestamp", "data-model"))
            rank = int(attributes["data-rank"] or "")
            position = float(attributes["cx"] or "")
            if not commit or not timestamp or not model or rank < 1 or not math.isfinite(position):
                raise ValueError("incomplete point")
            groups = self.groups.setdefault(self.section, {})
            column = groups.setdefault(position, Snapshot(commit, timestamp, {}))
            if column.commit != commit or column.timestamp != timestamp or model in column.ranks:
                raise ValueError("inconsistent column")
            column.ranks[model] = rank
        except (KeyError, TypeError, ValueError):
            self.invalid.add(self.section)

    def handle_endtag(self, tag):
        if tag == "svg":
            self.in_svg = False
        if tag == "section":
            self.section = ""

    def newest(self, section: str) -> Snapshot | None:
        """Return the rightmost column, or refuse malformed point data."""
        groups = self.groups.get(section, {})
        if not groups or section in self.invalid:
            return None
        return groups[max(groups)]


def git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        text=True, encoding="utf-8", timeout=60).stdout


def read_history(repo: pathlib.Path, path: str, key: str, limit: int,
                 commit: str = "HEAD") -> list[Snapshot]:
    """Read the latest path-changing commits, returning oldest first."""
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    log = git(repo, "log", "-n", str(limit), "--format=%H%x20%cI", commit, "--", path)
    history = []
    for line in reversed(log.splitlines()):
        commit, timestamp = line.split(" ", 1)
        timestamp = datetime.fromisoformat(timestamp).astimezone(timezone.utc).isoformat()
        timestamp = timestamp.replace("+00:00", "Z")
        capture = json.loads(git(repo, "show", f"{commit}:{path}"))
        ranks = {model[key]: rank for rank, model in enumerate(capture["models"], 1)}
        history.append(Snapshot(commit, timestamp, ranks))
    return history


def identity_history(repo: pathlib.Path, path: str, key: str, section: str,
                     limit: int, commit: str, columns: SnapshotColumns) -> list[Snapshot]:
    """Reconstruct a landed section using its newest identity and tracked ranks."""
    column = columns.newest(section)
    if column is None:
        raise ValueError(f"identity page: {section} newest column is missing or unparseable")
    changes = git(repo, "log", "-n", "2", "--format=%H", commit, "--", path).splitlines()
    if not changes:
        raise ValueError(f"identity page: {path} history is empty")
    history = (read_history(repo, path, key, limit - 1, changes[1])
               if limit > 1 and len(changes) > 1 else [])
    capture = json.loads(git(repo, "show", f"{commit}:{path}"))
    ranks = {model[key]: rank for rank, model in enumerate(capture["models"], 1)}
    return [*history, Snapshot(column.commit, column.timestamp, ranks)]


LIGHT = """
  color-scheme: light;
  --surface-1: #fcfcfb; --page-plane: #f9f9f7;
  --text-primary: #0b0b0b; --text-secondary: #52514e;
  --grid: #e1e0d9; --axis: #c3c2b7;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --series-4: #eda100; --series-5: #e87ba4; --series-6: #008300;
  --series-7: #6250d6; --series-8: #e34948;
"""
DARK = """
  color-scheme: dark;
  --surface-1: #1a1a19; --page-plane: #0d0d0d;
  --text-primary: #f0efec; --text-secondary: #c3c2b7;
  --grid: #2c2c2a; --axis: #383835;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
  --series-4: #c98500; --series-5: #d55181; --series-6: #008300;
  --series-7: #9085e9; --series-8: #e66767;
"""
CSS = """
* { box-sizing: border-box; }
body { margin: 0; }
.viz-root {
  background: var(--page-plane); color: var(--text-primary);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  padding: 2rem clamp(1rem, 4vw, 4rem); min-height: 100vh;
}
main { margin: 0 auto; max-width: none; }
h1 { font-size: clamp(1.8rem, 4vw, 2.6rem); margin-bottom: .5rem; }
h2 { margin-bottom: .25rem; } h3 { font-size: 1rem; }
p { max-width: 85ch; color: var(--text-secondary); }
nav { display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 1.5rem 0; }
a { color: var(--text-primary); text-underline-offset: .2em; }
button { font: inherit; color: var(--text-primary); background: var(--surface-1);
  border: 1px solid var(--axis); border-radius: 4px; padding: .35rem .7rem; }
section { margin: 3rem 0; }
.chart-scroll, .table-scroll { overflow-x: auto; }
.chart { background: var(--surface-1); position: relative; }
svg { display: block; width: 100%; max-width: 100%; height: auto; }
svg text { fill: var(--text-secondary); font-size: 12px; }
.end-label { fill: var(--text-primary); font-size: 13px; }
.grid { stroke: var(--grid); stroke-width: 1; }
.series { fill: none; stroke: var(--series); stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: var(--series-dash, none); }
.point { fill: var(--series); stroke: var(--surface-1); stroke-width: 2; }
.point:focus, .point.selected { outline: none; r: 6; }
.leader { fill: none; stroke: var(--axis); stroke-width: 1; }
.crosshair { stroke: var(--axis); stroke-width: 1; pointer-events: none; }
.crosshair[hidden] { display: none; }
.legend { list-style: none; padding: 0; display: flex; gap: .5rem 1.25rem;
  flex-wrap: wrap; font-size: .85rem; color: var(--text-secondary); }
.legend li { display: flex; align-items: center; gap: .5rem; overflow-wrap: anywhere; }
.key { display: inline-block; width: 24px; flex: 0 0 24px;
  border-top: 2px solid var(--series); }
.key.dashed { border-top-style: dashed; }
.tooltip { position: fixed; z-index: 10; background: var(--surface-1);
  color: var(--text-primary); border: 1px solid var(--axis); border-radius: 4px;
  padding: .75rem; pointer-events: none; max-width: min(440px, calc(100vw - 32px));
  max-height: calc(100vh - 32px); overflow: auto; font-size: .85rem; }
.tooltip time { display: block; margin-bottom: .5rem; }
.tooltip-row { display: flex; align-items: center; gap: .5rem; }
.tooltip-row span:last-child { color: var(--text-secondary); overflow-wrap: anywhere; }
table { border-collapse: collapse; width: 100%; background: var(--surface-1);
  font-size: .85rem; font-variant-numeric: tabular-nums; }
caption { text-align: left; padding: .75rem 0; color: var(--text-secondary); }
th, td { text-align: left; vertical-align: top; border-bottom: 1px solid var(--grid);
  padding: .7rem; } td:first-child { overflow-wrap: anywhere; min-width: 16rem; }
td ul { margin: 0; padding: 0; list-style: none; min-width: 24rem; }
td time { white-space: nowrap; } .timestamp-tick { font-variant-numeric: tabular-nums; }
@media print { .tooltip, button { display: none; } .chart-scroll { overflow: visible; }
  svg { max-width: 100%; height: auto; } }
"""

JS = """
const theme = document.querySelector('#theme');
theme.addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === 'dark'
    : matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'light' : 'dark';
  theme.textContent = dark ? 'Use dark theme' : 'Use light theme';
});
for (const chart of document.querySelectorAll('.chart')) {
  const svg = chart.querySelector('svg');
  const points = Array.from(chart.querySelectorAll('.point'));
  const tip = chart.querySelector('.tooltip');
  const crosshair = chart.querySelector('.crosshair');
  if (!points.length) continue;
  function show(point, clientX, clientY) {
    const column = points.filter(p => p.getAttribute('cx') === point.getAttribute('cx'));
    points.forEach(p => p.classList.toggle('selected', p === point));
    crosshair.setAttribute('x1', point.getAttribute('cx'));
    crosshair.setAttribute('x2', point.getAttribute('cx'));
    crosshair.removeAttribute('hidden');
    tip.replaceChildren();
    const timestamp = document.createElement('time');
    timestamp.dateTime = point.dataset.timestamp;
    timestamp.textContent = point.dataset.timestamp;
    tip.append(timestamp);
    column.sort((a, b) => Number(a.dataset.rank) - Number(b.dataset.rank));
    for (const p of column) {
      const row = document.createElement('div');
      row.className = 'tooltip-row';
      const key = document.createElement('span');
      key.className = 'key' + (p.dataset.dashed === 'true' ? ' dashed' : '');
      key.style.setProperty('--series', p.style.getPropertyValue('--series'));
      const rank = document.createElement('strong');
      rank.textContent = 'Rank ' + p.dataset.rank;
      const model = document.createElement('span');
      model.textContent = p.dataset.model;
      row.append(key, rank, model);
      tip.append(row);
    }
    const left = clientX > innerWidth / 2;
    const top = clientY > innerHeight / 2;
    tip.style.left = left ? '16px' : 'auto';
    tip.style.right = left ? 'auto' : '16px';
    tip.style.top = top ? '16px' : 'auto';
    tip.style.bottom = top ? 'auto' : '16px';
    tip.hidden = false;
  }
  function hide() {
    tip.hidden = true;
    crosshair.setAttribute('hidden', '');
    points.forEach(p => p.classList.remove('selected'));
  }
  svg.addEventListener('pointermove', event => {
    const position = new DOMPoint(event.clientX, event.clientY)
      .matrixTransform(svg.getScreenCTM().inverse());
    // Snap to a commit column, then find its nearest rank point.
    const nearestX = points.reduce((best, p) =>
      Math.abs(Number(p.getAttribute('cx')) - position.x)
        < Math.abs(Number(best.getAttribute('cx')) - position.x) ? p : best);
    const column = points.filter(p => p.getAttribute('cx') === nearestX.getAttribute('cx'));
    const point = column.reduce((best, p) =>
      Math.abs(Number(p.getAttribute('cy')) - position.y)
        < Math.abs(Number(best.getAttribute('cy')) - position.y) ? p : best);
    show(point, event.clientX, event.clientY);
  });
  svg.addEventListener('pointerleave', hide);
  svg.addEventListener('focusout', hide);
  svg.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  for (const point of points) point.addEventListener('focus', () => {
    const bounds = point.getBoundingClientRect();
    show(point, bounds.x, bounds.y);
  });
}
"""


def series_style(index: int) -> str:
    """Reuse fixed hues with a dash pattern consumed only by series paths."""
    cycle, slot = divmod(index, 8)
    dash = f";--series-dash:{4 + cycle * 2} 4" if cycle else ""
    return f"--series:var(--series-{slot + 1}){dash}"


def chart_svg(history: list[Snapshot], models: list[str], identifier: str) -> str:
    """Draw ranks, commit ticks and labelled endpoints with collision leaders."""
    plot_width = max(240, (len(history) - 1) * 130)
    plot_height = max(450, len(models) * 24)
    label_width = max((len(model) * 8 for model in models), default=200) + 40
    width, height = plot_width + label_width + 80, plot_height + 130

    def x(index: int) -> float:
        return 60 + (index * plot_width / (len(history) - 1) if len(history) > 1
                     else plot_width / 2)

    def y(rank: int) -> float:
        return 35 + (rank - 1) * plot_height / 9

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {width} {height}" aria-labelledby="{identifier}-title" '
             f'aria-describedby="{identifier}-description">',
             f'<title id="{identifier}-title">Top 10 rank history</title>',
             f'<desc id="{identifier}-description">Rank 1 is at the top. '
             'Each column is a changing commit, oldest to newest. Full data follows in a table.</desc>']
    for rank in range(1, 11):
        parts.append(f'<line class="grid" x1="60" x2="{60 + plot_width}" '
                     f'y1="{y(rank):.1f}" y2="{y(rank):.1f}"/>'
                     f'<text x="40" y="{y(rank) + 4:.1f}" text-anchor="end">{rank}</text>')
    for index, snapshot in enumerate(history):
        tick = escape(snapshot.timestamp)
        parts.append(f'<line class="grid" x1="{x(index):.1f}" x2="{x(index):.1f}" '
                     f'y1="35" y2="{35 + plot_height}"/>'
                     f'<text class="timestamp-tick" x="{x(index):.1f}" '
                     f'y="{plot_height + 60}" text-anchor="middle"><title>{tick}</title>'
                     f'<tspan x="{x(index):.1f}">{tick[:10]}</tspan>'
                     f'<tspan x="{x(index):.1f}" dy="17">{tick[11:19]}</tspan>'
                     f'<tspan x="{x(index):.1f}" dy="17">{tick[19:]}</tspan></text>')
    endpoints = []
    for model_index, model in enumerate(models):
        commands = []
        carried = False
        last_index, last_rank = 0, 0
        for index, snapshot in enumerate(history):
            rank = snapshot.ranks.get(model)
            if rank is None:
                carried = False
                continue
            commands.append(f'{"L" if carried else "M"}{x(index):.1f},{y(rank):.1f}')
            carried = True
            last_index, last_rank = index, rank
        style = series_style(model_index)
        parts.append(f'<path class="series" style="{style}" data-model="{escape(model)}" '
                     f'd="{" ".join(commands)}"/>')
        for index, snapshot in enumerate(history):
            if model not in snapshot.ranks:
                continue
            rank = snapshot.ranks[model]
            description = escape(f"Rank {rank} · {model} · {snapshot.timestamp}")
            parts.append(f'<circle class="point" style="{style}" r="4" tabindex="0" '
                         f'cx="{x(index):.1f}" cy="{y(rank):.1f}" '
                         f'data-model="{escape(model)}" data-rank="{rank}" '
                         f'data-commit="{escape(snapshot.commit)}" '
                         f'data-timestamp="{escape(snapshot.timestamp)}" '
                         f'data-dashed="{str(model_index >= 8).lower()}" '
                         f'aria-label="{description}"><title>{description}</title></circle>')
        endpoints.append((y(last_rank), last_index, model))
    # Separate converging labels and connect each to its own newest carried point.
    ordered_ends = sorted(endpoints)
    label_positions = []
    for end_y, _, _ in ordered_ends:
        previous_y = label_positions[-1] if label_positions else 13.0
        label_positions.append(max(end_y, previous_y + 22))
    ceiling = float(plot_height + 35)
    for index in range(len(label_positions) - 1, -1, -1):
        label_positions[index] = min(label_positions[index], ceiling)
        ceiling = label_positions[index] - 22
    for (end_y, index, model), label_y in zip(ordered_ends, label_positions):
        label_x = plot_width + 80
        parts.append(f'<path class="leader" d="M{x(index) + 6:.1f},{end_y:.1f} '
                     f'L{label_x - 8},{label_y:.1f}"/>'
                     f'<text class="end-label" x="{label_x}" y="{label_y + 4:.1f}">'
                     f'{escape(model)}</text>')
    parts.append(f'<line class="crosshair" x1="60" x2="60" y1="35" '
                 f'y2="{plot_height + 35}" hidden=""/></svg>')
    return "\n".join(parts)


def table_html(history: list[Snapshot], models: list[str]) -> str:
    parts = ['<div class="table-scroll"><table><caption>Full rank history; '
             '— means absent from that top 10. First-seen is within this window.</caption>'
             '<thead><tr><th scope="col">Model</th><th scope="col">Rank history</th>'
             '<th scope="col">First-seen</th><th scope="col">Latest timestamp</th>'
             '</tr></thead><tbody>']
    for model in models:
        carried = [snapshot for snapshot in history if model in snapshot.ranks]
        cells = [f'<li><time datetime="{escape(snapshot.timestamp)}">'
                 f'{escape(snapshot.timestamp)}</time> · '
                 f'{"Rank " + str(snapshot.ranks[model]) if model in snapshot.ranks else "—"}</li>'
                 for snapshot in history]
        first, latest = (escape(carried[0].timestamp), escape(carried[-1].timestamp))
        parts.append(f'<tr><td>{escape(model)}</td><td><ul>{"".join(cells)}</ul></td>'
                     f'<td><time datetime="{first}">{first}</time></td>'
                     f'<td><time datetime="{latest}">{latest}</time></td></tr>')
    parts.append('</tbody></table></div>')
    return "\n".join(parts)


def section_html(identifier: str, title: str, source: str, history: list[Snapshot]) -> str:
    models = list(dict.fromkeys(model for snapshot in history for model in snapshot.ranks))
    window = (f'{escape(history[0].timestamp)} → {escape(history[-1].timestamp)}'
              if history else 'No tracked snapshots')
    parts = [f'<section id="{identifier}"><h2>{title}</h2><p>Source: {source}. '
             f'{len(history)} changing commits · {window}</p>']
    if len(models) >= 2:
        parts.append('<ul class="legend" aria-label="Model legend">')
        for index, model in enumerate(models):
            dashed = " dashed" if index >= 8 else ""
            parts.append(f'<li><span class="key{dashed}" style="{series_style(index)}" '
                         f'aria-hidden="true"></span>{escape(model)}</li>')
        parts.append('</ul>')
    parts.append('<div class="chart"><div class="chart-scroll">')
    parts.append(chart_svg(history, models, identifier))
    parts.append('</div><div class="tooltip" role="tooltip" hidden></div></div>')
    parts.append('<h3>Table view</h3>')
    parts.append(table_html(history, models))
    parts.append('</section>')
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> None:
    """Write each list from fresh input, a preserved identity, or git history."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path("."))
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("out/trending-rankings.html"))
    parser.add_argument("--fresh-hf", type=pathlib.Path)
    parser.add_argument("--fresh-hf-timestamp")
    parser.add_argument("--fresh-or", type=pathlib.Path)
    parser.add_argument("--fresh-or-timestamp")
    parser.add_argument("--fresh-label")
    parser.add_argument("--identity-page", type=pathlib.Path)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 10:
        parser.error("--limit must be between 1 and 10")
    has_fresh = args.fresh_hf is not None or args.fresh_or is not None
    if has_fresh and args.fresh_label is None:
        parser.error("--fresh-label is required with a fresh file")
    if args.fresh_label is not None and not has_fresh:
        parser.error("--fresh-label requires --fresh-hf or --fresh-or")
    for source in ("hf", "or"):
        fresh = getattr(args, f"fresh_{source}")
        timestamp = getattr(args, f"fresh_{source}_timestamp")
        if fresh is not None and timestamp is None:
            parser.error(f"--fresh-{source}-timestamp is required with --fresh-{source}")
        if timestamp is not None and fresh is None:
            parser.error(f"--fresh-{source}-timestamp requires --fresh-{source}")
    columns = None
    if args.identity_page is not None and (args.fresh_hf is None or args.fresh_or is None):
        try:
            columns = SnapshotColumns(args.identity_page.read_bytes())
        except OSError as exc:
            parser.error(f"identity page is unreadable: {exc}")
    histories = []
    for path, key, section, fresh, timestamp in (
            ("data/hf-trending.json", "id", "hugging-face", args.fresh_hf, args.fresh_hf_timestamp),
            ("data/openrouter-trending.json", "slug", "openrouter",
             args.fresh_or, args.fresh_or_timestamp)):
        if fresh is None and columns is not None:
            try:
                histories.append(identity_history(args.repo, path, key, section,
                                                  args.limit, args.commit, columns))
            except ValueError as exc:
                parser.error(str(exc))
            continue
        history_limit = args.limit - int(fresh is not None)
        history = (read_history(args.repo, path, key, history_limit, args.commit)
                   if history_limit else [])
        if fresh is not None:
            assert args.fresh_label is not None
            capture = json.loads(fresh.read_text(encoding="utf-8"))
            ranks = {model[key]: rank for rank, model in enumerate(capture["models"], 1)}
            history.append(Snapshot(args.fresh_label, timestamp, ranks))
        histories.append(history)
    style = (f".viz-root {{{LIGHT}}}\n"
             f'@media (prefers-color-scheme: dark) {{\n'
             f':root:where(:not([data-theme="light"])) .viz-root {{{DARK}}}\n}}\n'
             f':root[data-theme="dark"] .viz-root {{{DARK}}}\n' + CSS)
    document = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Trending rankings — Hugging Face &amp; OpenRouter top 10 over time</title>'
                f'<style>{style}</style></head><body><div class="viz-root"><main>'
                '<h1>Trending rankings</h1>'
                '<p>Hugging Face trending models and OpenRouter weekly leaders by tokens. '
                'Each chart shows its most recent changing commits, oldest to newest. '
                'Rank 1 is highest; commit positions are equally spaced, not elapsed time. '
                'Gaps mean a model was absent. Dashed lines reuse the eight-color palette. '
                'Hover near a point or focus it with the keyboard for every rank at that commit.</p>'
                '<button id="theme" type="button">Toggle light / dark theme</button>'
                '<nav aria-label="Contents"><a href="#hugging-face">Hugging Face</a>'
                '<a href="#openrouter">OpenRouter</a></nav>'
                + section_html("hugging-face", "Hugging Face · trending top 10", "Hugging Face",
                               histories[0])
                + section_html("openrouter", "OpenRouter · weekly top 10 by tokens", "OpenRouter",
                               histories[1])
                + f'</main></div><script>{JS}</script></body></html>\n')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(document, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
