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

Usage:  python3 scripts/fetch_aa.py [--html F] [--detail-html F] [--agents-html F]
"""
from __future__ import annotations

import argparse
import datetime as dt
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
    GDPVAL_SLUG, INDEX_VERSION, merge_captures,
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
# build, commit, publish. Worst case for the capture itself is three page
# fetches (leaderboard, detail, coding agents), each bounded at
# PAGE_ATTEMPTS * FETCH_TIMEOUT_SECONDS plus its backoff sleeps
# (3 * 25 + 15 = 90 s), so at most 270 s -- and that only if every fetch
# succeeds slowly; transport exhaustion SHORT-CIRCUITS, fetch_html refuses and
# the process exits inside one page bound. The fetch terms are the per-attempt
# BOUND, not a promise: a slow-drip body can outlast a single socket timeout,
# and the job's headroom is what absorbs the difference.
PAGE_ATTEMPTS = 3
PAGE_BACKOFF_SECONDS = 5


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
    """

    models: list
    host: str
    version: str


def capture(cached_base: str | None, cached_detail: str | None) -> Capture:
    """Fetch both routes fresh, parse each from its own bytes, and merge.

    detail_host_slug is computed from THIS leaderboard's own rows: the detail
    page is chosen for what its page excludes, so the corpus must never be
    paired with a host picked from a different read. The merge is
    merge_captures', and its rule is the whole contract: the leaderboard's
    value wins wherever both routes carry a field, and the detail route fills
    only what the leaderboard omits (issue #200).
    """
    base_text = fetch_html(cached_base)
    payload = flight_payload(base_text)
    version = check_index_version(payload)
    base = richest_models_array(payload)

    host = detail_host_slug(base)
    detail = richest_models_array(
        flight_payload(fetch_html(cached_detail, MODEL_DETAIL_URL.format(slug=host))))
    return Capture(merge_captures(base, detail), host, version)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="use a cached copy of the leaderboard HTML")
    ap.add_argument("--detail-html", help="use a cached copy of a model detail page")
    ap.add_argument("--agents-html", help="use a cached copy of the coding-agents HTML")
    args = ap.parse_args()

    captured = capture(args.html, args.detail_html)
    models = captured.models
    priced = check_cost_breakdown(models)
    agents_text = fetch_html(args.agents_html, AGENTS_URL)
    agents = coding_agent_rows(flight_payload(agents_text))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(OUT, json.dumps(models, indent=1))
    write_atomic(AGENTS_OUT, json.dumps(agents, indent=1))
    STAMP.write_text(dt.date.today().isoformat() + "\n", encoding="utf-8")

    scored = sum(1 for m in models if isinstance(m.get("intelligenceIndex"), (int, float)))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {scored} with an "
          f"intelligence index, {priced} with a v{captured.version} cost breakdown "
          f"(gaps filled from /models/{captured.host}; the leaderboard's own "
          "value wins wherever both routes carry the field)")
    print(f"wrote {AGENTS_OUT.relative_to(ROOT)}: {len(agents)} agent+model rows "
          f"with a paired index score and cost per task")


if __name__ == "__main__":
    main()
