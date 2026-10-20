#!/usr/bin/env python3
"""Refuse deficient histories, stale newest ranks or a differing page rebuild.

    python3 scripts/ci/check_committed_rankings_page.py

The page supplies each list's newest SVG column label and timestamp; landed
JSON supplies its ranks, checked independently against that column. Earlier
columns come from the preceding path-changing commit. This reconstructs both
run-labelled and SHA-labelled pages, with independent windows for each list.
A pull-request merge checkout selects HEAD^2 so newer main tracker commits
cannot change the branch's snapshot window. Every byte participates in the
comparison; each tracker must also have at least one committed snapshot.

Exit 0 when both histories are non-empty and the page is present and
identical; 1 with one line per violated invariant otherwise -- an empty
history for either tracker, a missing or unreadable committed page, a
failed rebuild, missing or unreadable rebuild output, or a content difference.
A build failure is red, never a silent pass.
"""
from __future__ import annotations

import pathlib
import json
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_rankings  # noqa: E402  # pylint: disable=wrong-import-position

PAGE = "out/trending-rankings.html"
CONTEXT = 80
_CHECK = "committed-rankings-page check"
LIMIT = 10
TRACKERS = (("data/hf-trending.json", "id", "hugging-face", "hf"),
            ("data/openrouter-trending.json", "slug", "openrouter", "or"))


def _section(document: bytes, identifier: str) -> bytes:
    """Extract one complete section from the builder's generated document."""
    match = re.search(rb'<section id="' + identifier.encode("ascii") + rb'">.*?</section>',
                      document, re.DOTALL)
    if match is None:
        raise ValueError(f"rebuilt section {identifier} is missing")
    return match.group()


def _read_output(output: pathlib.Path, violations: list[str]) -> bytes | None:
    try:
        return output.read_bytes()
    except OSError as exc:
        violations.append(f"{_CHECK}: {PAGE} rebuild output is missing or "
                          f"unreadable: {' '.join(str(exc).splitlines())}")
        return None


def _rebuild(checkout: pathlib.Path, ref: str, committed: bytes | None,
             directory: pathlib.Path, violations: list[str]) -> bytes | None:
    """Rebuild each list at its own anchor, then join the generated sections."""
    columns = build_rankings.SnapshotColumns(committed or b"")
    requests = []
    for path, key, section, flag in TRACKERS:
        history = build_rankings.git(checkout, "log", "-n", str(LIMIT + 1), "--format=%H",
                                     ref, "--", path).splitlines()
        if not history:
            violations.append(f"{_CHECK}: {path} history is empty")
            continue
        column = columns.newest(section)
        if column is None:
            if committed is not None:
                violations.append(f"{_CHECK}: {path} newest column is missing or unparseable")
            continue
        capture = build_rankings.git(checkout, "show", f"{ref}:{path}")
        ranks = {model[key]: rank for rank, model in enumerate(json.loads(capture)["models"], 1)}
        if ranks != column.ranks:
            violations.append(f"{_CHECK}: {path} newest column ranks differ from landed JSON")
        fresh = directory / f"{flag}.json"
        fresh.write_text(capture, encoding="utf-8")
        # The builder reserves one column for fresh data. A lone root snapshot
        # has no preceding history, so use a one-column window at that commit.
        anchor = history[1] if len(history) > 1 else history[0]
        requests.append((section, ["--commit", anchor, "--limit",
                                  str(LIMIT if len(history) > 1 else 1),
                                  f"--fresh-{flag}", str(fresh),
                                  f"--fresh-{flag}-timestamp", column.timestamp,
                                  "--fresh-label", column.commit]))
    output = directory / "trending-rankings.html"
    common = ["--repo", str(checkout)]
    if len(requests) != len(TRACKERS):
        build_rankings.main([*common, "--out", str(output), "--commit", ref])
        return _read_output(output, violations)
    rebuilt = None
    for section, arguments in requests:
        output = directory / f"{section}.html"
        build_rankings.main([*common, "--out", str(output), *arguments])
        document = _read_output(output, violations)
        if document is None:
            return None
        rebuilt = (document if rebuilt is None else
                   rebuilt.replace(_section(rebuilt, section), _section(document, section), 1))
    return rebuilt


def _snippet(content: bytes, at: int) -> str:
    """A bounded byte window, escaped to keep each finding on one line."""
    return repr(content[max(0, at - CONTEXT):at + CONTEXT + 1])


def verify(committed: bytes, rebuilt: bytes) -> list[str]:
    """Report the first differing byte with short context on both sides."""
    if committed == rebuilt:
        return []
    index = next((i for i, (a, b) in enumerate(zip(committed, rebuilt)) if a != b),
                 min(len(committed), len(rebuilt)))
    return [f"{_CHECK}: {PAGE} differs from a rebuild of the selected history: "
            f"lengths {len(committed)} B vs {len(rebuilt)} B, "
            f"first difference at index {index}: "
            f"committed[...] {_snippet(committed, index)} | "
            f"rebuilt[...] {_snippet(rebuilt, index)}"]


def main(repo: pathlib.Path | None = None) -> int:
    checkout = repo if repo is not None else ROOT
    violations = []
    committed = rebuilt = None
    try:
        committed = (checkout / PAGE).read_bytes()
    except OSError as exc:
        violations.append(f"{_CHECK}: {PAGE} committed page is missing or "
                          f"unreadable: {' '.join(str(exc).splitlines())}")

    with tempfile.TemporaryDirectory(prefix=".committed-rankings-page-") as tmp:
        try:
            head = build_rankings.git(checkout, "rev-list", "--parents", "-n", "1", "HEAD").split()
            history_commit = "HEAD^2" if len(head) > 2 else "HEAD"
            rebuilt = _rebuild(checkout, history_commit, committed, pathlib.Path(tmp), violations)
        except (SystemExit, Exception) as exc:  # pylint: disable=broad-exception-caught
            violations.append(f"{_CHECK}: {PAGE} rebuild failed "
                              f"({' '.join(str(exc).splitlines())}) "
                              "-- red, never a silent pass")

    if committed is not None and rebuilt is not None:
        violations.extend(verify(committed, rebuilt))
    if violations:
        for line in violations:
            print(line, file=sys.stderr)
        return 1
    print(f"{_CHECK}: {PAGE} matches its rebuild -- ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
