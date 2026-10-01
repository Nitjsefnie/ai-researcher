#!/usr/bin/env python3
"""Refuse a committed page that lacks its stamp or differs from a rebuild.

    python3 scripts/ci/check_committed_page.py

out/frontier-models.html gets its `Source commit <code>...</code>` footer
stamp only when AA_SOURCE_COMMIT is set at build time, and only the refresh
workflow sets it -- so a page a contributor builds and commits by hand goes
out stamp-less, and the hourly heal run then republishes that stamp-less
page byte for byte (issue #105). This check runs in CI on every commit of
the page and refuses one that

  (i)   does not carry exactly one well-shaped source-commit stamp, or
  (ii)  differs from a stamp-less rebuild of HEAD's committed data once
        build provenance (the capture digest and the stamp itself) is
        masked out.

The check's subject is the COMMITTED tree. The rebuild stages data/ from
HEAD (`git show HEAD:data/...`) rather than reading the working tree's,
because the refresh runs this suite after capture but before the commit:
during a refresh the working data/ holds the fresh uncommitted capture, and
building from it judged HEAD's page against data it was never built from,
going red on exactly the runs that had something to commit (issue #108).
In CI the checkout IS the committed tree, so the `page` job judges the same
thing it always has.

Exit 0 when the committed page is well-stamped and byte-equal to its masked
rebuild; 1 with one line per violated invariant otherwise -- a missing page,
a missing, duplicated or malformed stamp, a rebuild that failed, or a
content difference. A build failure is red, never a silent pass: the page
must be rebuildable from what is committed, or the commit is broken.
"""
from __future__ import annotations

import contextlib
import io
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from capture_gate import mask_digest  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import build  # noqa: E402  # pylint: disable=wrong-import-position

PAGE = "out/frontier-models.html"

# The env var build.py reads the stamp value from, and that the rebuild
# below pops so the rebuilt page is stamp-less.
STAMP_ENV = "AA_SOURCE_COMMIT"

# A well-shaped stamp: the exact span build.py renders into the provenance
# line when AA_SOURCE_COMMIT holds a SHA-shaped value. Exactly-once is
# sound: build.py html-escapes the value and escapes `<` to \\u003c in the
# embedded JSON payload, so the marker cannot occur in data -- the same
# argument capture_gate.py's DIGEST_RE comment makes for the digest. The
# stamp VALUE is deliberately not compared to any commit: a page cannot
# contain its own commit's sha (the commit exists only after the page is
# built), the refresh bot's value is correct by construction (github.sha),
# and a hand build's is correct by convention (CONTRIBUTING.md). The shape
# is the invariant; the value is not.
STAMP_RE = re.compile(r" Source commit <code>[0-9a-fA-F]{7,40}</code>\.")

# The marker without the shape requirement: any occurrence of the stamp's
# prose. A page carrying a marker that STAMP_RE does not accept carries a
# malformed stamp, which is its own violation -- distinct from carrying
# none, because the fix differs (rebuild with the env set vs re-read what
# wrote a bad span).
STAMP_MARKER_RE = re.compile(r" Source commit <code>")

# Chars of context shown either side of the first masked difference.
CONTEXT = 80

_CHECK = "committed-page check"


def stamp_mask(page: str) -> str:
    """The page with the source-commit stamp removed.

    Removal, not substitution: only the committed side can carry a stamp --
    the rebuild is forced stamp-less -- so a non-empty constant would stand
    on one masked side alone and vote as a difference. Erasing the span
    normalizes the committed page to exactly the stamp-less rendering the
    rebuild produces, which is the comparison's own definition.
    """
    return STAMP_RE.sub("", page)


def mask(page: str) -> str:
    """The page with every build-provenance span normalized out."""
    return stamp_mask(mask_digest(page))


# The data files the rebuild stages from HEAD, named as build.py and
# capture_gate.py name them: the two captures plus the stamp file beside
# them, which build reads from RAW.parent -- staging all three fully
# determines the build. The count has no drift-sensing control: a fourth
# data/ input in build.py would mix HEAD's staged files with the working
# tree's. The refresh-shape test is the one guard it has -- its staged dir
# holds ONLY these three, so a required input beside the captures fails
# that build loudly; optional or elsewhere-read inputs stay on this
# comment and the reader.
MODELS_NAME = "aa-raw-models.json"
AGENTS_NAME = "aa-raw-coding-agents.json"
STAMP_NAME = "captured-at.txt"


class HeadCaptureError(Exception):
    """No readable data at HEAD -- the rebuild cannot run, so it is red."""


def _git_show(path: str) -> bytes:
    """One file exactly as HEAD committed it.

    Mirrors capture_gate._git_show but fails red: the gate asks a question
    about a world where data may not exist yet and fails open, while a
    check that cannot rebuild has no answer and must not pass.
    """
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=str(build.ROOT), capture_output=True, check=False)
    if proc.returncode != 0:
        raise HeadCaptureError(
            f"git show HEAD:{path} failed: "
            + (proc.stderr or b"").decode("utf-8", "replace").strip())
    return proc.stdout or b""


def rebuild_page() -> str:
    """The page HEAD's committed data/ builds, stamp-less.

    The check's subject is the committed tree (issue #108): the refresh
    runs this suite after capture but before the commit, so during a
    refresh the working data/ holds the fresh uncommitted capture, and a
    rebuild that honored it judged HEAD's page against data it was never
    built from. HEAD's two captures and their captured-at stamp are staged
    into a temp data/ dir -- build reads the stamp from RAW.parent -- and
    build.RAW/AGENTS_RAW/OUT are pointed at the staged copies. Mirrors
    capture_gate._render_side: the temp dir lives under build.ROOT because
    build.main() prints OUT.relative_to(ROOT) and would raise on a page
    outside it. build's module globals and AA_SOURCE_COMMIT are restored no
    matter how the build ends, so a failed rebuild cannot poison the
    caller's tree state. A failed `git show` raises -- red, never a silent
    pass.
    """
    with tempfile.TemporaryDirectory(prefix=".committed-page-",
                                     dir=build.ROOT) as tmp:
        data_dir = pathlib.Path(tmp) / "data"
        data_dir.mkdir()
        for name in (MODELS_NAME, AGENTS_NAME, STAMP_NAME):
            (data_dir / name).write_bytes(_git_show(f"data/{name}"))
        page_path = pathlib.Path(tmp) / "frontier-models.html"
        saved = (build.RAW, build.AGENTS_RAW, build.OUT)
        env_saved = os.environ.pop(STAMP_ENV, None)
        try:
            build.RAW = data_dir / MODELS_NAME
            build.AGENTS_RAW = data_dir / AGENTS_NAME
            build.OUT = page_path
            with contextlib.redirect_stdout(io.StringIO()):
                build.main()
        finally:
            build.RAW, build.AGENTS_RAW, build.OUT = saved
            if env_saved is not None:
                os.environ[STAMP_ENV] = env_saved
        return page_path.read_text(encoding="utf-8")


def _snippet(text: str, at: int) -> str:
    """A bounded window around `at`, newlines escaped so one finding line
    stays one line however the page wraps."""
    lo = max(0, at - CONTEXT)
    hi = min(len(text), at + CONTEXT + 1)
    return text[lo:hi].replace("\n", "\\n")


def verify(committed: str, rebuilt: str) -> list[str]:
    """The invariants a committed page violates against its rebuild.

    Pure: strings in, human-readable violations out -- file IO and exit
    codes live in main(), so tests can pin every failure mode without a
    filesystem.
    """
    markers = STAMP_MARKER_RE.findall(committed)
    if not markers:
        return [f"{_CHECK}: {PAGE} carries no source-commit stamp; build "
                f"with {STAMP_ENV}=\"$(git rev-parse HEAD)\" immediately "
                "before committing"]
    if len(markers) > 1:
        return [f"{_CHECK}: {PAGE} carries {len(markers)} source-commit "
                f"stamps; exactly one is well-formed"]
    if not STAMP_RE.search(committed):
        return [f"{_CHECK}: {PAGE} carries a malformed source-commit stamp "
                f"(expected {STAMP_RE.pattern!r})"]

    left, right = mask(committed), mask(rebuilt)
    if left == right:
        return []
    index = next((i for i, (a, b) in enumerate(zip(left, right)) if a != b),
                 min(len(left), len(right)))
    return [f"{_CHECK}: {PAGE} differs from a stamp-less rebuild of the "
            f"same tree once provenance is masked: masked lengths "
            f"{len(left)} vs {len(right)}, first difference at index "
            f"{index}: committed[...] {_snippet(left, index)} | "
            f"rebuilt[...] {_snippet(right, index)}"]


def main(page_path: pathlib.Path | None = None) -> int:
    path = page_path if page_path is not None else build.ROOT / PAGE
    try:
        committed = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"{_CHECK}: {PAGE} is missing or unreadable: {exc}",
              file=sys.stderr)
        return 1

    try:
        rebuilt = rebuild_page()
    except (SystemExit, Exception) as exc:  # pylint: disable=broad-exception-caught
        print(f"{_CHECK}: rebuilding {PAGE} from the committed data failed "
              f"({exc}) -- red, never a silent pass", file=sys.stderr)
        return 1

    violations = verify(committed, rebuilt)
    if violations:
        for line in violations:
            print(line, file=sys.stderr)
        return 1
    # Defensive: verify() passing means the page carries exactly one
    # well-shaped stamp, so search() cannot return None here. The branch
    # exists to keep the Optional honest -- and to fail loudly rather than
    # trust that invariant, should the two ever drift apart.
    match = STAMP_RE.search(committed)
    if match is None:
        print(f"{_CHECK}: {PAGE} passed verify() but carries no source-"
              "commit stamp -- the verifier and the stamp pattern disagree",
              file=sys.stderr)
        return 1
    print(f"{_CHECK}: {PAGE} carries one source-commit stamp "
          f"({match.group(0).strip()}) and matches its stamp-less rebuild "
          "-- ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
