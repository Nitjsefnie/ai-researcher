#!/usr/bin/env python3
"""Would the fresh capture build a page that differs from HEAD capture's page?

One question, one answer on stdout: `true` when the page built from the two
capture files in data/ would differ from the page HEAD's two capture files
build, `false` when it would not. The hourly refresh's no-change gate runs
this instead of comparing raw capture bytes: AA's payload churns hourly in
fields the page never renders, long after every rendered number is stable,
and raw-byte comparison committed that churn hour after hour (issue #94).

Both sides are built with build.py itself, so "the page" is the page: a
changed render function IS a real page change, and a field the builder never
reads is invisible to the gate -- which is the point.

One refinement keeps the gate agreeing with the differ's own definition of
news: the rendered speed fields are compared with diff_aa.py's own
--speed-tol test -- a re-sample within SPEED_TOL of the last COMMITTED
value is jitter and is reconciled to it (see reconcile_speed). A
sub-threshold re-sample of output tokens/sec or time per task compares
equal, so a quiet month of speed jitter commits nothing. The cost, stated
plainly: the page's speed columns can lag AA's live re-sampling by just
under the threshold -- and they cannot lag further, because each hour
compares against the last committed value, so a sustained crawl crosses
the threshold cumulatively and commits.

Exit codes:
  0   an answer was reached: stdout carries `true` (moved) or `false`.
  1   broken, not unchanged: a fresh capture file is missing, or the build
      failed. The refresh run turns red -- a broken capture is the designed
      signal to re-read the leaderboard, never a quiet "nothing moved".
No capture at HEAD (the first capture ever) is NOT broken: it fails OPEN,
printing `true`, so the first run publishes instead of skipping forever.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import traceback
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from diff_aa import SPEED_TOL  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import build  # noqa: E402  # pylint: disable=wrong-import-position

MODELS_NAME = "aa-raw-models.json"
AGENTS_NAME = "aa-raw-coding-agents.json"
STAMP_NAME = "captured-at.txt"

# Both gate builds run stamp-less: an unset AA_SOURCE_COMMIT renders nothing
# extra (build.py renders only a SHA-shaped value), so the source-commit
# stamp -- build-machine provenance -- can never vote in the comparison.
STAMP_ENV = "AA_SOURCE_COMMIT"

# The page's provenance line embeds a sha256 over the two raw capture files.
# The digest moves with every raw-byte difference, sub-render churn included,
# so it is provenance too and must not vote: it is masked out of both pages
# before comparing, anchored on the provenance line's own prose. Nothing else
# can match: build.py escapes `<` to \\u003c in the embedded JSON payload, so
# the marker cannot occur there.
DIGEST_RE = re.compile(r"(Capture <code>)[0-9a-f]{64}(</code>)")

# Written into BOTH temp data dirs. The capture date is metadata -- AGENTS.md:
# the stamp file moves when the DATA moves -- so a date-only difference must
# not vote; building both sides from the same synthetic date removes it from
# the comparison entirely.
SYNTHETIC_STAMP = "2000-01-01\n"

# What the digest is masked TO, on both sides, before the comparison.
MASKED_DIGEST = "0" * 64


def mask_page(page: str) -> str:
    """The provenance mask: the capture digest."""
    return mask_digest(page)


class HeadCaptureError(Exception):
    """No readable capture at HEAD -- e.g. the first capture ever."""


class FreshCaptureError(Exception):
    """A fresh capture file is missing or unreadable."""


# --- speed quantization ------------------------------------------------------


# The rendered speed fields the gate reconciles, and where each is rendered.
# Two of them are diff_aa.py's own SPEED_SHOWN fields -- build.py:356-357
# carries the models capture's medianOutputTokensPerSecond ("tps") and
# intelligenceIndexTimePerTask ("secs") onto model rows, and the differ
# thresholds those re-samples as news-only-past-SPEED_TOL. agentWallTimeSec
# (build.py:443-444, the coding capture's "secs") is NOT in SPEED_SHOWN: the
# differ's report never carries it (its classifier files it as derived and
# drops it). The gate reconciles it anyway, under the same threshold,
# because the page renders it -- an intentional gate-side strictness, not
# tool agreement.
SPEED_KEYS_MODELS = frozenset(
    {"medianOutputTokensPerSecond", "intelligenceIndexTimePerTask"})
SPEED_KEYS_AGENTS = frozenset({"agentWallTimeSec"})


def _is_number(value) -> bool:
    """A JSON number -- bools are Python ints and are not numbers here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def within_tolerance(value, head_value):
    """HEAD's value when this re-sample is sub-threshold relative to it.

    This is diff_aa.py's --speed-tol test applied to one rendered cell:
    |fresh/committed - 1| <= SPEED_TOL means the re-sample is jitter, and
    the cell is made to compare equal by carrying HEAD's committed value.
    Anything else -- a move past the threshold, a zeroed or vanished
    committed value, a non-number on either side -- is left verbatim.
    """
    if not (_is_number(value) and _is_number(head_value)) or head_value == 0:
        return value
    if abs(value / head_value - 1) <= SPEED_TOL:
        return head_value
    return value


def reconcile_tree(head, fresh, keys) -> Any:
    """The fresh tree with sub-threshold speed cells overwritten by HEAD's.

    Walks both trees jointly, position by position. A speed key present
    numerically on BOTH sides is reconciled (within_tolerance); anything
    else -- a key missing or re-typed on either side, a fresh-only subtree,
    a fresh-only list tail -- is left verbatim, so a structural change
    commits by simply falling out of the overwrite.
    """
    if isinstance(fresh, dict) and isinstance(head, dict):
        reconciled = {}
        for key, value in fresh.items():
            if key not in head:
                reconciled[key] = value
            elif key in keys:
                reconciled[key] = within_tolerance(value, head[key])
            else:
                reconciled[key] = reconcile_tree(head[key], value, keys)
        return reconciled
    if isinstance(fresh, list) and isinstance(head, list):
        return ([reconcile_tree(h, v, keys) for h, v in zip(head, fresh)]
                + fresh[len(head):])
    return fresh


def reconcile_speed(head: tuple[bytes, bytes],
                    fresh: tuple[bytes, bytes]) -> tuple[bytes, bytes]:
    """The fresh captures with sub-threshold speed re-samples reconciled.

    Runs on the gate's TEMP COPIES ONLY -- data/ keeps the verbatim capture,
    and nothing reconciled is ever written back or committed. HEAD's temp
    copies stay verbatim (the synthetic captured-at stamp aside), so the two
    pages can only differ on non-speed fields, on speed cells beyond
    SPEED_TOL relative to the last committed value, or on structure.

    Drift accumulates by construction: each hour compares against the last
    COMMITTED value, so a sustained crawl crosses the threshold cumulatively
    and commits rather than hiding inside successive sub-threshold steps.
    """
    models = reconcile_tree(json.loads(head[0]), json.loads(fresh[0]),
                            SPEED_KEYS_MODELS)
    agents = reconcile_tree(json.loads(head[1]), json.loads(fresh[1]),
                            SPEED_KEYS_AGENTS)
    return (json.dumps(models, indent=1).encode("utf-8"),
            json.dumps(agents, indent=1).encode("utf-8"))


# --- reads -------------------------------------------------------------------


def read_head_captures() -> tuple[bytes, bytes]:
    """The two capture files exactly as HEAD committed them.

    Factored for tests: monkeypatch this one function and everything
    downstream is hermetic on the bytes it returns. A failing `git show`
    (capture absent at HEAD, not a git repo) raises HeadCaptureError, which
    main() turns into the fail-open `true`.
    """
    return _git_show(f"data/{MODELS_NAME}"), _git_show(f"data/{AGENTS_NAME}")


def _git_show(path: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=str(ROOT), capture_output=True, check=False)
    if proc.returncode != 0:
        raise HeadCaptureError(
            f"git show HEAD:{path} failed: "
            + (proc.stderr or b"").decode("utf-8", "replace").strip())
    return proc.stdout or b""


def read_fresh_captures() -> tuple[bytes, bytes]:
    """The two capture files as fetch_aa.py just wrote them.

    A missing fresh capture is broken, not unchanged -- the caller fails red.
    """
    data = ROOT / "data"
    try:
        return ((data / MODELS_NAME).read_bytes(),
                (data / AGENTS_NAME).read_bytes())
    except OSError as exc:
        raise FreshCaptureError(
            f"{data / MODELS_NAME} / {data / AGENTS_NAME}: {exc}") from exc


# --- build both sides --------------------------------------------------------


def _stage(side_dir: pathlib.Path, captures: tuple[bytes, bytes]) -> None:
    """One side's temp data dir: the two captures plus the synthetic stamp.

    The real stamps (tree and HEAD) are never read: the date is build-machine
    metadata, and building both sides from the same synthetic date is what
    keeps a date-only difference from voting.
    """
    side_dir.mkdir(parents=True)
    (side_dir / MODELS_NAME).write_bytes(captures[0])
    (side_dir / AGENTS_NAME).write_bytes(captures[1])
    (side_dir / STAMP_NAME).write_text(SYNTHETIC_STAMP, encoding="utf-8")


def _render_side(side_dir: pathlib.Path,
                 captures: tuple[bytes, bytes]) -> str:
    """Stage one side and build its page; return the page HTML.

    The temp dir lives under build.ROOT because build.main() prints
    OUT.relative_to(ROOT) and would raise on a page outside it. build's
    module globals and AA_SOURCE_COMMIT are restored no matter how the build
    ends, so a failed gate build cannot poison the caller's tree state.
    """
    _stage(side_dir, captures)
    page_path = side_dir / "frontier-models.html"
    saved = (build.RAW, build.AGENTS_RAW, build.OUT)
    env_saved = os.environ.pop(STAMP_ENV, None)
    try:
        build.RAW = side_dir / MODELS_NAME
        build.AGENTS_RAW = side_dir / AGENTS_NAME
        build.OUT = page_path
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()
    finally:
        build.RAW, build.AGENTS_RAW, build.OUT = saved
        if env_saved is not None:
            os.environ[STAMP_ENV] = env_saved
    return page_path.read_text(encoding="utf-8")


def build_page_pair(head: tuple[bytes, bytes],
                    fresh: tuple[bytes, bytes]) -> tuple[str, str]:
    """Build the page from HEAD's captures and from the fresh ones.

    The fresh side is reconciled against HEAD's first (reconcile_speed):
    sub-threshold speed drift compares equal, a move past SPEED_TOL relative
    to the last committed value (or a structural change) stays and differs.

    Returns the two pages UNMASKED, in that order; the caller applies the
    digest mask before comparing. Raises whatever the build raises (SystemExit
    for a capture build.py refuses) -- a build failure is red, not "changed".
    """
    fresh = reconcile_speed(head, fresh)
    with tempfile.TemporaryDirectory(prefix=".capture-gate-",
                                     dir=build.ROOT) as tmp:
        tmp_root = pathlib.Path(tmp)
        old_page = _render_side(tmp_root / "old", head)
        new_page = _render_side(tmp_root / "new", fresh)
    return old_page, new_page


def mask_digest(page: str) -> str:
    """The page with the capture digest replaced by a constant."""
    return DIGEST_RE.sub(
        lambda m: m.group(1) + MASKED_DIGEST + m.group(2), page)


# --- the gate ----------------------------------------------------------------


def main() -> int:
    try:
        head = read_head_captures()
    except HeadCaptureError as exc:
        print(f"capture-gate: no readable capture at HEAD ({exc}) -- failing "
              "open: the capture counts as moved", file=sys.stderr)
        print("true")
        return 0

    try:
        fresh = read_fresh_captures()
    except FreshCaptureError as exc:
        print(f"capture-gate: {exc} -- broken, not unchanged; re-capture with "
              "scripts/fetch_aa.py", file=sys.stderr)
        return 1

    try:
        old_page, new_page = build_page_pair(head, fresh)
    except (SystemExit, Exception) as exc:  # pylint: disable=broad-exception-caught
        # build.py's own refusals (SystemExit) already carry their named
        # reason. An unexpected crash gets the traceback appended, so the
        # next occurrence names its site and field from the log alone --
        # the 2026-10-03T01:09Z hour printed only "float division by zero"
        # and named neither (issue #146).
        detail = str(exc)
        if not isinstance(exc, SystemExit):
            detail += "\n" + traceback.format_exc()
        print(f"capture-gate: the capture broke the build ({detail}) -- failing "
              "red rather than report the capture as unchanged", file=sys.stderr)
        return 1

    moved = mask_page(old_page) != mask_page(new_page)
    print("true" if moved else "false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
