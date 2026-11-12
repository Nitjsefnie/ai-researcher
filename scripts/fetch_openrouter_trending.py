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

import fetch_http
import trending_message

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "https://openrouter.ai/api/frontend/v1/models/find?order=top-weekly"
DATA = ROOT / "data" / "openrouter-trending.json"


def fetch() -> list[dict[str, str]]:
    """Fetch the top ten model slugs in OpenRouter's weekly token order."""
    body = fetch_http.fetch_bytes(
        URL, {"User-Agent": "Mozilla/5.0 (openrouter-top)",
              "Cache-Control": "no-cache"}, 60)
    models = json.loads(body)["data"]["models"]
    return [{"slug": model["slug"]} for model in models[:10]]


def message(old: list[dict[str, str]], new: list[dict[str, str]]) -> str:
    """Describe entries, departures and rank changes with explicit rank labels."""
    return trending_message.message(old, new, "slug", "chore(openrouter):", "new")


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
