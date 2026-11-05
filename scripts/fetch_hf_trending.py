#!/usr/bin/env python3
"""Fetch Hugging Face's top 10 trending model ids into data/hf-trending.json.

    fetch_hf_trending.py [--message FILE]

Rewrites the tracked list in Hugging Face's trending order and writes a commit
message describing what moved since the previous file: models that entered the
top 10, models that left it, and rank changes. Prints the message too.

Persisted JSON and --message output use LF on every platform, rather than
upstream update.py's native text-mode newlines.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import fetch_http
import trending_message

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "https://huggingface.co/api/models?sort=trendingScore&limit=10"
DATA = ROOT / "data" / "hf-trending.json"


def fetch() -> list[dict[str, str]]:
    """Fetch the top ten model ids in Hugging Face's trending order."""
    body = fetch_http.fetch_bytes(URL, {"User-Agent": "hf-trending"}, 30)
    models = json.loads(body)
    return [{"id": model["id"]} for model in models[:10]]


def message(old: list[dict[str, str]], new: list[dict[str, str]]) -> str:
    """Describe entries, departures and rank changes in upstream spelling."""
    return trending_message.message(old, new, "id", "Trending:", "new in the top 10")


def main(argv: list[str] | None = None) -> None:
    """Refresh the tracked data file and print its commit message."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--message", help="write the commit message to this file")
    args = parser.parse_args(argv)
    try:
        with DATA.open(encoding="utf-8") as capture:
            old = json.load(capture)["models"]
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
