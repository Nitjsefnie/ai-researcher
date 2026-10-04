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
import http.client
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
    check_route_agreement, merge_captures,
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
#     page bound: PAGE_ATTEMPTS * FETCH_TIMEOUT_SECONDS plus the backoff
#              sleeps between attempts ((1+2) * PAGE_BACKOFF_SECONDS)
#              = 3 * 25 + 15                                         =   90 s
#     waits:   (ATTEMPTS - 1) * WAIT_SECONDS
#              = 3 * 120                                             =  360 s
#     fetches: ATTEMPTS * 2 * (page bound)
#              (leaderboard + detail per attempt, each bounded as above)
#              = 4 * 2 * 90                                          =  720 s
#     agents:  one page fetch after a pair agrees                    =   90 s
#     total                                                        = 1170 s
#
# 1170 s is inside the 1200 s capture budget the suite pins
# (RetryBoundArithmeticTests), which leaves >= 600 s of the job for
# everything that is not the capture -- the ~420 s heal remainder, with
# slack. The levels do NOT multiply on a hard-down site, because transport
# exhaustion SHORT-CIRCUITS: the first page's three attempts exhaust,
# fetch_html refuses, and the process exits within one page bound (~90 s)
# -- the disagreement loop never reaches attempt 2. Their product
# materializes only when every page fetch SUCCEEDS slowly (near its
# socket bound) while the routes keep disagreeing. The fetch terms are
# the per-attempt BOUND, not a promise: a slow-drip body can outlast a
# single socket timeout, and the 600 s of headroom is what absorbs the
# difference rather than the sum meeting the job timeout.
ATTEMPTS = 4
WAIT_SECONDS = 120
# One page-fetch ATTEMPT's stall bound -- urlopen's socket timeout, the
# most a single attempt may stall before the page retry (issue #154)
# declares it dead and backs off. Tighter than the pre-#154 90 s on
# purpose: with the retry as the recovery path a stall costs one attempt
# instead of the whole page, and the page bound stays 90 s (3 x 25 + 15),
# so the combined worst case above is unchanged at 1170 s.
FETCH_TIMEOUT_SECONDS = 25
# The page-fetch retry (issue #154): a transient upstream answer -- HTTP
# 429, a 5xx, a timeout, a dropped connection -- is attempted at most
# PAGE_ATTEMPTS times IN TOTAL (fetch_html's loop bound, not a retry
# count) with linear backoff (attempt k waits k * PAGE_BACKOFF_SECONDS)
# before the page is refused for good. A non-retryable 4xx is an ANSWER,
# not an outage, and fails on attempt 1; the classifier's precedent is
# audit.yml's pip-audit retry (issue #128, PR #142).
PAGE_ATTEMPTS = 3
PAGE_BACKOFF_SECONDS = 5
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


def _retryable_transport_error(exc: BaseException) -> bool:
    """Whether a page-fetch attempt's failure is worth another attempt.

    The classifier mirrors audit.yml's pip-audit retry (issue #128): HTTP
    429 and the 5xx family are the rate-limit and server-outage answers a
    retry can clear; every OTHER 4xx is an answer -- a 404 is a moved page,
    a 403 a block -- that no retry will change, so it fails on attempt 1.
    Beyond the status code everything transport-shaped gets the full bound:
    URLError and its reason (DNS, connect, refused, SSL), socket timeouts,
    and dropped connections (http.client.HTTPException -- RemoteDisconnected,
    IncompleteRead). HTTPError subclasses URLError subclasses OSError, so
    the status-bearing exception is tested FIRST and the bare transport
    check last.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (OSError, http.client.HTTPException))


def fetch_html(cached: str | None, url: str = URL) -> tuple[str, int | None]:
    """The page text, plus the epoch the route's copy was generated at (or
    None -- see _generated_epoch).

    Each page carries its own bounded retry (issue #154): a transient
    answer is retried within a total of PAGE_ATTEMPTS attempts with
    linear backoff, and the refusal -- exhaustion or a non-retryable 4xx
    -- is the same one-line guarded exit as before the retry existed. The
    #89 pair-level loop sits OUTSIDE this one and never re-enters it: a
    refusal here ends the capture, which is what keeps a hard-down site
    failing fast inside the combined worst case documented beside the
    bounds."""
    if cached:
        return (pathlib.Path(cached).read_text(encoding="utf-8",
                                               errors="replace"), None)
    for attempt in range(1, PAGE_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as r:
                text = r.read().decode("utf-8", errors="replace")
                return text, _generated_epoch(r.headers)
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            # HTTPError subclasses URLError and socket.timeout subclasses
            # OSError, so this is every transport shape: DNS, connect,
            # refused status, a dead read, a dropped body (issue #66).
            # The classifier decides whether the answer is transient;
            # either way the refusal is the same one actionable stderr
            # line, not a traceback.
            if not _retryable_transport_error(exc) or attempt == PAGE_ATTEMPTS:
                exhausted = f" after {attempt} attempts" if attempt > 1 else ""
                sys.exit(f"{url}: fetch failed{exhausted}: {exc} -- nothing "
                         "was captured; check connectivity or the site, "
                         "then re-run")
            delay = attempt * PAGE_BACKOFF_SECONDS
            print(f"{url}: attempt {attempt} of {PAGE_ATTEMPTS} failed "
                  f"({exc}); retrying in {delay}s", file=sys.stderr)
            _sleep(delay)
    # Unreachable while PAGE_ATTEMPTS >= 1: the last attempt's try returns
    # on success and exits on failure, so the loop cannot fall through.
    raise AssertionError("fetch_html ran out of attempts without a verdict")


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


# The one shared field AA splits across shapes: a bare number (its cost.total)
# on the leaderboard, the {cost, evaluations} object on the detail route. A
# disagreement reported at this path is the shape-split one.
COST_TOTAL_PATH = "intelligenceIndexCostPerTask.cost.total"

# _value_at's marker for a path that resolves nowhere on a record -- a missing
# key, a walk through a scalar, a list-index path. Deliberately not None: a
# JSON null is a VALUE (an absent field AA published as null), and a baseline
# null must match a route's null without reading as resolvable-elsewhere.
_UNRESOLVED = object()


def _value_at(record, path):
    """The value a record carries at a disagreement path, or _UNRESOLVED.

    Dotted-path read over nested dicts. The leaderboard's flattened cost
    scalar reads at COST_TOTAL_PATH -- the same reshape check_route_agreement
    applies (and the shape the detail-stale repair leaves behind). List-index
    paths resolve to _UNRESOLVED: the current window has none, and an
    unresolvable lookup may only fall back to the disputed rendering.
    """
    parts = path.split(".")
    value = record
    for index, part in enumerate(parts):
        if not isinstance(value, dict):
            remaining = ".".join(parts[index:])
            if (remaining == "cost.total"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)):
                return value
            return _UNRESOLVED
        if part not in value:
            return _UNRESOLVED
        value = value[part]
    return value


def _set_value_at(record, path, value) -> bool:
    """Set `value` at a dotted path over existing dicts; False when the walk
    leaves the record's shape (the caller then treats the repair as failed)."""
    parts = path.split(".")
    node = record
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    if not isinstance(node, dict):
        return False
    node[parts[-1]] = value
    return True


def heal_route_disagreement(exc, baseline):
    """One route provably stale: the fresh route's capture, or None.

    Overseer ruling (delegated by the maintainer), 2026-10-04 (issue #176).
    When ALL of one route's disputed values equal the last committed capture
    (the last agreeing capture, data/aa-raw-models.json) and NONE of the other
    route's do, the matching route is serving that capture unchanged -- it is
    stale -- and its disagreeing values are dropped: the capture is the fresh
    route's copy of every shared field, through the normal capture path. This
    amends the #118 disputed rendering ONLY for that provable case; where
    staleness cannot be shown -- mixed matches, both routes differing from the
    last capture, a disputed slug with no row in the last capture -- this
    returns None and the disputed rendering stands unchanged. The per-route
    generation timestamps are never consulted: #117's window had copies 3 s
    apart carrying different data, so no timestamp identifies the stale route.

    When the DETAIL route is stale, its detail-only fields (the per-evaluation
    cost breakdown, parameters, license, release date) stay at their last
    capture, and any field that would MIX two generations renders absent:
    for a model whose cost.total moved, the stale breakdown is dropped and
    the fresh flattened total takes its place -- the GDPval cost that
    breakdown fed renders '--' until the routes agree. check_cost_breakdown
    remains the refusal of the alternative: a stale breakdown left under a
    moved total sums to the old total and exits. Every value is still AA's
    own, from the snapshot or the committed capture; nothing is estimated.

    Returns (models, note) -- the healed capture in merge_captures' shape and
    a one-line diagnostic -- or None when staleness is not provable (no
    baseline, unresolvable paths, or a repair that fails its own
    verification: every divergent path must end at the fresh route's value).
    Never raises for a disagreement.
    """
    entries = exc.divergences
    if not entries or not isinstance(baseline, list) or not baseline:
        return None
    base_by_slug = {m.get("slug"): m for m in baseline if isinstance(m, dict)}
    lb_matches: list[bool] = []
    dt_matches: list[bool] = []
    for slug, path, lb_value, dt_value in entries:
        record = base_by_slug.get(slug)
        base_value = (_value_at(record, path)
                      if record is not None else _UNRESOLVED)
        resolvable = base_value is not _UNRESOLVED
        lb_matches.append(resolvable and lb_value == base_value)
        dt_matches.append(resolvable and dt_value == base_value)
    if all(lb_matches) and not any(dt_matches):
        stale_route = "leaderboard"
    elif all(dt_matches) and not any(lb_matches):
        stale_route = "detail"
    else:
        return None

    models = merge_captures(exc.base, exc.detail)
    by_slug = {m.get("slug"): m for m in models if isinstance(m.get("slug"), str)}
    lb_by_slug = {m.get("slug"): m for m in exc.base if isinstance(m.get("slug"), str)}

    absent_costs = 0
    if stale_route == "detail":
        # The leaderboard is fresh, and merge_captures already keeps its copy
        # of every shared scalar. The one place the stale detail record still
        # shadows it is the shape split: the merge lets the object win, which
        # would publish the stale total -- and the stale breakdown under it.
        # Drop the breakdown (the GDPval cost renders absent) and keep the
        # fresh scalar total.
        cost_moves = sorted({slug for slug, path, _, _ in entries
                             if path == COST_TOTAL_PATH})
        for slug in cost_moves:
            record = by_slug.get(slug)
            leaderboard_record = lb_by_slug.get(slug)
            fresh_total = (leaderboard_record or {}).get(
                "intelligenceIndexCostPerTask")
            if (record is None or leaderboard_record is None
                    or not isinstance(fresh_total, (int, float))
                    or isinstance(fresh_total, bool)):
                return None
            record["intelligenceIndexCostPerTask"] = fresh_total
        absent_costs = len(cost_moves)
    else:
        # The detail route is fresh; the merge kept the stale leaderboard's
        # copy of every divergent scalar. Override each divergent path with
        # the detail route's value -- the cost total included, where the
        # merge's object-wins rule already took the fresh object.
        for slug, path, _lb_value, dt_value in entries:
            record = by_slug.get(slug)
            if record is None or not _set_value_at(record, path, dt_value):
                return None

    # Verification: every divergent path now carries the fresh route's value.
    # A repair that misses -- an unmodelled shape split letting the stale
    # detail record shadow a fresh scalar, a path the setter could not walk --
    # is staleness the code cannot actually deliver, so it falls back rather
    # than publish a half-repaired merge.
    for slug, path, lb_value, dt_value in entries:
        record = by_slug.get(slug)
        healed_value = _value_at(record, path)
        expected = dt_value if stale_route == "leaderboard" else lb_value
        if healed_value is _UNRESOLVED or healed_value != expected:
            return None

    note = (
        f"route disagreement resolved: the {stale_route} route is stale -- "
        f"all {len(entries)} disputed value(s) equal the last committed "
        "capture and none of the other route's do; publishing the fresh "
        "route through the normal capture path"
        + (f" ({absent_costs} GDPval cost(s) absent until the routes agree)"
           if absent_costs else " (every axis pairs same-run values)"))

    return models, note


def _healed_capture(exc):
    """heal_route_disagreement over the capture on disk, or None.

    The refusing run has not written OUT -- whatever sits there is the last
    committed capture (the refresh runs on a clean checkout), exactly the
    baseline the staleness verdict compares against. A missing, corrupt or
    non-list file is staleness nobody can prove: None, and the disputed path
    takes over.
    """
    try:
        baseline = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(baseline, list):
        return None
    return heal_route_disagreement(exc, baseline)


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

    def __init__(self, message: object, base_generated: int | None,
                 detail_generated: int | None, base: list,
                 detail: list, divergences: list) -> None:
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
                                 getattr(exc, "divergences") or []) from None
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
        # refusal is a buildable disputed capture; issue #176: it heals
        # first when one route is provably the last capture's copy).
        print(str(exc), file=sys.stderr)
        print(f"leaderboard generated {_iso_utc(exc.base_generated)}, "
              f"detail generated {_iso_utc(exc.detail_generated)} — "
              "Vercel serves the two routes from independent caches and "
              "AA's data lands on them at different times (issues #100, "
              "#118); refresh builds and publishes the disputed capture "
              "this hour", file=sys.stderr)
        healed = _healed_capture(exc)
        if healed is None:
            # The snapshot's pieces all come from the refused attempt -- both
            # raw payloads, the structured divergence list, the per-route
            # generation times -- so the disputed page is exactly the read
            # that was refused, never a second one.
            snapshot = disagreement_snapshot(
                exc.base, exc.detail, exc.divergences,
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
        models, heal_note = healed
        print(heal_note, file=sys.stderr)
        origin = (f"v{INDEX_VERSION} cost breakdown (stale-route heal, "
                  "issue #176: the stale route's disagreeing values are "
                  "discarded)")
    else:
        models = merge_captures(pair.base, pair.detail)
        origin = (f"v{pair.version} cost breakdown (detail merged from "
                  f"/models/{pair.host}; {pair.shared_values} shared values "
                  "cross-checked)")
    priced = check_cost_breakdown(models)
    # An agreeing capture -- or a healed one -- ends any window: drop a
    # leftover snapshot so the build this capture feeds cannot render the
    # disputed layer from stale data. The workflow's own retirement commit
    # removes the tracked copy on the same rule.
    OUT.with_name(DISPUTED_SNAPSHOT_NAME).unlink(missing_ok=True)
    agents_text, _ = fetch_html(args.agents_html, AGENTS_URL)
    agents = coding_agent_rows(flight_payload(agents_text))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(OUT, json.dumps(models, indent=1))
    write_atomic(AGENTS_OUT, json.dumps(agents, indent=1))
    STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    scored = sum(1 for m in models if isinstance(m.get("intelligenceIndex"), (int, float)))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {scored} with an "
          f"intelligence index, {priced} with a {origin}")
    print(f"wrote {AGENTS_OUT.relative_to(ROOT)}: {len(agents)} agent+model rows "
          f"with a paired index score and cost per task")


if __name__ == "__main__":
    main()
