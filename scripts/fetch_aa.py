#!/usr/bin/env python3
"""Extract the Artificial Analysis model dataset from the public leaderboard page.

artificialanalysis.ai is a Next.js app; the leaderboard's full model array ships
inside the RSC flight payload embedded in the HTML rather than via a public JSON
API. This pulls the page, reassembles the flight chunks, and picks out the rich
model array (the one carrying intelligenceIndex, not the lightweight filter list).

Writes two captures, both from artificialanalysis.ai and nothing else:

  data/aa-raw-models.json         the model leaderboard WIDENED with a model
                                  detail page -- the leaderboard publishes
                                  every value it carries, and the detail route
                                  fills only what it omits
  data/aa-raw-coding-agents.json  the Coding Agent Index -- agent+model rows
                                  carrying indexScore and mean.costUsd on the
                                  SAME record, so no reweighting is needed

alongside data/captured-at.txt, the date the capture was taken.

Usage:  python3 scripts/fetch_aa.py [--html F] [--detail-html F]
        [--methodology-html F] [--agents-html F]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
    GDPVAL_INDEX_WEIGHT, GDPVAL_SLUG, INDEX_VERSION, SUM_TOLERANCE,
    breakdown_matches_total, evaluation_cost_per_task, merge_captures,
)

URL = "https://artificialanalysis.ai/leaderboards/models"
# The leaderboard's payload was trimmed once, and it still omits licenceName,
# releaseDate, the parameter count and the per-evaluation cost breakdown. Those
# ship, on any model detail page, which embeds the whole corpus for its
# comparison widgets. The two routes are NOT the same generation, though: the
# detail corpus is MEASURED to lag the leaderboard, and the per-route generation
# timestamps do not identify the stale one -- a detail page regenerated later
# still embeds the older corpus (issue #200). So the leaderboard is the
# authority: it publishes every value it carries, and the detail route fills
# only what it omits. See merge_captures in build.py.
MODEL_DETAIL_URL = "https://artificialanalysis.ai/models/{slug}"
# The Coding Agent Index. This is a DIFFERENT AA product from the leaderboard's
# `codingIndex` field: it scores agent+model+harness combinations (Claude Code -
# Opus 5 (xhigh), Codex - GPT-6 Astra (max)) rather than bare models, and it is
# the index AA means when the methodology page says Terminal-Bench v2.1 "remains
# part of the Coding Index". It is the only /agents/* route carrying a benchmark;
# the other six are marketing comparison pages with no index and no cost.
AGENTS_URL = "https://artificialanalysis.ai/agents/coding-agents"
# The Intelligence Index version pin reads THIS page (issue #220): the version
# string left the leaderboard payload, and the methodology page headlines its
# live version ("Artificial Analysis Intelligence Index v4.3.2"). The pin
# compares at MAJOR.MINOR granularity -- AA ships point releases within a
# generation without rebalancing the weights.
METHODOLOGY_URL = (
    "https://artificialanalysis.ai/methodology/intelligence-benchmarking")
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

# One page-fetch ATTEMPT's stall bound -- urlopen's socket timeout, the most a
# single attempt may stall before the retry (issue #154) declares it dead and
# backs off. Tighter than the pre-#154 90 s on purpose: with the retry as the
# recovery path a stall costs one attempt instead of the whole page.
FETCH_TIMEOUT_SECONDS = 25
# The page-fetch retry (issue #154): a transient upstream answer -- HTTP
# 429, a 5xx, a timeout, a dropped connection -- is attempted at most
# PAGE_ATTEMPTS times IN TOTAL (fetch_html's loop bound, not a retry
# count) with linear backoff (attempt k waits k * PAGE_BACKOFF_SECONDS)
# before the page is refused for good. A non-retryable 4xx is an ANSWER,
# not an outage, and fails on attempt 1; the classifier's precedent is
# audit.yml's pip-audit retry (issue #128, PR #142).
#
# Against refresh.yml's timeout-minutes: 30 (1800 s), which is sized for a FULL
# run -- checkout, setup-python, the pip + Chromium installs, the browser suite,
# build, commit, publish. Worst case for the capture itself is five page
# fetches (the methodology version pin, two spaced leaderboard looks, the
# detail page, the coding agents), each bounded at
# PAGE_ATTEMPTS * FETCH_TIMEOUT_SECONDS plus its backoff sleeps
# (3 * 25 + 15 = 90 s), so at most 450 s -- and that only if every fetch
# succeeds slowly; transport exhaustion SHORT-CIRCUITS, fetch_html refuses and
# the process exits inside one page bound. The fetch terms are the per-attempt
# BOUND, not a promise: a slow-drip body can outlast a single socket timeout,
# and the job's headroom is what absorbs the difference.
PAGE_ATTEMPTS = 3
PAGE_BACKOFF_SECONDS = 5

# Issue #208: AA's two routes can serve two different generations of the
# corpus at once, and a single leaderboard read takes whichever half is
# cached at that instant. So each run reads the leaderboard TWICE, this
# many seconds apart -- far enough that the two reads land on different
# Vercel cache generations when a window is live -- plus the detail page.
# The spacing is a lower bound on how long an update stays detectable, not
# a retry: both looks are published, both are kept when they disagree.
DISPUTE_LOOK_SPACING_SECONDS = 180

# Fields that NEVER go red and never identify a generation: AA's speed and
# latency family re-samples every hour BY DESIGN (median/quartile output
# speed, time-to-first-token, end-to-end latency, and the timescale chart
# data built from them), so two looks of the SAME generation routinely
# disagree on them and a dispute raised on that movement would hold the
# page red permanently. The set is hardcoded and never widened silently:
# a new speed-shaped field starts as a generation-identity difference that
# never reds (it is not dispute-capable) and joins this set only by a
# reviewed change to this constant.
NEVER_RED_FIELDS = frozenset({
    "endToEndResponseTime",
    "intelligenceIndexTimePerTask",
    "medianEndToEndResponseTimeSeconds",
    "medianOutputTokensPerSecond",
    "medianReasoningTimeSeconds",
    "medianTimeToFirstAnswerTokenSeconds",
    "medianTimeToFirstTokenSeconds",
    "quartile25OutputTokensPerSecond",
    "quartile25TimeToFirstTokenSeconds",
    "quartile75OutputTokensPerSecond",
    "quartile75TimeToFirstTokenSeconds",
    "timeToFirstAnswerToken",
    "timeToFirstChunkVariance",
    "timescaleData",
})

# The record fields a DISPUTE-CAPABLE value can come from -- the variant
# axes' own sources. Everything else is canonical-first silent: a field
# outside this list never renders twice, so two published values for it
# are not a dispute (the canonical generation's value simply wins).
DISPUTE_CAPABLE = ("intelligenceIndex", "intelligenceIndexCostPerTask",
                   "gdpvalNormalized", "contextWindowTokens",
                   "price1mInputTokens", "price1mOutputTokens")


def _sleep(seconds: float) -> None:
    """The wait between re-read attempts, as a seam so tests can record the
    waits without sleeping."""
    time.sleep(seconds)


# AA no longer server-renders the full coding table it once did; what remains
# is a smaller set split across two arrays, currently thirteen rows. The floor
# only has to catch that set vanishing outright rather than shrinking, since
# AA is free to feature fewer runs without anything being broken.
CODING_ROW_FLOOR = 5

# The methodology page stamps the live index version in its headline, and its
# historical prose cites older generations WITHOUT the "Artificial Analysis"
# prefix -- so the regex anchors on the full brand prefix and the version-
# sorted MAXIMUM match is the live one. Never a plain string compare over the
# version: "4.10" would sort below "4.3".
VERSION_RE = re.compile(
    r"Artificial Analysis Intelligence Index v(\d+(?:\.\d+)*)")
# The pin compares at MAJOR.MINOR granularity: the pinned generation, not a
# point release within it.
PINNED_VERSION = tuple(int(p) for p in INDEX_VERSION.split("."))

# The per-evaluation costs are the index weights already applied, so they sum
# to the published total. A drift past build.py's SUM_TOLERANCE -- the same
# constant merge_captures uses to drop another generation's breakdown -- means
# AA changed what the breakdown contains, which is exactly the move that
# silently emptied two charts at v4.3.


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


def fetch_html(cached: str | None, url: str = URL) -> str:
    """The page text, from the pinned copy or a bounded set of live attempts.

    Each page carries its own bounded retry (issue #154): a transient answer is
    retried within a total of PAGE_ATTEMPTS attempts with linear backoff, and
    the refusal -- exhaustion or a non-retryable 4xx -- is the same one-line
    guarded exit as before the retry existed.
    """
    if cached:
        return pathlib.Path(cached).read_text(encoding="utf-8", errors="replace")
    for attempt in range(1, PAGE_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as r:
                return r.read().decode("utf-8", errors="replace")
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


def check_index_version(methodology_text: str) -> str | None:
    """Refuse a capture from an index version build.py was not written for.

    AA publishes the per-evaluation weights on its methodology page and NEVER
    in the payload, so a rebalance is undetectable from the data alone: the
    numbers stay well-formed and the page silently ships wrong costs. v4.2 did
    exactly that. Pinning the version is the only place this can be caught.

    The version string left the leaderboard payload (issue #220), so the pin
    reads the methodology page's own live version: the version-sorted MAXIMUM
    of the page's full-prefix citations. Its MAJOR.MINOR must equal
    INDEX_VERSION -- AA ships point releases (v4.3.2) within a generation
    without rebalancing. A page that names no version at all proves nothing
    and must NOT fail: the capture passes on absence, and says so on stderr.
    """
    versions = [tuple(int(p) for p in m.group(1).split("."))
                for m in VERSION_RE.finditer(methodology_text)]
    if not versions:
        # The absence note goes to BOTH streams: the refresh's capture step
        # tees only stdout into its log on a green run (stderr is cat'd on
        # the failure branch alone), and an operator must never mistake an
        # absence-passed capture for a pinned one.
        note = ("the methodology page named no Intelligence Index version; "
                "the pin check passed on absence and proves nothing -- if AA "
                f"moved the version, re-read {METHODOLOGY_URL} by hand")
        print(note, file=sys.stderr)
        print(note)
        return None
    found = max(versions)
    if found[:2] != PINNED_VERSION:
        found_text = ".".join(str(p) for p in found)
        sys.exit(
            f"AA is now on Intelligence Index v{found_text}, but build.py is "
            f"written against v{INDEX_VERSION}. Re-read {METHODOLOGY_URL} "
            "-- a version bump can rename a cost slug or rebalance the weights, "
            "and neither shows up in the data."
        )
    return ".".join(str(p) for p in found)


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


def check_cost_breakdown(models: list[dict]) -> tuple[int, list[str]]:
    """The cost breakdown still contains what build.py reads from it.

    Returns (models carrying a usable breakdown, models whose breakdown
    merge_captures DROPPED). The second is not an error: a detail-route
    breakdown that does not sum to the leaderboard's total is not that
    total's breakdown, so the merge leaves the leaderboard's number alone and
    the GDPval axis reads absent for that model until the routes converge
    (issue #200). When the merge dropped EVERY breakdown, the hour is a
    cross-generation window the merge is holding honest through, not a schema
    change: it is reported and returned as (0, dropped) -- main() records the
    state to the window marker, and the refresh publishes through the hour
    rather than refusing one the page recovers from on its own (issue #217).
    """
    checked = 0
    dropped: list[str] = []
    for m in models:
        outer = m.get("intelligenceIndexCostPerTask")
        if not isinstance(outer, dict):
            if isinstance(outer, (int, float)) and not isinstance(outer, bool):
                dropped.append(label(m))
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
        if dropped:
            # The merge dropped every breakdown, so nothing is left to check.
            # That is a window, not a schema change: AA's two routes are
            # serving two generations and the merge is refusing to decompose
            # one generation's total with another's breakdown. Reported and
            # returned, never refused -- during a window the refresh
            # publishes from the fresh route or leaves the page as-is, and
            # only a real schema change fails the capture (issue #217).
            print(
                f"every model's cost breakdown was dropped as another "
                f"generation's ({len(dropped)} model(s), first "
                f"{dropped[0]!r}) -- AA's leaderboard and detail routes are "
                "serving two generations at once; nothing is wrong with the "
                "schema, and the page will recover on its own once they "
                "converge"
            )
            return 0, dropped
        sys.exit("no model carries a cost breakdown -- schema changed")
    return checked, dropped


# The sidecar marker for the all-dropped window (issue #217): check_cost_
# breakdown's (0, dropped) return lands here as pipeline state the build
# layer reads. Beside the capture, like the stamp it complements.
COST_WINDOW_MARKER = ROOT / "data" / "cost-breakdown-window.txt"


def record_cost_window(priced: int, dropped: list[str],
                       path: pathlib.Path = COST_WINDOW_MARKER, *,
                       generations: int | None = None) -> None:
    """Record -- or clear -- the all-dropped window marker beside the capture.

    A window hour (priced == 0 with a non-empty `dropped`, issue #217) writes
    the file with ONE human-readable line -- count and first dropped slug,
    plus the in-run generation count when the caller supplies one (issue
    #223: the build layer's refusal reads it, so a window hour that empties
    an axis beyond the #217 exemption names the window instead of blaming a
    capture shape change). The line stays a git-history note first: nothing
    from the file is page input, build.py reads EXISTENCE plus this one
    integer, and no marker text is ever interpolated into the page. Any other
    hour removes the file (missing_ok=True), so a stale marker can never
    outlive its own hour. The function guarantees only what its arguments
    say: the schema sys.exit paths live in check_cost_breakdown, and a
    schema-broken run escapes there only because main() records the returned
    verdict -- call order, not a property of this function.
    """
    if priced == 0 and dropped:
        count = (f"; {generations} generation(s) observed in-run"
                 if generations is not None else "")
        path.write_text(
            f"every cost breakdown dropped as another generation's: "
            f"{len(dropped)} model(s), first {dropped[0]}{count}\n",
            encoding="utf-8")
        return
    path.unlink(missing_ok=True)


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


# The dispute layer (issues #208 and #211). Detection is IN-RUN -- the two
# spaced leaderboard looks are compared on their shared slugs over the
# leaderboard field universe, and a disagreement holds BOTH generations in
# the capture rather than picking one -- plus a CROSS-RUN presence
# look-back (cross_run_presence_merge below): the hourly refresh passes
# --cross-run-lookback, and a model present in the previous committed
# capture's firm set and absent from this run's own fetch, or the reverse,
# is merged and marked disputed the same way, because a flip that happens
# between runs is invisible to any number of in-run looks.


def _number(value):
    """The value when it is a published number, else None. AA writes absent
    fields as the string "$undefined" and unmeasured ones as null; neither
    is a number to plot."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def normalize_for_comparison(value):
    """One comparison form for a published value.

    The missing markers AA writes -- null, the empty string, the literal
    "$undefined" -- fold to ONE marker, so a look that stopped carrying a
    field is a fill and never a dispute; a cost object compares as the
    scalar of its own cost.total, so the leaderboard's flattened shape and
    the detail route's full object compare equal whenever they publish the
    same measurement. Everything else compares as itself, recursively.
    """
    if value is None or value == "" or value == "$undefined":
        return None
    if isinstance(value, dict):
        cost = value.get("cost")
        if isinstance(cost, dict) and "total" in cost:
            return normalize_for_comparison(cost.get("total"))
        return {k: normalize_for_comparison(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalize_for_comparison(v) for v in value]
    return value


def generation_key(records: list[dict], universe: set[str]) -> str:
    """One corpus generation's fingerprint: a 16-hex sha256 prefix over the
    slug-sorted records normalized on `universe - NEVER_RED_FIELDS`.

    Equal keys mean every shared field carries the same published value,
    so grouping the reads by key is the dispute test; the speed and latency
    family is excluded first, because it moves every hour by design and
    never means a generation. The key is order-stable: records are sorted
    by slug and the field dict is built in sorted order, so two runs that
    read the same bytes compute the same key.
    """
    fields = sorted(universe - NEVER_RED_FIELDS)
    normalized = [
        {f: normalize_for_comparison(rec.get(f)) for f in fields}
        for rec in sorted((r for r in records if isinstance(r, dict)),
                          key=lambda r: str(r.get("slug", "")))
    ]
    blob = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def leaderboard_universe(looks: list[list[dict]]) -> set[str]:
    """Every field carried by at least one leaderboard look -- the field set
    generation comparisons run on. The detail-only fields (parameters,
    licence, release date, the per-evaluation cost breakdown) are absent by
    construction: they are computed from the leaderboard reads alone.
    """
    universe: set[str] = set()
    for look in looks:
        for rec in look:
            if isinstance(rec, dict):
                universe.update(rec)
    return universe


def _cost_total(record):
    """The record's measured cost total in either published shape: the bare
    scalar AA flattened the leaderboard to, or the object's cost.total."""
    outer = record.get("intelligenceIndexCostPerTask")
    total = _number(outer)
    if total is None and isinstance(outer, dict):
        cost = outer.get("cost")
        if isinstance(cost, dict):
            total = _number(cost.get("total"))
    return total


def variant_fields(record) -> dict:
    """The per-generation flat map the page renders from: {"ii", "cost",
    "gdpval", "gdpvalCost", "ctx", "pin", "pout"}, absent keys absent.

    gdpvalCost is recovered from THIS record's own breakdown and is absent
    when that breakdown does not decompose its own total -- never supplied
    from another generation's parts, which is what makes a disputed axis
    honest: each variant carries exactly what its generation published.
    """
    fields: dict = {}
    ii = _number(record.get("intelligenceIndex"))
    if ii is not None:
        fields["ii"] = ii
    total = _cost_total(record)
    if total is not None:
        fields["cost"] = total
    gdp = _number(record.get("gdpvalNormalized"))
    if gdp is not None:
        fields["gdpval"] = gdp
    outer = record.get("intelligenceIndexCostPerTask")
    if isinstance(outer, dict) and breakdown_matches_total(outer):
        gdpval_cost = evaluation_cost_per_task(record, GDPVAL_SLUG,
                                               GDPVAL_INDEX_WEIGHT)
        if gdpval_cost is not None:
            fields["gdpvalCost"] = gdpval_cost
    ctx = _number(record.get("contextWindowTokens"))
    if ctx is not None:
        fields["ctx"] = ctx
    pin = _number(record.get("price1mInputTokens"))
    if pin is not None:
        fields["pin"] = pin
    pout = _number(record.get("price1mOutputTokens"))
    if pout is not None:
        fields["pout"] = pout
    return fields


def _dispute_columns(record):
    """The record's dispute-capable values, normalized, in DISPUTE_CAPABLE
    order -- one column per field for the pairwise conflict test."""
    return [normalize_for_comparison(record.get(f)) for f in DISPUTE_CAPABLE]


def _conflicting(values) -> bool:
    """Whether two PUBLISHED values in one field's column differ.

    The missing marker never conflicts: absent/null/""/"$undefined" fold to
    one marker, so a look that stopped carrying a field is a fill, and a
    model a look did not price is not a dispute with one that did.
    """
    for i, a in enumerate(values):
        if a is None:
            continue
        for b in values[i + 1:]:
            if b is not None and a != b:
                return True
    return False


def cross_generation_merge(corpora: list[list[dict]]) -> list[dict]:
    """Union the per-generation corpora by slug and hold every generation.

    The corpora arrive in any order; canonical order is ASCENDING
    generation_key, so corpora with differing keys give identical bytes
    whichever look a run read first (corpora ranking equal keep input
    order -- the one shape a disputed run cannot reach, since presence
    and value disagreements both imply differing keys). A record's plain
    fields are the first CARRYING variant's --
    the canonical generation's published value where that generation
    carries the record, filled only where that record lacks the field (a
    missing marker is a fill, never a winner).
    When any record is disputed -- by a value conflict on its
    dispute-capable fields, or by PRESENCE, one generation carrying the
    model and another not (issue #211) -- EVERY record gets genVariants:
    one entry per ranked corpus, padded to the run's generation count
    with the empty map at every position whose corpus does not carry the
    record (`{}` = this generation does not carry this model), whose
    fields are that generation's own values -- so the page's dispute
    layer can hold the whole run red; otherwise the corpus is exactly
    the single-generation union and no genVariants key exists.

    Identity/flag fields and every field outside DISPUTE_CAPABLE are
    never disputed: they render the canonical generation's value, silent.
    """
    universe = leaderboard_universe(corpora)
    ranked = sorted(corpora, key=lambda c: generation_key(c, universe))
    by_slug = [{m["slug"]: m for m in corpus if isinstance(m.get("slug"), str)}
               for corpus in ranked]
    slugs = sorted(set().union(*by_slug))
    rows = []
    disputed = False
    for slug in slugs:
        present = [(i, by_slug[i][slug]) for i in range(len(ranked))
                   if slug in by_slug[i]]
        plain = dict(present[0][1])
        for _, rec in present[1:]:
            for k, v in rec.items():
                if ((k not in plain or normalize_for_comparison(plain[k]) is None)
                        and normalize_for_comparison(v) is not None):
                    plain[k] = v
        columns: list = []
        if len(present) > 1:
            columns = list(zip(*[_dispute_columns(rec) for _, rec in present]))
        record_disputed = ((len(present) < len(ranked))
                           or (len(present) > 1
                               and any(_conflicting(list(col))
                                       for col in columns)))
        disputed = disputed or record_disputed
        rows.append((plain, [by_slug[i][slug] if slug in by_slug[i] else None
                             for i in range(len(ranked))]))
    if not disputed:
        return [plain for plain, _ in rows]
    return [dict(plain, genVariants=[variant_fields(rec) if rec is not None
                                     else {} for rec in recs])
            for plain, recs in rows]


# The synthetic key a record merged from the PREVIOUS committed capture
# carries (issue #211's cross-run half): this run's own fetch did not serve
# the model; the record is the previous generation's, held across the run
# boundary. The next run strips it when it reads its own look-back -- the
# model's presence in that file is dispute state, not serving evidence --
# and that is what lets a stable retirement settle within one further hour:
# a look-back that pinned a model disputed forever would be wrong.
CROSS_RUN_KEY = "crossRunMerged"


class CrossRun(typing.NamedTuple):
    """The cross-run presence layer's summary for one capture (issue #211):
    the slugs each presence direction caught, sorted. `dropped` -- the
    previous capture's firm set carries them, this run's fetch does not;
    merged back and marked. `readded` -- this run serves them, the firm set
    lacks them; kept, disputed by the empty previous-generation slot."""

    dropped: list
    readded: list


def cross_run_presence_merge(models, prev_records, run_corpora):
    """Issue #211's cross-run half (Overseer ruling, 2026-10-06, on the
    reopened issue): a model present in the previous committed capture and
    absent from this run's own fetch -- or the reverse -- is MERGED and
    marked disputed, never quietly dropped or re-added, so the published
    set does not flip hour to hour. Presence-only: the previous corpus
    participates only through the diff slugs, so a shared model raises no
    cross-run value dispute and takes no previous-generation slot.

    A record the previous capture held only by CROSS_RUN_KEY is dispute
    state, not serving evidence: it neither merges nor disputes again, and
    the model settles out the first hour AA still does not serve it --
    the settling bound one-capture-back demands.

    The previous capture's records are read canonically: genVariants and
    the marker stripped, the plain fields being that generation's view.
    `run_corpora` are the run's own per-generation corpora in the order
    the in-run merge ranked them; the previous generation's slot is
    positioned among them by ascending generation_key over the joint
    field universe.
    """
    canonical: dict[str, dict] = {}
    firm: set[str] = set()
    for rec in prev_records:
        if not isinstance(rec, dict):
            continue
        slug = rec.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        canonical[slug] = {k: v for k, v in rec.items()
                           if k not in ("genVariants", CROSS_RUN_KEY)}
        if not rec.get(CROSS_RUN_KEY):
            firm.add(slug)

    current_slugs = {m.get("slug") for m in models}
    dropped = sorted(firm - current_slugs)
    readded = sorted(current_slugs - firm)
    # An unusable previous capture holds no presence evidence: an empty
    # file, or one whose records all lack a usable slug or all carry the
    # marker, would read every slug as a readd against it -- the wrong
    # reading of a file the layer cannot key, not a dispute to hold.
    if not prev_records or not firm or not (dropped or readded):
        return models, CrossRun([], [])

    prev_corpus = [canonical[slug] for slug in dropped]
    universe = leaderboard_universe(run_corpora + [prev_corpus])
    run_keys = [generation_key(c, universe) for c in run_corpora]
    prev_key = generation_key(prev_corpus, universe)
    # The previous generation's rank among the run's own: how many run
    # corpora rank before it. A key tie with a run corpus is an identical
    # generation, and either position renders identically.
    prev_position = sum(1 for k in run_keys if k < prev_key)

    readded_set = set(readded)
    out = []
    for m in models:
        if m.get("slug") not in readded_set:
            out.append(m)
            continue
        m = dict(m)
        run_slots = list(m.get("genVariants") or []) or [variant_fields(m)]
        m["genVariants"] = (list(run_slots[:prev_position]) + [{}]
                            + list(run_slots[prev_position:]))
        out.append(m)
    for slug in dropped:
        base = dict(canonical[slug])
        base[CROSS_RUN_KEY] = True
        base["genVariants"] = ([{}] * prev_position
                               + [variant_fields(canonical[slug])]
                               + [{}] * (len(run_corpora) - prev_position))
        out.append(base)
    return out, CrossRun(dropped, readded)


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


class Capture(typing.NamedTuple):
    """One capture's merged model corpus, and the reads it was stitched from.

    `host` and `version` are what the capture log names: which model detail
    page filled the gaps, and which Intelligence Index the costs belong to.
    `version` is None when the methodology page named no index version at
    all -- the pin passed on absence (issue #220), and the log says so
    rather than interpolating a version where none was found.
    `generations` counts the distinct generation fingerprints the run
    observed across its reads, and `disputed` says the written corpus
    carries genVariants -- the looks disagreed on a published value.
    """

    models: list
    host: str
    version: str | None
    generations: int
    disputed: bool
    # The cross-run presence layer's summary (issue #211); empty when the
    # look-back was not engaged or found no presence diff.
    cross_run: CrossRun = CrossRun([], [])


def capture(cached_base: str | None, cached_detail: str | None,
            cached_methodology: str | None,
            prev_records: list | None = None) -> Capture:
    """Fetch the routes fresh, parse each from its own bytes, and merge.

    The methodology page is read FIRST and the version pin runs on it before
    anything else is fetched (issue #220): a bumped index fails the capture
    without spending the other page reads.

    detail_host_slug is computed from THIS leaderboard's own rows: the detail
    page is chosen for what its page excludes, so the corpus must never be
    paired with a host picked from a different read. The merge is
    merge_captures', and its rule is the whole contract: the leaderboard's
    value wins wherever both routes carry a field, and the detail route fills
    only what the leaderboard omits (issue #200).

    Issue #208 adds the second, spaced leaderboard look. The DISPUTE DECISION
    compares THE LOOKS on their shared slugs over the leaderboard universe:
    a run whose looks agree is one generation and merges exactly as before,
    byte for byte. A run whose looks disagree holds both -- each generation's
    corpus is that generation's own look, widened by the detail page only
    when the detail corpus IS that generation, and stitched by
    cross_generation_merge. The detail route is ONE generation's snapshot:
    it never raises a dispute by itself (a stale detail corpus is the known,
    precedence-handled state of issue #200) and it fills the generation it
    belongs to.

    Issue #211 adds the cross-run look-back: when `prev_records` is passed,
    a model present in the previous committed capture's firm set and absent
    from this run's fetch -- or the reverse -- is merged and marked
    disputed on top of whatever the in-run layer held; see
    cross_run_presence_merge.
    """
    version = check_index_version(
        fetch_html(cached_methodology, METHODOLOGY_URL))
    base_text = fetch_html(cached_base)
    payload = flight_payload(base_text)
    look1 = richest_models_array(payload)

    host = detail_host_slug(look1)
    detail = richest_models_array(
        flight_payload(fetch_html(cached_detail, MODEL_DETAIL_URL.format(slug=host))))

    _sleep(DISPUTE_LOOK_SPACING_SECONDS)
    look2 = richest_models_array(flight_payload(fetch_html(cached_base)))

    universe = leaderboard_universe([look1, look2])
    slugs = [
        {m.get("slug") for m in look if isinstance(m.get("slug"), str)}
        for look in (look1, look2)]
    shared = slugs[0] & slugs[1]

    def keyed(records, keep):
        """generation_key over the records whose slug is in `keep` -- the
        structural restriction that makes two reads comparable: the detail
        page omits exactly one model (its own host). A model AA added or
        retired between the looks is an inconsistency between the
        generations (issue #211): the union keeps the model and marks it
        disputed -- a presence dispute."""
        return generation_key(
            [r for r in records
             if isinstance(r.get("slug"), str) and r.get("slug") in keep],
            universe)

    look1_key = keyed(look1, shared)
    look2_key = keyed(look2, shared)

    detail_slugs = {m.get("slug") for m in detail
                    if isinstance(m.get("slug"), str)}

    def same_generation(look, look_slugs) -> bool:
        """Whether the detail corpus IS this look's generation, compared on
        the slugs both reads carry."""
        with_detail = look_slugs & detail_slugs
        return keyed(look, with_detail) == keyed(detail, with_detail)

    run_corpora: list[list[dict]]
    if look1_key == look2_key and slugs[0] == slugs[1]:
        # One leaderboard generation: today's merge, byte for byte, with
        # the detail route filling what the leaderboard omits whatever
        # generation the detail corpus itself is (issue #200).
        models = merge_captures(look1, detail)
        disputed = False
        generations = 1 + (0 if same_generation(look1, slugs[0]) else 1)
        run_corpora = [models]
    else:
        # The looks disagree on a published value, or on WHICH SLUGS the
        # generation carries (issue #211): a model present in one look and
        # absent from the other is an inconsistency between the two
        # generations, not a corpus union to take quietly.
        #
        # Both matches can hold at once when the looks' disagreement sits
        # entirely on slugs the detail route omits (its own host), so "D
        # matches both" is reachable, and both corpora then take the fill
        # -- gap-only either way, merge_captures precedence keeping each
        # look's own values.
        matches1 = same_generation(look1, slugs[0])
        matches2 = same_generation(look2, slugs[1])
        corpora = [
            merge_captures(look1, detail) if matches1 else look1,
            merge_captures(look2, detail) if matches2 else look2,
        ]
        models = cross_generation_merge(corpora)
        disputed = any("genVariants" in m for m in models)
        generations = 2 + (0 if matches1 or matches2 else 1)
        run_corpora = corpora

    cross_run = CrossRun([], [])
    if prev_records:
        models, cross_run = cross_run_presence_merge(models, prev_records,
                                                     run_corpora)
        disputed = disputed or bool(cross_run.dropped or cross_run.readded)
    return Capture(models, host, version, generations, disputed, cross_run)


def load_previous_capture() -> list | None:
    """The previous committed capture, read before the fetch overwrites it.

    --cross-run-lookback's source. The refresh checks main out, so the
    working copy IS the last committed capture at fetch time -- read here,
    never from a second network source. A missing file is no look-back
    (the first capture ever); a malformed one refuses: it is our own
    committed artifact, and a parse failure is repo damage, not an AA
    event the hour should paper over.
    """
    if not OUT.exists():
        return None
    try:
        records = json.loads(OUT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.exit(f"{OUT}: the previous capture does not read back as JSON "
                 f"({exc}) -- the cross-run look-back refuses to guess; "
                 "repair or drop the file, then re-run")
    if not isinstance(records, list):
        sys.exit(f"{OUT}: the previous capture is not a JSON array -- "
                 "schema changed")
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="use a cached copy of the leaderboard HTML")
    ap.add_argument("--detail-html", help="use a cached copy of a model detail page")
    ap.add_argument("--methodology-html",
                    help="use a cached copy of the methodology page HTML")
    ap.add_argument("--agents-html", help="use a cached copy of the coding-agents HTML")
    ap.add_argument("--cross-run-lookback", action="store_true",
                    help="hold a slug-set diff against the previous "
                         "committed capture as a cross-run presence "
                         "dispute (issue #211); pass it where the working "
                         "copy of data/aa-raw-models.json IS that capture "
                         "-- the hourly refresh")
    args = ap.parse_args()

    prev_records = (load_previous_capture()
                    if args.cross_run_lookback else None)
    captured = capture(args.html, args.detail_html, args.methodology_html,
                       prev_records)
    models = captured.models
    priced, dropped = check_cost_breakdown(models)
    record_cost_window(priced, dropped, generations=captured.generations)
    agents_text = fetch_html(args.agents_html, AGENTS_URL)
    agents = coding_agent_rows(flight_payload(agents_text))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(OUT, json.dumps(models, indent=1))
    write_atomic(AGENTS_OUT, json.dumps(agents, indent=1))
    STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    scored = sum(1 for m in models if isinstance(m.get("intelligenceIndex"), (int, float)))
    if captured.version is not None:
        version_phrase = f"a v{captured.version} cost breakdown"
    else:
        version_phrase = ("a cost breakdown whose index version the "
                          "methodology page did not name")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {scored} with an "
          f"intelligence index, {priced} with {version_phrase} "
          f"(gaps filled from /models/{captured.host}; the leaderboard's own "
          "value wins wherever both routes carry the field)")
    # The run's one-line generation summary (issue #208): how many distinct
    # generations the three reads observed, and how many records the
    # dispute layer holds. The quiet hour prints the 1 / 0 shape the
    # capture-log test pins.
    disputed = sum(1 for m in models if "genVariants" in m)
    print(f"{captured.generations} generation(s) observed in-run; "
          f"{disputed} models carry disputed values")
    cross_run = captured.cross_run
    if cross_run.dropped or cross_run.readded:
        def names(slugs):
            return ", ".join(slugs[:10]) + (", ..." if len(slugs) > 10
                                            else "")
        print(f"cross-run presence: {len(cross_run.dropped)} model(s) "
              f"merged from the previous capture "
              f"({names(cross_run.dropped)}); "
              f"{len(cross_run.readded)} re-added since it "
              f"({names(cross_run.readded)})")
    if dropped:
        # Named, not counted: each is a model whose GDPval cost renders absent
        # until AA's two routes agree, and a count alone does not say which.
        print(f"{len(dropped)} model(s) carry the leaderboard's measured cost "
              "but no cost breakdown to decompose it (the detail route's "
              "breakdown is another generation's), so their GDPval cost renders "
              "absent until the routes converge: "
              + ", ".join(dropped[:10])
              + (", ..." if len(dropped) > 10 else ""))
    print(f"wrote {AGENTS_OUT.relative_to(ROOT)}: {len(agents)} agent+model rows "
          f"with a paired index score and cost per task")


if __name__ == "__main__":
    main()
