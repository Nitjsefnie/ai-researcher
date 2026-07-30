#!/usr/bin/env python3
"""Extract the Artificial Analysis model dataset from the public leaderboard page.

artificialanalysis.ai is a Next.js app; the leaderboard's full model array ships
inside the RSC flight payload embedded in the HTML rather than via a public JSON
API. This pulls the page, reassembles the flight chunks, and picks out the rich
model array (the one carrying intelligenceIndex, not the lightweight filter list).

Writes data/aa-raw-models.json -- the single source of truth for this repo.

Usage:  python3 scripts/fetch_aa.py [--html CACHED.html]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.request

URL = "https://artificialanalysis.ai/leaderboards/models"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "aa-raw-models.json"

# The flight payload escapes the model array into JS string chunks.
CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def fetch_html(cached: str | None) -> str:
    if cached:
        return pathlib.Path(cached).read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="use a cached copy of the leaderboard HTML")
    args = ap.parse_args()

    models = richest_models_array(flight_payload(fetch_html(args.html)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(models, indent=1), encoding="utf-8")

    scored = sum(1 for m in models if isinstance(m.get("intelligenceIndex"), (int, float)))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {scored} with an intelligence index")


if __name__ == "__main__":
    main()
