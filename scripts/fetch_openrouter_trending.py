#!/usr/bin/env python3
"""Fetch OpenRouter's top 10 models by weekly tokens into data/openrouter-trending.json.

    fetch_openrouter_trending.py [--message FILE]

Rewrites the tracked list in OpenRouter's weekly token order and writes a commit
message describing what moved since the previous file: models that entered the
top 10, models that left it, and rank changes. Prints the message too.

Ported from Nitjsefnie/openrouter-top update.py. Persisted JSON and
--message output use UTF-8 and LF on every platform.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "https://openrouter.ai/api/frontend/v1/models/find?order=top-weekly"
DATA = ROOT / "data" / "openrouter-trending.json"


def fetch() -> list[dict[str, str]]:
    """Fetch the top ten model slugs in OpenRouter's weekly token order."""
    req = urllib.request.Request(
        URL, headers={"User-Agent": "Mozilla/5.0 (openrouter-top)",
                      "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        models = json.load(resp)["data"]["models"]
    return [{"slug": model["slug"]} for model in models[:10]]


def message(old: list[dict[str, str]], new: list[dict[str, str]]) -> str:
    """Describe entries, departures and rank changes with explicit rank labels."""
    before = {model["slug"]: rank for rank, model in enumerate(old, 1)}
    after = {model["slug"]: rank for rank, model in enumerate(new, 1)}
    entered = [model for model in new if model["slug"] not in before]
    left = [model for model in old if model["slug"] not in after]
    moved = [model for model in new
             if model["slug"] in before
             and before[model["slug"]] != after[model["slug"]]]
    if entered:
        subject = (f"Top 10: {len(entered)} new: "
                   + ", ".join(model["slug"] for model in entered))
    elif moved:
        subject = f"Top 10: {len(moved)} rank change(s)"
    else:
        subject = "Top 10: order updated"
    # Ranks never carry "#": GitHub links "#N" in a commit message to issue N.
    body = [f"NEW  rank {after[model['slug']]} {model['slug']}" for model in entered]
    body += [f"OUT  {model['slug']} (was rank {before[model['slug']]})" for model in left]
    body += [f"MOVE {model['slug']} rank {before[model['slug']]} -> "
             f"{after[model['slug']]}" for model in moved]
    return subject + ("\n\n" + "\n".join(body) if body else "") + "\n"


def main(argv: list[str] | None = None) -> None:
    """Refresh the tracked data file and print its commit message."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--message", help="write the commit message to this file")
    args = parser.parse_args(argv)
    try:
        old = json.loads(DATA.read_text(encoding="utf-8"))["models"]
    except FileNotFoundError:
        old = []
    new = fetch()
    if len(new) != 10:
        raise SystemExit(f"expected 10 models, got {len(new)}")
    commit_message = message(old, new)
    with DATA.open("w", encoding="utf-8", newline="\n") as capture:
        json.dump({"source": URL, "models": new}, capture, indent=2)
        capture.write("\n")
    if args.message:
        pathlib.Path(args.message).write_text(commit_message, encoding="utf-8", newline="\n")
    print(commit_message, end="")


if __name__ == "__main__":
    main()
