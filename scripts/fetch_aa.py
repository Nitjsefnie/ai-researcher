#!/usr/bin/env python3
"""Extract the Artificial Analysis model dataset from the public leaderboard page.

artificialanalysis.ai is a Next.js app; the leaderboard's full model array ships
inside the RSC flight payload embedded in the HTML rather than via a public JSON
API. This pulls the page, reassembles the flight chunks, and picks out the rich
model array (the one carrying intelligenceIndex, not the lightweight filter list).

Writes two captures, both from artificialanalysis.ai and nothing else:

  data/aa-raw-models.json         the model leaderboard -- intelligence index,
                                  its measured cost breakdown, GDPval-AA, price,
                                  parameters, context, licence
  data/aa-raw-coding-agents.json  the Coding Agent Index -- agent+model rows
                                  carrying indexScore and mean.costUsd on the
                                  SAME record, so no reweighting is needed

alongside data/captured-at.txt, the date the capture was taken.

Usage:  python3 scripts/fetch_aa.py [--html CACHED.html] [--agents-html CACHED.html]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request

URL = "https://artificialanalysis.ai/leaderboards/models"
# The Coding Agent Index. This is a DIFFERENT AA product from the leaderboard's
# `codingIndex` field: it scores agent+model+harness combinations (Claude Code -
# Opus 5 (xhigh), Codex - GPT-6 Astra (max)) rather than bare models, and it is
# the index AA means when the methodology page says Terminal-Bench v2.1 "remains
# part of the Coding Index". It is the only /agents/* route carrying a benchmark;
# the other six are marketing comparison pages with no index and no cost.
AGENTS_URL = "https://artificialanalysis.ai/agents/coding-agents"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "aa-raw-models.json"
AGENTS_OUT = ROOT / "data" / "aa-raw-coding-agents.json"
# When the capture happened. build.py stamps this on the page, so it cannot be
# derived at build time: rebuilding an old capture tomorrow would relabel it with
# tomorrow's date, and the page's copy-as-JSON export would carry the lie too.
STAMP = ROOT / "data" / "captured-at.txt"

# The flight payload escapes the model array into JS string chunks.
CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def fetch_html(cached: str | None, url: str = URL) -> str:
    if cached:
        return pathlib.Path(cached).read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="replace")


def flight_payload(html: str) -> str:
    chunks = CHUNK_RE.findall(html)
    if not chunks:
        sys.exit("no flight chunks found -- page structure changed")
    return "".join(json.loads(c) for c in chunks)


def balanced_array(text: str, start: int) -> str | None:
    """Return the JSON array literal beginning at text[start] == '['."""
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        c = text[j]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def richest_models_array(payload: str) -> list[dict]:
    """Several "models":[...] arrays exist; take the one with the most fields."""
    best: list[dict] = []
    best_keys = 0
    for m in re.finditer(r'"models":\[', payload):
        raw = balanced_array(payload, m.end() - 1)
        if not raw:
            continue
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        keys = max((len(x) for x in arr if isinstance(x, dict)), default=0)
        if keys > best_keys:
            best, best_keys = arr, keys
    if best_keys < 20:
        sys.exit(f"richest models array had only {best_keys} fields -- schema changed")
    return best


def coding_agent_rows(payload: str) -> list[dict]:
    """The Coding Agent Index table, server-rendered inside the flight payload.

    The page embeds it twice -- once as the ten highlighted rows behind the
    summary charts, once in full -- so this takes the largest array whose
    entries carry an `indexScore`. Entries interleave with RSC marker strings,
    hence the isinstance filter.
    """
    best: list[dict] = []
    for m in re.finditer(r'\[\{"id":"', payload):
        raw = balanced_array(payload, m.start())
        if not raw:
            continue
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        scored = [r for r in arr if isinstance(r, dict) and "indexScore" in r]
        if len(scored) > len(best):
            best = scored
    priced = [
        r for r in best
        if isinstance(r.get("indexScore"), (int, float))
        and isinstance(r.get("mean"), dict)
        and isinstance(r["mean"].get("costUsd"), (int, float))
    ]
    # AA has shipped 58 rows here; a collapse to a handful means the page moved
    # its data client-side or renamed the pair, which is a hand-read signal and
    # not something to publish a half-empty chart from.
    if len(priced) < 20:
        sys.exit(
            f"coding agent index: only {len(priced)} rows carry indexScore and "
            f"mean.costUsd -- schema changed"
        )
    return priced


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="use a cached copy of the leaderboard HTML")
    ap.add_argument("--agents-html", help="use a cached copy of the coding-agents HTML")
    args = ap.parse_args()

    models = richest_models_array(flight_payload(fetch_html(args.html)))
    agents = coding_agent_rows(
        flight_payload(fetch_html(args.agents_html, AGENTS_URL))
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(models, indent=1), encoding="utf-8")
    AGENTS_OUT.write_text(json.dumps(agents, indent=1), encoding="utf-8")
    STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    scored = sum(1 for m in models if isinstance(m.get("intelligenceIndex"), (int, float)))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {scored} with an intelligence index")
    print(f"wrote {AGENTS_OUT.relative_to(ROOT)}: {len(agents)} agent+model rows "
          f"with a paired index score and cost per task")


if __name__ == "__main__":
    main()
