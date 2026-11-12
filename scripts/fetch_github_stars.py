#!/usr/bin/env python3
"""Fetch GitHub's 10 most-starred repositories into data/github-stars.json.

    fetch_github_stars.py [--message FILE]

Reads the token from AI_RESEARCHER_GITHUB_TOKEN and prints the commit message.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib

import fetch_http
import trending_message

ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = ("https://api.github.com/search/repositories"
       "?q=stars:>1000&sort=stars&order=desc&per_page=30")
DATA = ROOT / "data" / "github-stars.json"


def fetch() -> list[dict[str, str]]:
    """Return the top ten in star order."""
    token = os.environ.get("AI_RESEARCHER_GITHUB_TOKEN")
    if not token:
        raise SystemExit("AI_RESEARCHER_GITHUB_TOKEN is not set; the search API "
                         "call needs the workflow's token -- nothing was captured")
    body = fetch_http.fetch_bytes(
        URL, {"User-Agent": "ai-researcher-github-stars",
              "Accept": "application/vnd.github+json",
              "Authorization": f"Bearer {token}"}, 30)
    try:
        result = json.loads(body)
        # A timed-out search returns partial matches.
        if result["incomplete_results"] is not False:
            raise ValueError("incomplete_results is not false")
        names = [item["full_name"] for item in result["items"][:10]]
        if not all(isinstance(name, str) and name for name in names):
            raise ValueError("a full_name is not a non-empty string")
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"{URL}: unexpected response: {exc!r} -- nothing "
                         "was captured") from exc
    return [{"full_name": name} for name in names]


def message(old: list[dict[str, str]], new: list[dict[str, str]]) -> str:
    """Describe what moved."""
    return trending_message.message(old, new, "full_name", "chore(github-stars):", "new in the top 10")


def main(argv: list[str] | None = None) -> None:
    """Refresh the data file and print its commit message."""
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
        raise SystemExit(f"expected 10 repositories, got {len(new)}")
    commit_message = message(old, new)
    with DATA.open("w", encoding="utf-8", newline="\n") as capture:
        json.dump({"source": URL, "models": new}, capture, indent=2)
        capture.write("\n")
    if args.message:
        pathlib.Path(args.message).write_text(commit_message, encoding="utf-8", newline="\n")
    print(commit_message, end="")


if __name__ == "__main__":
    main()
