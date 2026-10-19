#!/usr/bin/env python3
"""Refuse deficient tracker histories, a missing page or a differing rebuild.

    python3 scripts/ci/check_committed_rankings_page.py

The rankings page is rebuilt from HEAD on ordinary commits. A pull-request
checkout is a merge ref whose second parent is the tested branch tip: merge
commits rebuild from HEAD^2 so newer main tracker commits cannot change the
snapshot window the branch's page was built from. The rebuild goes into a
temp directory and is compared byte-for-byte with out/trending-rankings.html.
This refuses a stale committed page when the builder or captured history
changes. No provenance is masked: every byte participates in the check.
Each tracker must have at least one committed snapshot in the selected
history; identical bytes cannot make an empty tracker history valid.

Exit 0 when both histories are non-empty and the page is present and
identical; 1 with one line per violated invariant otherwise -- an empty
history for either tracker, a missing or unreadable committed page, a
failed rebuild, missing or unreadable rebuild output, or a content difference.
A build failure is red, never a silent pass.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_rankings  # noqa: E402  # pylint: disable=wrong-import-position

PAGE = "out/trending-rankings.html"
CONTEXT = 80
_CHECK = "committed-rankings-page check"


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
        output = pathlib.Path(tmp) / "trending-rankings.html"
        try:
            head = build_rankings.git(checkout, "rev-list", "--parents", "-n", "1", "HEAD").split()
            history_commit = "HEAD^2" if len(head) > 2 else "HEAD"
            for path in ("data/hf-trending.json", "data/openrouter-trending.json"):
                history = build_rankings.git(checkout, "log", "-n", "1", "--format=%H",
                                             history_commit, "--", path)
                if not history.strip():
                    violations.append(f"{_CHECK}: {path} history is empty")
            build_rankings.main(["--repo", str(checkout), "--commit", history_commit,
                                 "--out", str(output)])
        except (SystemExit, Exception) as exc:  # pylint: disable=broad-exception-caught
            violations.append(f"{_CHECK}: {PAGE} rebuild failed "
                              f"({' '.join(str(exc).splitlines())}) "
                              "-- red, never a silent pass")
        else:
            try:
                rebuilt = output.read_bytes()
            except OSError as exc:
                violations.append(f"{_CHECK}: {PAGE} rebuild output is missing or "
                                  f"unreadable: {' '.join(str(exc).splitlines())}")

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
