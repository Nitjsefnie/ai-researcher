#!/usr/bin/env python3
"""Extract the Artificial Analysis model dataset from the public leaderboard page.

artificialanalysis.ai is a Next.js app; the leaderboard's full model array ships
inside the RSC flight payload embedded in the HTML rather than via a public JSON
API. This pulls the page, reassembles the flight chunks, and picks out the rich
model array (the one carrying intelligenceIndex, not the lightweight filter list).

Writes two captures, both from artificialanalysis.ai and nothing else:

  data/aa-raw-models.json         the model leaderboard STITCHED WITH a model
                                  detail page -- AA trimmed the leaderboard
                                  payload and the two now carry different
                                  halves of one record, from one snapshot
  data/aa-raw-coding-agents.json  the Coding Agent Index -- agent+model rows
                                  carrying indexScore and mean.costUsd on the
                                  SAME record, so no reweighting is needed

alongside data/captured-at.txt, the date the capture was taken.

Usage:  python3 scripts/fetch_aa.py [--html F] [--detail-html F] [--agents-html F]
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.message
import email.utils
import json
import os
import pathlib
import re
import sys
import time
import typing
import urllib.error
import urllib.request

ROOT_FOR_IMPORT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_FOR_IMPORT))

from build import (  # noqa: E402  # pylint: disable=wrong-import-position
    DISPUTED_SNAPSHOT_NAME, GDPVAL_SLUG, INDEX_VERSION,
    RouteDisagreement, check_route_agreement, merge_captures,
)

URL = "https://artificialanalysis.ai/leaderboards/models"
# The leaderboard's payload was trimmed to 50 fields: it kept identity, price,
# speed and context but LOST name, licenceName, releaseDate, the parameter
# count and the per-evaluation cost breakdown. All of those still ship, on any
# model detail page, which embeds the whole corpus for its comparison widgets.
# The two routes render from one snapshot -- every shared intelligenceIndex and
# cost.total agrees exactly -- so merging them keeps the score/cost pairing on
# a single AA run, which is the rule the whole page rests on.
MODEL_DETAIL_URL = "https://artificialanalysis.ai/models/{slug}"
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

# Cross-route disagreement retry (issue #89). AA updates its leaderboard and
# model-detail routes minutes apart, and a capture that straddles an update
# sees a mixed snapshot: check_route_agreement refuses it -- correctly, the
# page must never ship a score from one AA run beside a cost from another --
# but before this bound every such refusal turned the whole refresh run red
# even though a re-read minutes later passed (three red runs on 2026-09-29).
# On a disagreement the capture waits and re-fetches BOTH routes, comparing a
# complete fresh pair each time; the unit of retry is the (leaderboard,
# detail) PAIR, and the coding-agents page is still fetched once, after a
# pair agrees.
#
# The bound, against refresh.yml's timeout-minutes: 30 (1800 s), which is
# sized for a FULL heal run -- checkout, setup-python, the pip + Chromium
# installs, the browser suite, build, commit, publish (~7 min / 420 s
# measured) -- on top of the capture. Worst case for the capture itself:
#
#     waits:   (ATTEMPTS - 1) * WAIT_SECONDS
#              = 3 * 120                                             =  360 s
#     fetches: ATTEMPTS * 2 * FETCH_TIMEOUT_SECONDS
#              (leaderboard + detail per attempt, at the urlopen bound)
#              = 4 * 2 * 90                                          =  720 s
#     agents:  FETCH_TIMEOUT_SECONDS, fetched once after a pair agrees
#                                                                    =   90 s
#     total                                                        = 1170 s
#
# 1170 s is inside the 1200 s capture budget the suite pins
# (RetryBoundArithmeticTests), which leaves >= 600 s of the job for
# everything that is not the capture -- the ~420 s heal remainder, with
# slack. The fetch terms are the per-fetch BOUND, not a promise: a slow-drip
# body can outlast a single socket timeout, and the 600 s of headroom is
# what absorbs the difference rather than the sum meeting the job timeout.
ATTEMPTS = 4
WAIT_SECONDS = 120
FETCH_TIMEOUT_SECONDS = 90
# The exit code for a route disagreement that outlasts every re-read attempt
# (issue #100). AA's two routes are independently cached Vercel pages whose
# data lands at different times -- measured windows up to ~1 h -- so this
# refusal is usually gone within the hour and must not fail the refresh run
# the way a schema change (exit 1) does. refresh.yml green-skips on exactly
# this code and raises its own red alarm once the window is older than 3 h.
DISAGREEMENT_EXIT_CODE = 3


def _sleep(seconds: float) -> None:
    """The wait between re-read attempts, as a seam so tests can record the
    waits without sleeping."""
    time.sleep(seconds)


# AA no longer server-renders the full coding table it once did; what remains
# is a smaller set split across two arrays, currently thirteen rows. The floor
# only has to catch that set vanishing outright rather than shrinking, since
# AA is free to feature fewer runs without anything being broken.
CODING_ROW_FLOOR = 5

# AA stamps the live index version into the leaderboard copy.
VERSION_RE = re.compile(r"Intelligence Index v(\d+\.\d+)")

# The per-evaluation costs are the index weights already applied, so they sum
# to the published total. A drift past this means AA changed what the breakdown
# contains -- exactly the move that silently emptied two charts at v4.3.
SUM_TOLERANCE = 1e-6


def _generated_epoch(headers: email.message.Message) -> int | None:
    """When the route's cached copy was generated, as an epoch.

    Measured on every probed shape (200 HIT and 404 MISS alike), Vercel's
    `Date` header equals the entry's generation time (`date == now - age`
    exactly, within clock drift), which is the only observable that says HOW
    OLD the disagreeing snapshots are. The value is a diagnostic and nothing
    else: no behavior is gated on it, and a response that does not carry a
    parseable Date -- the cached-file path, an absent or malformed header --
    yields None rather than a guess.
    """
    raw = headers.get("Date")
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        # HTTP dates are GMT by definition; a format that still parses to a
        # naive datetime ("-0000") is read as UTC, not local time.
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp())


def _iso_utc(epoch: int | None) -> str:
    """A generation epoch as ISO-8601 UTC, or the explicit unknown marker.

    Rendered into diagnostics only -- an unparseable time must degrade to a
    readable placeholder, never to "None" or a bare blank."""
    if epoch is None:
        return "(generation time unknown)"
    return dt.datetime.fromtimestamp(
        epoch, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_html(cached: str | None, url: str = URL) -> tuple[str, int | None]:
    """The page text, plus the epoch the route's copy was generated at (or
    None -- see _generated_epoch)."""
    if cached:
        return (pathlib.Path(cached).read_text(encoding="utf-8",
                                               errors="replace"), None)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as r:
            text = r.read().decode("utf-8", errors="replace")
            return text, _generated_epoch(r.headers)
    except (urllib.error.URLError, OSError) as exc:
        # HTTPError subclasses URLError and socket.timeout subclasses OSError,
        # so this is every transport shape: DNS, connect, refused status, a
        # dead read. Same shape as the schema-change refusals -- one
        # actionable stderr line and a nonzero exit, not a traceback
        # (issue #66). Nothing has been written.
        sys.exit(f"{url}: fetch failed: {exc} -- nothing was captured; "
                 "check connectivity or the site, then re-run")


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
    # RSC splices marker strings ("$L1c") in among the records; they are
    # references to other payload nodes, not models, and every consumer
    # downstream treats an entry as a mapping.
    records = [m for m in best if isinstance(m, dict)]
    # AA has shipped the same record twice in one array -- identical id, name
    # and scores. Everything downstream keys on slug, so a duplicate would
    # either collapse silently in a dict or trip the uniqueness check and stop
    # the run over a row that carries no new information. Keep the first.
    seen: set[str] = set()
    unique = []
    for m in records:
        slug = m.get("slug")
        if isinstance(slug, str):
            if slug in seen:
                continue
            seen.add(slug)
        unique.append(m)
    return unique


def check_index_version(payload: str) -> str:
    """Refuse a capture from an index version build.py was not written for.

    AA publishes the per-evaluation weights on its methodology page and NEVER
    in the payload, so a rebalance is undetectable from the data alone: the
    numbers stay well-formed and the page silently ships wrong costs. v4.2 did
    exactly that. Pinning the version is the only place this can be caught.
    """
    found = VERSION_RE.search(payload)
    if not found:
        sys.exit("no Intelligence Index version in the payload -- page structure changed")
    if found.group(1) != INDEX_VERSION:
        sys.exit(
            f"AA is now on Intelligence Index v{found.group(1)}, but build.py is "
            f"written against v{INDEX_VERSION}. Re-read "
            "https://artificialanalysis.ai/methodology/intelligence-benchmarking "
            "-- a version bump can rename a cost slug or rebalance the weights, "
            "and neither shows up in the data."
        )
    return found.group(1)


def label(m: dict) -> str:
    """How a guard names the offending model.

    Deliberately not `name` alone: these messages fire precisely WHEN AA's
    schema moved, and `name` is one of the fields it has already deleted once
    -- which turned a real diagnostic into "None: cost breakdown lost its
    evaluations". `slug` is the join key, so it is the last thing to go.
    """
    for key in ("slug", "name", "shortName"):
        value = m.get(key)
        if isinstance(value, str) and value:
            return value
    return "<unidentifiable model>"


def check_cost_breakdown(models: list[dict]) -> int:
    """The cost breakdown still contains what build.py reads from it."""
    checked = 0
    for m in models:
        outer = m.get("intelligenceIndexCostPerTask")
        if not isinstance(outer, dict):
            continue
        evaluations = outer.get("evaluations")
        total = (outer.get("cost") or {}).get("total")
        if not isinstance(evaluations, list) or not isinstance(total, (int, float)):
            sys.exit(f"{label(m)}: cost breakdown lost its evaluations or total "
                     "-- schema changed")
        slugs = {e.get("slug") for e in evaluations if isinstance(e, dict)}
        if GDPVAL_SLUG not in slugs:
            sys.exit(
                f"{label(m)}: cost breakdown no longer carries "
                f"'{GDPVAL_SLUG}' -- the GDPval axis has no cost to plot. "
                "Re-read the leaderboard rather than publishing an empty chart."
            )
        summed = sum(e["weightedCostPerTask"] for e in evaluations
                     if isinstance(e, dict)
                     and isinstance(e.get("weightedCostPerTask"), (int, float)))
        if abs(summed - total) > SUM_TOLERANCE * max(1.0, abs(total)):
            sys.exit(
                f"{label(m)}: per-evaluation costs sum to {summed!r} but the "
                f"published total is {total!r}. build.py divides an index weight "
                "back out of these, which is only valid while they sum to the total."
            )
        checked += 1
    if not checked:
        sys.exit("no model carries a cost breakdown -- schema changed")
    return checked


def balanced_object(text: str, start: int) -> str | None:
    """Return the JSON object literal beginning at text[start] == '{'."""
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
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def enclosing_object(payload: str, offset: int, window: int = 40000) -> dict | None:
    """The smallest JSON object containing `offset`, parsed.

    Walks back to successive '{' candidates until one both parses and actually
    spans the offset. `window` bounds that walk: a row is a few KB, so a search
    that runs further has lost the thread and should give up rather than crawl
    the whole payload.
    """
    i = offset
    floor = max(0, offset - window)
    while i > floor:
        i = payload.rfind("{", floor, i)
        if i < 0:
            return None
        raw = balanced_object(payload, i)
        if raw and i + len(raw) > offset:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                continue
    return None


def detail_host_slug(models: list[dict]) -> str:
    """Which model's page to pull the corpus from.

    A detail page lists every model EXCEPT the one it is about, so whichever
    slug is picked loses its detail-only fields. Picking one with no measured
    cost per task makes that free: without a cost it cannot appear on any
    chart, so the loss is confined to table columns the merge back-fills from
    the leaderboard anyway. Sorted, so the choice -- and therefore the capture
    -- is stable between runs instead of churning the diff.
    """
    def measured(m):
        # Two shapes: the object {"cost": {"total": x}, ...} on the detail
        # route, and a bare number -- just the total -- on the leaderboard
        # since AA flattened it. Either means AA spent money on this model.
        # AA writes ABSENT fields as the string "$undefined", which is why
        # the type checks are explicit rather than truthiness.
        outer = m.get("intelligenceIndexCostPerTask")
        if isinstance(outer, (int, float)):
            return True
        cost = outer.get("cost") if isinstance(outer, dict) else None
        total = cost.get("total") if isinstance(cost, dict) else None
        return isinstance(total, (int, float))

    unpriced = sorted(m["slug"] for m in models
                      if isinstance(m.get("slug"), str) and not measured(m))
    if not unpriced:
        sys.exit("every model carries a cost -- no free detail host; schema changed")
    return unpriced[0]


def merge_captures(base: list[dict], detail: list[dict]) -> list[dict]:
    """Leaderboard records widened with the detail route's extra fields.

    The leaderboard is the authority on WHICH models exist and on every field
    it still carries; detail only fills gaps. Overlapping values are identical
    between the routes, so gap-filling and overwriting would agree -- filling
    is chosen so a future divergence surfaces on the detail-only fields rather
    than silently rewriting the leaderboard's own numbers.
    """
    def fill(into, extra):
        """`into` wins; `extra` supplies only what is absent.

        One level deep, because the split runs THROUGH a nested object: the
        leaderboard kept intelligenceIndexCostPerTask.cost and dropped its
        .evaluations, so a key-level fill would let the surviving stub shadow
        the complete breakdown and leave the GDPval axis with no cost.
        """
        out = dict(into)
        for k, v in extra.items():
            if k not in out:
                out[k] = v
            elif isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = fill(out[k], v)
            elif isinstance(v, dict) and not isinstance(out[k], dict):
                # Same key, different SHAPE. The leaderboard flattened
                # intelligenceIndexCostPerTask to its bare total while the
                # detail route kept the object with the per-evaluation
                # breakdown. A scalar cannot hold what the object holds, so
                # the object wins; the scalar was its `cost.total` anyway.
                out[k] = v
        return out

    by_slug = {m["slug"]: m for m in detail if isinstance(m.get("slug"), str)}
    return [fill(m, by_slug[m["slug"]]) if by_slug.get(m.get("slug")) else m
            for m in base]


def coding_agent_rows(payload: str) -> list[dict]:
    """Every agent+model row in the Coding Agent Index, wherever it is nested.

    AA splits these across at least two arrays: `rows`, holding the highlighted
    selection, and `benchmarkRows`, which begins with an RSC BACK-REFERENCE
    STRING pointing at a row in the first array and then carries the remainder
    inline. Anchoring on an array that starts with an object missed the second
    array completely and published 10 of 13 rows without a word.

    So this anchors on the PAIR ITSELF -- every object carrying a score and a
    cost, wherever it sits -- and dedupes. A future reshuffle between arrays,
    or a third array, costs nothing.
    """
    seen: dict[str, dict] = {}
    for m in re.finditer(r'"indexScore"', payload):
        row = enclosing_object(payload, m.start())
        if not isinstance(row, dict):
            continue
        mean = row.get("mean")
        if not (isinstance(row.get("indexScore"), (int, float))
                and isinstance(mean, dict)
                and isinstance(mean.get("costUsd"), (int, float))):
            continue
        # Back-references mean one row can be reachable twice.
        key = row.get("id") or row.get("displayLabel")
        if isinstance(key, str):
            seen.setdefault(key, row)
    priced = list(seen.values())
    # A collapse below the highlighted selection means the page moved its data
    # or renamed the pair -- a hand-read signal, not something to publish a
    # half-empty chart from.
    if len(priced) < CODING_ROW_FLOOR:
        sys.exit(
            f"coding agent index: only {len(priced)} rows carry indexScore and "
            f"mean.costUsd -- schema changed"
        )
    return priced


# The refusal path's output (issue #118): both routes' raw payloads plus the
# disagreement map, keyed exactly as check_route_agreement reported them.
# The coding-agents capture is deliberately NOT in it -- the agents page is a
# different AA product fetched once after a pair agrees, and pulling it onto
# the refusal path would break the retry-bound arithmetic the suite pins; a
# disputed build reads the last-good agents capture instead.
def window_start_epoch() -> int:
    """When the disagreement window began, as the refusal records it.

    The window's start is the workflow stamp's first line -- the epoch the
    Capture step wrote when the window opened. Reading it (instead of
    resetting to now) is what keeps the disputed banner naming ONE window
    across hours; without a stamp -- a hand-run before any workflow saw the
    window -- this fetch starts it.
    """
    stamp = ROOT / "data" / "aa-route-disagreement.txt"
    try:
        return int(stamp.read_text(encoding="utf-8").splitlines()[0])
    except (OSError, IndexError, ValueError):
        return int(time.time())


def disagreement_snapshot(base: list, detail: list, divergences: list,
                          base_generated: int | None,
                          detail_generated: int | None) -> dict:
    """The disputed snapshot: schema, window, both raw route payloads, and
    the disagreement map as (slug, path, leaderboard, detail) entries. The
    model-detail host slug and the index version are deliberately absent:
    the refusal path has no CapturePair to read them from, and both are
    derivable from the payloads -- never invented to fill a field."""
    return {
        "schema": 1,
        "capturedAt": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "windowStartEpoch": window_start_epoch(),
        "leaderboardGeneratedAt": base_generated,
        "detailGeneratedAt": detail_generated,
        "leaderboard": base,
        "detail": detail,
        "disagreements": [
            {"slug": slug, "path": path, "lb": lb, "dt": dt}
            for slug, path, lb, dt in divergences
        ],
    }


def write_atomic(path: pathlib.Path, text: str) -> None:
    """Stage `text` in a temp file beside `path`, then os.replace it in.

    A crash mid-write (ENOSPC, a killed runner) used to leave a truncated
    file where the previous good capture -- the one the page builds from
    and that is committed -- used to be (issue #66). The staging file lives
    in the destination's own directory so the rename never crosses a
    filesystem, and carries the pid so two concurrent fetches cannot stage
    onto the same file. On any failure the staging file is removed and the
    previous capture is left byte-intact.
    """
    staged = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        staged.write_text(text, encoding="utf-8")
        os.replace(staged, path)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise


class _RouteDisagreement(SystemExit):
    """check_route_agreement's refusal, tagged for the retry loop.

    The retry loop catches ONLY this tagged exit; every other SystemExit a
    capture attempt can raise (schema change, index bump, no free detail
    host) propagates uncaught -- pinned from main() by
    RouteDisagreementRetryTests. The tag is applied at the agreement call
    site by converting whatever SystemExit check_route_agreement raises,
    and TODAY that is only the divergence exit: the check's own contract is
    to return the compared count or exit listing the divergences, and the
    coupling is to those two documented outcomes, not a promise about its
    future -- a second exit kind appearing there would be tagged and
    retried with this code none the wiser.

    Tagging keeps the scoping true without matching on the message. The
    message is untouched: on the last attempt the refusal propagates out of
    the retry helper to main(), which prints it verbatim and exits
    DISAGREEMENT_EXIT_CODE (issue #100) -- the distinct code the refresh
    workflow green-skips on, since a straddled pair is usually AA's cache
    stagger and not a broken extractor.

    The two generation epochs ride along for the diagnostics only: the
    stderr lines name how old each disagreeing copy was. No behavior is
    gated on them, and either may be None. Since issue #118 the refusal
    also carries the refused ATTEMPT's two raw route payloads and the
    structured divergence list -- exactly what the disagreement snapshot is
    built from, so a refused read becomes a buildable disputed capture
    without re-fetching or re-deriving anything.
    """

    def __init__(self, message: object, base_generated: int | None = None,
                 detail_generated: int | None = None, base: list | None = None,
                 detail: list | None = None, divergences: list | None = None) -> None:
        super().__init__(message)
        self.base_generated = base_generated
        self.detail_generated = detail_generated
        self.base = base
        self.detail = detail
        self.divergences = divergences


class CapturePair(typing.NamedTuple):
    """One capture attempt's agreed (leaderboard, detail) pair, what the
    capture log quotes from the attempt that produced it, and when each
    route said its copy was generated (epoch, or None)."""

    base: list
    detail: list
    host: str
    version: str
    shared_values: int
    base_generated: int | None
    detail_generated: int | None


def capture_pair(cached_base: str | None, cached_detail: str | None) -> CapturePair:
    """One capture attempt: BOTH routes fetched fresh, each parsed from its
    own bytes, and check_route_agreement run UNCHANGED over the fresh pair.

    detail_host_slug is recomputed from THIS attempt's own leaderboard: the
    detail page is chosen for what its page excludes, so a retry must never
    pair attempt N's leaderboard with attempt N-1's host. Everything the
    caller keeps comes from the attempt that returns from here -- no parsed
    value crosses attempts, so the written capture cannot mix one attempt's
    score with another's cost. The generation epochs are the one exception,
    and only on the refusal path: they ride the tagged exit to the stderr
    diagnostics, never into the capture.
    """
    base_text, base_generated = fetch_html(cached_base)
    payload = flight_payload(base_text)
    version = check_index_version(payload)
    base = richest_models_array(payload)

    host = detail_host_slug(base)
    detail_text, detail_generated = fetch_html(
        cached_detail, MODEL_DETAIL_URL.format(slug=host))
    detail = richest_models_array(flight_payload(detail_text))
    # The page claims the two routes agree exactly on every value they share;
    # only a check run while they are still separate can see a divergence --
    # after the merge, the leaderboard's copy shadows the detail's (issue
    # #44).
    try:
        shared_values = check_route_agreement(base, detail)
    except SystemExit as exc:
        raise _RouteDisagreement(exc.code, base_generated,
                                 detail_generated, base, detail,
                                 getattr(exc, "divergences", None)) from None
    return CapturePair(base, detail, host, version, shared_values,
                       base_generated, detail_generated)


def _generation_note(exc: _RouteDisagreement) -> str:
    """The parenthetical appended to an intermediate retry line: how old each
    disagreeing copy was, when either route reported it. Empty when neither
    did, so the quiet case keeps the exact line shape issue #89 shipped."""
    if exc.base_generated is None and exc.detail_generated is None:
        return ""
    return (f" (leaderboard generated {_iso_utc(exc.base_generated)}, "
            f"detail generated {_iso_utc(exc.detail_generated)})")


def capture_pair_retrying(cached_base: str | None,
                          cached_detail: str | None) -> CapturePair:
    """capture_pair, retried while the two routes disagree (issue #89).

    Each refusal costs one stderr line and one bounded wait, then a fully
    fresh pair -- fresh bytes, fresh parse, nothing carried over. The loop
    covers attempts 1..ATTEMPTS-1; the LAST attempt runs outside the try, so
    its refusal propagates to main() unchanged: the exact diagnostic the
    check has always raised, nothing written. main() alone turns it into
    exit DISAGREEMENT_EXIT_CODE (issue #100).

    A capture whose pages BOTH come from --html/--detail-html files is
    exempt: those bytes are pinned, so a re-read would return the identical
    snapshot and the wait could never clear the disagreement -- the one
    attempt then refuses exactly as before this bound existed.
    """
    both_cached = bool(cached_base) and bool(cached_detail)
    attempts = 1 if both_cached else ATTEMPTS
    for attempt in range(1, attempts):
        try:
            return capture_pair(cached_base, cached_detail)
        except _RouteDisagreement as exc:
            print(f"routes disagree on attempt {attempt} of {attempts}; "
                  f"re-reading both routes in {WAIT_SECONDS}s"
                  f"{_generation_note(exc)}",
                  file=sys.stderr)
            _sleep(WAIT_SECONDS)
    return capture_pair(cached_base, cached_detail)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="use a cached copy of the leaderboard HTML")
    ap.add_argument("--detail-html", help="use a cached copy of a model detail page")
    ap.add_argument("--agents-html", help="use a cached copy of the coding-agents HTML")
    args = ap.parse_args()

    try:
        pair = capture_pair_retrying(args.html, args.detail_html)
    except _RouteDisagreement as exc:
        # The divergence diagnostic is the original, verbatim: a straddled
        # pair and a broken extractor must stay distinguishable by eye. The
        # appended line explains WHY the exit code differs from every other
        # refusal and what the refresh will do about it (issue #118: the
        # refusal is now a buildable disputed capture, not a skipped hour).
        print(str(exc), file=sys.stderr)
        print(f"leaderboard generated {_iso_utc(exc.base_generated)}, "
              f"detail generated {_iso_utc(exc.detail_generated)} — "
              "Vercel serves the two routes from independent caches and "
              "AA's data lands on them at different times (issues #100, "
              "#118); refresh builds and publishes the disputed capture "
              "this hour", file=sys.stderr)
        # The snapshot's pieces all come from the refused attempt -- both
        # raw payloads, the structured divergence list, the per-route
        # generation times -- so the disputed page is exactly the read that
        # was refused, never a second one.
        snapshot = disagreement_snapshot(
            exc.base, exc.detail, exc.divergences or [],
            exc.base_generated, exc.detail_generated)
        # The schema guards stay red on the disputed merge (issue #118):
        # only the disagreement itself stopped being red. A detail payload
        # that has lost what build.py reads fails here -- exit 1, no
        # snapshot written -- exactly as it would on an agreeing pair.
        models = merge_captures(exc.base, exc.detail)
        check_cost_breakdown(models)
        out = OUT.with_name(DISPUTED_SNAPSHOT_NAME)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(out, json.dumps(snapshot, indent=1))
        print(f"wrote {out.relative_to(ROOT)}: "
              f"{len(snapshot['disagreements'])} disputed value(s) across "
              f"{len({d['slug'] for d in snapshot['disagreements']})} model(s)",
              file=sys.stderr)
        sys.exit(DISAGREEMENT_EXIT_CODE)
    models = merge_captures(pair.base, pair.detail)
    priced = check_cost_breakdown(models)
    # An agreeing capture ends any window: drop a leftover snapshot so the
    # build this capture feeds cannot render the disputed layer from stale
    # data. The workflow's own retirement commit removes the tracked copy on
    # the same rule.
    OUT.with_name(DISPUTED_SNAPSHOT_NAME).unlink(missing_ok=True)
    agents_text, _ = fetch_html(args.agents_html, AGENTS_URL)
    agents = coding_agent_rows(flight_payload(agents_text))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(OUT, json.dumps(models, indent=1))
    write_atomic(AGENTS_OUT, json.dumps(agents, indent=1))
    STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    scored = sum(1 for m in models if isinstance(m.get("intelligenceIndex"), (int, float)))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {scored} with an "
          f"intelligence index, {priced} with a v{pair.version} cost breakdown "
          f"(detail merged from /models/{pair.host}; {pair.shared_values} shared "
          "values cross-checked)")
    print(f"wrote {AGENTS_OUT.relative_to(ROOT)}: {len(agents)} agent+model rows "
          f"with a paired index score and cost per task")


if __name__ == "__main__":
    main()
