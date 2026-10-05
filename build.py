#!/usr/bin/env python3
"""Build out/frontier-models.html from data/aa-raw-models.json.

Single deliverable: AA's Coding Agent, Intelligence and GDPval-AA indices against their
matched measured cost per task, plus total parameter count against Intelligence
Index, sourced exclusively from artificialanalysis.ai.

Usage:  python3 build.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re

# The page's formatting rules live beside the build that renders them into
# the static table bodies, not inside it: build.py is one line-budgeted HTML
# emitter, and these mirrors are the page's own, shared shape (#97).
from page_format import (EM_DASH, fmt_cost, fmt_ctx, fmt_params, js_number,
                         js_to_fixed, show_text, weights_text)

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "data" / "aa-raw-models.json"
AGENTS_RAW = ROOT / "data" / "aa-raw-coding-agents.json"
OUT = ROOT / "out" / "frontier-models.html"

# The AA Intelligence Index version this file's weights and field names are
# written against. AA bumps it every few weeks and a bump can rename or drop a
# cost-breakdown slug -- v4.3 replaced tau3-banking with automationbench-aa and
# Terminal-Bench v2.1 with v4.0. The weights are published on AA's methodology
# page and are NOT in the payload, so nothing can detect a rebalance for us;
# fetch_aa.py refuses a version this file was not written against instead.
INDEX_VERSION = "4.3"

# AA Intelligence Index v4.3 component evals, as listed on the source site.
INDEX_EVALS = [
    "AA-Briefcase", "GDPval-AA v2", "AutomationBench-AA", "Terminal-Bench v4.0",
    "SciCode", "AA-Omniscience", "GDP.pdf", "AA-LCR v1.1",
    "Humanity's Last Exam", "CritPt",
]

METRIC_ORDER = ("coding", "intelligence", "agentic")

# Every axis is now a score and a cost AA measured on the same run, and each
# comes from the source that publishes them together:
#
#   coding        the Coding Agent Index (data/aa-raw-coding-agents.json), whose
#                 rows carry indexScore and mean.costUsd on ONE record. Its unit
#                 is an agent+model+harness combination, not a bare model.
#   intelligence  the model leaderboard's intelligenceIndex against its own
#                 measured intelligenceIndexCostPerTask.cost.total.
#   agentic       GDPval-AA v2 -- gdpvalNormalized against the cost AA measured
#                 running it, recovered from the weighted breakdown below.
#
# The leaderboard's `codingIndex` and `agenticIndex` fields are deliberately NOT
# used: AA scores both from Terminal-Bench v2.1 and tau3-banking, whose per-task
# cost it stopped publishing in v4.3. A score with no cost cannot go on a
# cost axis, and estimating the missing half is off the table.
GDPVAL_SLUG = "gdpval-aa"
# GDPval-AA v2's weight inside Intelligence Index v4.3. AA reports each eval's
# task cost with this already applied; dividing it back out recovers the
# evaluation's own measured cost per task.
GDPVAL_INDEX_WEIGHT = 0.10


# AA encodes the effort knob in the model name; there is no field for it. The
# trailing parenthetical is one of four things -- a bare effort level "(high)",
# an effort clause inside a config list "(Adaptive Reasoning, Max Effort)",
# AA's dict-repr display label "('reasoning_effort': 'max')", or something
# that is not effort at all "(Reasoning)", "(Non-reasoning)", "(Jan '25)".
# Only the effort component is stripped; the rest identifies a genuinely
# different configuration and must survive.
EFFORT = re.compile(r"^(minimal|low|medium|high|xhigh|max)(\s+effort)?$", re.I)
# The dict-repr form AA's own displayLabel carries on some agent runs --
# "Codex - GPT-6 Luna (max) ({'reasoning_effort': 'max'})". The inner value
# is the same effort word the other two shapes carry; a typo'd key or a
# non-effort value must NOT match (issue #85).
EFFORT_DICT = re.compile(
    r"^\{\s*'reasoning_effort'\s*:\s*"
    r"'(minimal|low|medium|high|xhigh|max)'\s*\}$", re.I)


def _effort_scan(name):
    r"""-> (segments, found): one linear scan over `name`'s groups.

    The next "(" that has a ")" after it opens a group, its content is split
    on commas, effort words are pulled out and everything else is kept. A "("
    with no ")" after it can never open a group, so the scan stops there and
    the rest is kept verbatim -- which is what keeps a pathological name
    (issue #47: a capture-crafted name of ~80k parens cost ~54 s of regex
    backtracking) linear instead of quadratic in the parens' count.

    `segments` is the name re-rendered without the effort words: the leading
    text, then for each group either its kept remainder with the one-space
    lead-in a kept group renders back with, or nothing when the group was
    all-effort and takes its whitespace with it (same as the regex's \s*
    prefix). The scan appends the tail unconditionally, so `segments[0]`
    always exists. `found` carries every effort word in order of appearance.
    """
    found = []
    out = []
    i = 0
    while True:
        p = name.find("(", i)
        if p == -1:
            break
        close = name.find(")", p + 1)
        if close == -1:
            break
        # The reader between the previous match and the group: one space is
        # what a kept group renders back with, and an all-effort group takes
        # the whitespace with it (same as the regex's \s* prefix).
        lead = p
        while lead > i and name[lead - 1].isspace():
            lead -= 1
        out.append(name[i:lead])
        kept = []
        for part in name[p + 1:close].split(","):
            part = part.strip()
            dict_effort = EFFORT_DICT.match(part)
            if EFFORT.match(part):
                found.append(part)
            elif dict_effort:
                found.append(dict_effort.group(1))
            else:
                kept.append(part)
        if kept:
            out.append(" (" + ", ".join(kept) + ")")
        i = close + 1
    out.append(name[i:])
    return out, found


def split_effort(name):
    """-> (base name without the effort knob, effort label or None)"""
    segments, found = _effort_scan(name)
    base = "".join(segments).strip()
    label = found[0].lower().replace(" effort", "") if found else None
    return base, label


def display_label(name):
    """The compact chart label: the name with the effort knob moved forward.

    Identifies an effort variant within a 34-character chart cap (#85): the
    effort groups drop out of place and the FIRST effort re-attaches
    immediately after the leading text segment -- BEFORE any kept groups, so
    the one word that distinguishes effort variants of one model survives a
    truncation -- and the non-effort groups keep their place after it.
    """
    segments, found = _effort_scan(name)
    eff = found[0].lower().replace(" effort", "") if found else None
    label = segments[0] + (f" ({eff})" if eff else "") + "".join(segments[1:])
    return label.strip()


def display_name(name):
    """The reader-facing full name: AA's dict-form effort text decoded (#88).

    #85 moved the effort knob out of the chart labels; the dict-repr group
    AA puts on some agent runs still reached every full-name sink -- the
    payload's `name` field the tooltip, popup, table, aria-labels, search and
    the copy exports read, and diff_aa.py's report lines. The rule, per
    group, per comma-part:

    - a plain effort part ("(max)", "(Max Effort)") stays verbatim;
    - a dict-form effort part DROPS when its effort word already appears as a
      plain effort part anywhere in the name -- a decision over the raw
      name's plain parts only, so it is order-independent by design: the
      group cleans the same on either side of its plain twin;
    - otherwise the dict part REWRITES to its bare effort word;
    - anything else survives verbatim, case included.

    Group and whitespace rules are _effort_scan's (a kept group renders with
    a one-space lead, an emptied group takes its whitespace with it, a "("
    with no ")" after it stops the scan and keeps the rest verbatim), and the
    walk stays #47-linear. Case-insensitive like EFFORT/EFFORT_DICT, on both
    the dict key and the effort word the drop compares.
    """
    # Pass 1: the effort words the name carries as PLAIN parts, normalized
    # the way split_effort normalizes them ("Max Effort" and "max" are one
    # word). The drop test reads all of them, wherever they sit, so a dict
    # group before its plain twin drops all the same.
    plain = set()
    i = 0
    while True:
        p = name.find("(", i)
        if p == -1:
            break
        close = name.find(")", p + 1)
        if close == -1:
            break
        for part in name[p + 1:close].split(","):
            part = part.strip()
            if EFFORT.match(part):
                plain.add(part.lower().replace(" effort", ""))
        i = close + 1
    # Pass 2: render. Two linear walks, never a regex over the whole name --
    # the shape that cost issue #47 its ~54 s.
    out = []
    i = 0
    while True:
        p = name.find("(", i)
        if p == -1:
            break
        close = name.find(")", p + 1)
        if close == -1:
            break
        lead = p
        while lead > i and name[lead - 1].isspace():
            lead -= 1
        out.append(name[i:lead])
        kept = []
        for part in name[p + 1:close].split(","):
            part = part.strip()
            dict_effort = EFFORT_DICT.match(part)
            if EFFORT.match(part) or dict_effort is None:
                kept.append(part)
            elif dict_effort.group(1).lower() in plain:
                pass  # the plain part already says it; the dict echo drops
            else:
                kept.append(dict_effort.group(1))
        if kept:
            out.append(" (" + ", ".join(kept) + ")")
        i = close + 1
    out.append(name[i:])
    return "".join(out).strip()


def num(v):
    return v if isinstance(v, (int, float)) else None


def cost_per_task(m):
    """AA's measured cost per task, USD.

    Two shapes: the object intelligenceIndexCostPerTask.cost.total from the
    detail route, and -- since AA flattened the leaderboard -- a bare number
    that IS the total. The merge restores the object for every model the
    detail route describes; a bare number is what the one model it cannot
    describe (the detail host) is left with, and what a model whose stale
    breakdown was dropped under the leaderboard's newer total is left with
    (merge_captures: that model's GDPval cost renders absent until the routes
    converge, but its measured total is the fresh one and still plots).
    """
    outer = m.get("intelligenceIndexCostPerTask")
    if isinstance(outer, (int, float)):
        return outer
    if not isinstance(outer, dict):
        return None
    inner = outer.get("cost")
    if not isinstance(inner, dict):
        return None
    return num(inner.get("total"))


def evaluation_cost_per_task(m, slug, index_weight):
    """One evaluation's own measured cost per task, in USD.

    AA reports `weightedCostPerTask` with the evaluation's Intelligence Index
    weight already multiplied in -- the per-eval figures sum exactly to
    `cost.total`. Dividing the weight back out recovers what AA actually spent
    per task on that evaluation.
    """
    outer = m.get("intelligenceIndexCostPerTask")
    evaluations = outer.get("evaluations") if isinstance(outer, dict) else None
    if not isinstance(evaluations, list):
        return None
    for e in evaluations:
        if isinstance(e, dict) and e.get("slug") == slug:
            weighted = num(e.get("weightedCostPerTask"))
            return None if weighted is None else weighted / index_weight
    return None


def capability_cost_per_task(m, metric):
    """AA's measured average task cost for one displayed axis of a model row."""
    if metric == "intelligence":
        return cost_per_task(m)
    if metric == "agentic":
        return evaluation_cost_per_task(m, GDPVAL_SLUG, GDPVAL_INDEX_WEIGHT)
    if metric == "coding":
        # Model rows have no coding pair; coding lives on the agent capture.
        return None
    raise ValueError(f"unknown metric: {metric}")


def capability_score(m, metric):
    """The score AA publishes for one axis, on a 0-100 scale.

    intelligenceIndex already is; gdpvalNormalized is a 0-1 fraction.
    """
    if metric == "intelligence":
        return num(m.get("intelligenceIndex"))
    if metric == "agentic":
        raw = num(m.get("gdpvalNormalized"))
        return None if raw is None else raw * 100
    if metric == "coding":
        return None
    raise ValueError(f"unknown metric: {metric}")


def metric_record(m, metric):
    score = capability_score(m, metric)
    cost = capability_cost_per_task(m, metric)
    if score is None or cost is None or cost <= 0:
        return None
    return {"score": round(score, 2), "cost": round(cost, 4)}


def build_rows(models):
    """Every model row the page's axes and table render, sorted for display."""
    rows = []
    for m in models:
        metrics = {metric: metric_record(m, metric) for metric in METRIC_ORDER}
        if not any(metrics.values()):
            continue
        # The leaderboard ships `name`; `shortName` is its own compact label
        # and covers the one model the gap-fill detail route cannot describe
        # -- the host page the corpus came from.
        label = m.get("name") or m.get("shortName") or ""
        base, eff = split_effort(label)
        intelligence = metrics["intelligence"]
        # Renamed by AA: totalParameters -> parameters. Same numbers -- every
        # model carrying both across the rename agreed exactly.
        parameters = num(m.get("parameters"))
        row = {
            # The reader-facing name (#88): AA's dict-form effort text is
            # decoded out of it. The RAW label survives only in the capture;
            # base/eff/label below keep their raw-label semantics.
            "name": display_name(label),
            "base": base,
            "eff": eff,
            # The compact chart label (#85): the effort word re-attached right
            # after the model name, so effort variants of one model stay
            # distinguishable under the page's 34-character chart cap.
            "label": display_label(label),
            # Which capture the row came from. Model rows carry the
            # intelligence, agentic and parameter axes; agent rows carry
            # coding. Neither universe has the other's columns, and the page
            # renders an absent column as an em-dash, not a blank.
            "kind": "model",
            "agent": None,
            "creator": m.get("modelCreatorName") or "",
            # AA dropped modelCreatorCountry from every route. Nothing on the
            # page reads it; the key stays so the row shape is uniform.
            "country": "",
            # Compatibility aliases used by diff_aa.py and historical callers.
            "ii": intelligence["score"] if intelligence else None,
            "cost": intelligence["cost"] if intelligence else None,
            "metrics": metrics,
            "params": parameters if parameters is not None and parameters > 0 else None,
            "open": bool(m.get("isOpenWeights")),
            "dep": bool(m.get("deprecated")),
            "est": bool(m.get("intelligenceIndexIsEstimated")),
            "reas": bool(m.get("isReasoning")),
            "lic": m.get("licenseName") if isinstance(m.get("licenseName"), str) else None,
            "ctx": num(m.get("contextWindowTokens")),
            "rel": m.get("releaseDate") if isinstance(m.get("releaseDate"), str) else None,
            "tps": round(m["medianOutputTokensPerSecond"], 1) if num(m.get("medianOutputTokensPerSecond")) else None,
            "secs": round(m["intelligenceIndexTimePerTask"], 1) if num(m.get("intelligenceIndexTimePerTask")) else None,
            "pin": num(m.get("price1mInputTokens")),
            "pout": num(m.get("price1mOutputTokens")),
        }
        rows.append(row)
    rows.sort(key=lambda r: (
        -(r["ii"] if r["ii"] is not None else -1),
        r["cost"] if r["cost"] is not None else float("inf"),
        r["name"],
    ))
    return rows


def build_agent_rows(agents, models):
    """Rows for the Coding Agent Index capture.

    Unlike the leaderboard, this source pairs the score and the cost itself --
    `indexScore` and `mean.costUsd` sit on one record, measured on one run --
    so there is no weight to undo and no way for the two halves to drift apart.
    """
    # Weights status is a property of the MODEL a run used, and the agent
    # capture does not carry it. `hostModelSlug` is provider-prefixed
    # ("anthropic_claude-sonnet-4-6"), so match on the slug with and without
    # that prefix. Fourteen of the runs use models the leaderboard has no row
    # for at all -- unreleased codenames like "spiffy-blimp350" -- and those
    # stay None rather than being defaulted to proprietary, which would be a
    # claim AA never made.
    weights = {m["slug"]: bool(m.get("isOpenWeights"))
               for m in models if isinstance(m.get("slug"), str)}

    def open_weights(host_slug):
        if not isinstance(host_slug, str):
            return None
        parts = host_slug.split("_")
        # Provider prefixes are one OR two segments ("openai_gpt-5-6-sol",
        # "alibaba_cloud_qwen3-7-plus"), so try every suffix rather than
        # assuming a fixed depth.
        for i in range(len(parts)):
            candidate = "_".join(parts[i:])
            if candidate in weights:
                return weights[candidate]
        return None

    rows = []
    for a in agents:
        score = num(a.get("indexScore"))
        mean = a.get("mean") if isinstance(a.get("mean"), dict) else {}
        cost = num(mean.get("costUsd"))
        if score is None or cost is None or cost <= 0:
            continue
        label = a.get("displayLabel") or ""
        base, eff = split_effort(label)
        display = a.get("display")
        display = display if isinstance(display, dict) else {}
        creators = display.get("creator")
        creators = creators if isinstance(creators, dict) else {}
        rows.append({
            # The reader-facing name (#88), same as model rows: the dict-form
            # effort text is decoded out of it, and the RAW label survives
            # only in the capture.
            "name": display_name(label),
            "base": base,
            "eff": eff,
            # The compact chart label (#85), same as model rows.
            "label": display_label(label),
            "kind": "agent",
            "agent": a.get("agentName") or None,
            # The LAB filter groups by who made the MODEL, so a Claude Code run
            # on GLM-5.2 files under Z.ai rather than Anthropic -- the harness
            # is named separately in the row and the tooltip.
            "creator": creators.get("model") or "",
            "country": "",
            "ii": None,
            "cost": None,
            "metrics": {
                "coding": {"score": round(score * 100, 2), "cost": round(cost, 4)},
                "intelligence": None,
                "agentic": None,
            },
            "params": None,
            "open": open_weights(a.get("hostModelSlug")),
            "dep": bool(a.get("isUnavailable")),
            "est": False,
            "reas": False,
            "lic": None,
            "ctx": None,
            "rel": None,
            "tps": None,
            "secs": round(mean["agentWallTimeSec"], 1) if num(mean.get("agentWallTimeSec")) else None,
            "pin": None,
            "pout": None,
        })
    rows.sort(key=lambda r: (-r["metrics"]["coding"]["score"],
                             r["metrics"]["coding"]["cost"], r["name"]))
    return rows


def metric_of(row, metric):
    """The score/cost pair a metric renders for a row, mirroring the page's
    metricOf(). The parameters axis is not a pair in the payload -- it pairs
    the Intelligence Index with the parameter count, so it exists where both
    do -- and every other metric is the pair the payload carries.
    """
    if metric == "parameters":
        if row["params"] is not None and row["ii"] is not None:
            return {"score": row["ii"], "cost": row["params"]}
        return None
    return row.get("metrics", {}).get(metric)


def undominated(rows, metric="intelligence"):
    """The single Pareto layer -- the page's one and only definition of
    'superseded'. A model is superseded when some other model is at least as
    smart AND at least as cheap (strictly better on one of the two). Exact ties
    survive together: neither strictly beats the other. Pairs come from
    metric_of(), so the parameters axis is a metric like any other here, as
    it is in the page's frontierMetric()."""
    pairs = {id(r): pair for r in rows
             if (pair := metric_of(r, metric))}
    eligible = [r for r in rows if id(r) in pairs]
    return [
        r for r in eligible
        if not any(
            o is not r
            and pairs[id(o)]["score"] >= pairs[id(r)]["score"]
            and pairs[id(o)]["cost"] <= pairs[id(r)]["cost"]
            and (
                pairs[id(o)]["score"] > pairs[id(r)]["score"]
                or pairs[id(o)]["cost"] < pairs[id(r)]["cost"]
            )
            for o in eligible
        )
    ]


# The capture's one generation: the leaderboard's copy (Overseer ruling,
# delegated by the maintainer, 2026-10-05, issue #200). The two routes are
# independently cached Vercel pages and AA's data lands on them at different
# times, so a capture can straddle an update -- but the detail route is
# MEASURED to be the stale one (its corpus keeps the previous generation's
# display names and scores), and the per-route generation timestamps do NOT
# identify which route is stale: a detail page regenerated later still embeds
# the older corpus. So the leaderboard is published, always, and the detail
# route is a gap-fill and nothing more.
def merge_captures(base: list, detail: list) -> list:
    """Leaderboard records widened with the detail route's extra fields.

    The leaderboard is the authority on WHICH models exist and on every field
    it ships; the detail route fills only what the leaderboard does not carry
    (parameters, licence, release date, the per-evaluation cost breakdown).
    A value the leaderboard HAS is never replaced by the detail route's,
    silently and always: two generations mixed into one capture is exactly
    what made the page oscillate, so a conflicting detail value is not a
    disagreement to resolve -- it simply loses.
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
                # breakdown. The leaderboard's number WINS -- it is the
                # fresh generation's measured total, and it is the value the
                # cost axis plots. The object is a fill, so it is taken whole
                # except for that total, and only while its breakdown still
                # sums to the number it is being hung under: a breakdown from
                # another generation would decompose someone else's total, so
                # it is dropped whole and the axis that reads it (GDPval) is
                # absent for this model until the routes agree. Dropping is
                # the honest outcome -- the alternative is either publishing a
                # stale total or failing the refresh red for hours.
                cost = v.get("cost")
                out[k] = {
                    **v,
                    "cost": fill({"total": out[k]}, cost) if isinstance(cost, dict)
                    else {"total": out[k]},
                }
                if not _breakdown_matches_total(out[k]):
                    out[k] = out[k]["cost"]["total"]
        return out

    def _breakdown_matches_total(obj):
        """Whether `obj`'s per-evaluation breakdown decomposes its own total.

        AA writes the breakdown as the index weights already applied, so the
        parts sum to the total exactly (SUM_TOLERANCE in fetch_aa.py checks
        that over a whole capture). A breakdown that does not sum is not this
        total's breakdown, whatever route it came from.
        """
        evaluations = obj.get("evaluations")
        if not isinstance(evaluations, list):
            return True
        parts = [e.get("weightedCostPerTask") for e in evaluations
                 if isinstance(e, dict)]
        if not all(isinstance(p, (int, float)) and not isinstance(p, bool)
                   for p in parts):
            return True
        total = obj["cost"]["total"]
        return abs(sum(parts) - total) <= 1e-6 * max(1.0, abs(total))

    by_slug = {m["slug"]: m for m in detail if isinstance(m.get("slug"), str)}
    return [fill(m, by_slug[m["slug"]]) if by_slug.get(m.get("slug")) else m
            for m in base]


# The capture stamp is interpolated into the rendered page without escaping
# (the header, the method grid, and the copy-as-Markdown and copy-as-JSON
# clips, all fed by one value). scripts/fetch_aa.py:415 writes it as
# dt.date.today().isoformat() + "\n" -- a single zero-padded ISO date, nothing
# else -- so a stamp in any other shape did not come from fetch_aa.py: markup
# in it would execute when the page opens, and a __DATA__ in it would splice
# the JSON payload out of its template slot. The read is the chokepoint every
# sink is downstream of, so it accepts that one shape and refuses the rest.
CAPTURE_STAMP_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# fetch_aa.py writes the stamp beside the capture it stamps, and this build
# reads that capture from RAW and AGENTS_RAW -- so the capture is present
# exactly when one of these input files sits beside the stamp (issue #64).
# Fixed at import: a test that redirects RAW must not rename what the guard
# looks for.
CAPTURE_INPUTS = (RAW.name, AGENTS_RAW.name)


def _stamp_refusal(stamp_path: pathlib.Path, found: str) -> SystemExit:
    """The one refusal, shared so every exit names the same observation."""
    return SystemExit(
        f"{stamp_path} does not hold the stamp fetch_aa.py writes -- a "
        f"single zero-padded ISO date, YYYY-MM-DD: found {found}"
    )


def read_capture_stamp(stamp_path: pathlib.Path) -> str:
    """The stamp exactly as fetch_aa.py wrote it, or a refusal.

    fetch_aa.py writes dt.date.today().isoformat() + "\\n" -- a zero-padded
    ISO date and a trailing newline, nothing else. Whitespace around the date
    stays accepted: the existing strip() tolerance already removed it, and the
    accepted character set (digits and hyphens) cannot carry markup or a
    payload placeholder whatever pads it.
    """
    if not stamp_path.exists():
        # A capture that lost its stamp must not be silently relabelled with
        # the build date (issue #64): refuse when capture data is present.
        capture = [
            name for name in CAPTURE_INPUTS if (stamp_path.parent / name).exists()
        ]
        if capture:
            raise SystemExit(
                f"{stamp_path} is missing while the capture it stamps is "
                f"present ({', '.join(capture)}) -- fetch_aa.py writes the "
                f"stamp on capture; re-run the capture"
            )
        # No capture data beside the stamp: a genuinely empty (pre-stamp)
        # data directory, with nothing to relabel. Today's date is in the
        # accepted shape by construction.
        return dt.date.today().isoformat()
    raw = stamp_path.read_bytes()
    try:
        value = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        # Still fail-closed, but the designed refusal rather than a
        # traceback: the offending bytes themselves are the content named.
        raise _stamp_refusal(stamp_path, repr(raw)) from None
    valid = CAPTURE_STAMP_RE.fullmatch(value) is not None
    if valid:
        # The writer can only emit a real calendar date, so a date-shaped
        # non-date (2026-13-99) is refused too.
        try:
            dt.date.fromisoformat(value)
        except ValueError:
            valid = False
    if not valid:
        raise _stamp_refusal(stamp_path, repr(value))
    return value


def read_capture(path):
    """The capture at path, parsed -- or a guarded exit naming the file.

    A capture written by a crashed runner can end mid-file (issue #66), and
    parsing it anyway died with a raw JSONDecodeError traceback that named no
    file. A corrupt capture is the same signal as a schema change -- fail red
    with one actionable line -- never a traceback and never a partial build.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"{path.relative_to(ROOT)}: corrupt capture ({exc}) -- re-capture "
            "with scripts/fetch_aa.py rather than building from a half-written file"
        ) from exc


# The two table bodies rendered at build time (#97). The page's script fills
# #fTable and #tbl on load; with JavaScript disabled a visitor got page
# chrome and no data. main() now renders both bodies into the template in the
# page's DEFAULT state -- every filter chip on except superseded/effort, no
# lab, no query, no pins, sorted by Intelligence Index descending -- by
# running the same pipeline the script runs. The functions below mirror the
# page's JavaScript one for one; the browser drift test loads the page with
# and without JavaScript and holds the two renders equal cell-for-cell.

METRIC_LABELS = {
    "coding": "Coding Agent Index",
    "intelligence": "Intelligence Index",
    "agentic": "GDPval-AA v2",
}

# The metric views the page unions for the full table, in Object.keys()
# order -- the order the script's Set-union preserves for ties.
VIEW_ORDER = ("coding", "intelligence", "parameters", "agentic")

# A marker in a rendered tbody would be spliced by a substitution that runs
# after the tbody replacements -- "__DATA__" in a name would have the JSON
# payload written into its cell -- so a build carrying one refuses, naming
# the marker, the same fail-red culture as the stamp and commit-shape
# validations.
TEMPLATE_MARKERS = ("__DATA__", "__PROVENANCE__", "__CAPTURED__", "__TBODY_")


def frontier_layer(rows, metric):
    """The frontier in the page's display order: cost ascending, score
    descending, stable -- the page's frontierMetric() comparator, over the
    undominated layer `undominated` computes."""
    front = undominated(rows, metric)

    def order_key(row):
        # undominated() already filtered this layer to rows carrying the
        # metric, so the pair is present by construction; the assertion is
        # the type narrowing, not a runtime check that can fire.
        pair = metric_of(row, metric)
        assert pair is not None, f"{metric} pair missing for {row['name']}"
        return (pair["cost"], -pair["score"])

    return sorted(front, key=order_key)


def default_state_rows(rows):
    """The #tbl rows in the page's default state, in render order.

    The script's metricViews() with every filter chip on but
    superseded/effort off, no lab, no query and no pins, is the full
    unfiltered slices: one view per axis in VIEW_ORDER, the order
    Object.keys() hands the script and its Set-union preserves for ties.
    Rows deduplicate by identity across the views, then the default header
    sorts: Intelligence Index descending, missing values last, stable for
    ties (Array.prototype.sort is stable, and so is sorted()).
    """
    union = []
    seen = set()
    for metric in VIEW_ORDER:
        for row in rows:
            if metric_of(row, metric) and id(row) not in seen:
                seen.add(id(row))
                union.append(row)

    def order_key(row):
        pair = metric_of(row, "intelligence")
        return (pair is None, -(pair["score"] if pair else 0.0))

    return sorted(union, key=order_key)


def render_frontier_tbody(rows):
    """#fTable's body: per metric in METRIC_ORDER, its frontier rows in
    cost-DESCENDING order -- the page renders frontierMetric() (cost
    ascending, score descending) reversed, so the $/point read runs the
    same way a sorted column does."""
    parts = []
    for metric in METRIC_ORDER:
        for row in reversed(frontier_layer(rows, metric)):
            # The rows came through frontier_layer(), so the pair is
            # present; the assertion narrows for the reader below.
            pair = metric_of(row, metric)
            assert pair is not None, f"{metric} pair missing for {row['name']}"
            parts.append(
                "<tr>"
                + f"<td>{html.escape(METRIC_LABELS[metric])}</td>"
                + f'<td class="name">{html.escape(row["name"])}</td>'
                + f"<td>{html.escape(show_text(row['creator']))}</td>"
                + f'<td class="n">{js_to_fixed(pair["score"], 1)}</td>'
                + f'<td class="n">{fmt_cost(pair["cost"])}</td>'
                + '<td class="n">'
                # A zero score is a legal AA publication (gdpvalNormalized
                # carries literal zeros in the capture), and a score-0 row
                # sits on this layer exactly when it holds the axis's
                # minimum cost -- strictly, or tied only with other
                # zero-score rows. $/point at zero capability is not a
                # number:
                # em dash, the page's missing-value mark -- never a crash
                # (issue #146 red an hour on the bare ZeroDivisionError)
                # and never a "$Infinity" cell.
                + ('$' + js_to_fixed(pair["cost"] / pair["score"], 4)
                   if pair["score"] else EM_DASH)
                + "</td>"
                + f"<td>{_tag(weights_text(row), 'tag')}</td>"
                + "</tr>"
            )
    return "".join(parts)


def _tag(text, cls):
    """A pill span, the page's only inline tag shape."""
    return f'<span class="{cls}">{html.escape(text)}</span>'


def render_main_tbody(rows):
    """#tbl's body: the default-state rows through fillTable's cell rules."""
    front_sets = {
        metric: {id(r) for r in frontier_layer(rows, metric)}
        for metric in (*METRIC_ORDER, "parameters")
    }
    parts = []
    for row in default_state_rows(rows):
        cells = ['<tr>', f'<td class="name">{html.escape(row["name"])} ']
        if row["dep"]:
            cells.append(_tag("vendor-retired", "tag"))
        cells.append("</td>")
        cells.append(f"<td>{html.escape(show_text(row['creator']))}</td>")
        for metric in METRIC_ORDER:
            pair = metric_of(row, metric)
            if pair:
                score = js_to_fixed(pair["score"], 1)
                cost = fmt_cost(pair["cost"])
            else:
                score = cost = EM_DASH
            if pair and id(row) in front_sets[metric]:
                score += " " + _tag("frontier", "tag f")
            cells.append(f'<td class="n">{score}</td>')
            cells.append(f'<td class="n">{cost}</td>')
            if metric == "intelligence":
                params = fmt_params(row["params"])
                if metric_of(row, "parameters") and id(row) in front_sets["parameters"]:
                    params += " " + _tag("parameter frontier", "tag f")
                cells.append(f'<td class="n">{params}</td>')
        cells.append(
            "<td class=\"n\">"
            + (EM_DASH if row["pin"] is None else "$" + js_number(row["pin"]))
            + "</td>")
        cells.append(
            "<td class=\"n\">"
            + (EM_DASH if row["pout"] is None else "$" + js_number(row["pout"]))
            + "</td>")
        cells.append(
            "<td class=\"n\">"
            + (EM_DASH if row["tps"] is None else js_number(row["tps"]))
            + "</td>")
        cells.append(f'<td class="n">{fmt_ctx(row["ctx"])}</td>')
        cells.append(f"<td>{html.escape(show_text(row['rel']))}</td>")
        cells.append(f"<td>{html.escape(weights_text(row))}</td>")
        cells.append("</tr>")
        parts.append("".join(cells))
    return "".join(parts)


def render_static_tbodies(rows):
    """Both static tbody strings, in template order, guarded.

    A captured string carrying a template marker would be spliced by a
    substitution that runs after the tbody replacements -- so a build
    carrying one refuses here rather than shipping a page with a marker
    left in it, exactly as the stamp read refuses a stamp-shaped attack.
    """
    rendered = (("the frontier table", render_frontier_tbody(rows)),
                ("the full table", render_main_tbody(rows)))
    for name, tbody in rendered:
        for marker in TEMPLATE_MARKERS:
            if marker in tbody:
                raise SystemExit(
                    f"the static {name} carries the template marker "
                    f"{marker} -- a captured string reached the rendered "
                    "tbody and the later substitutions would splice it; "
                    "refusing to build"
                )
    return rendered[0][1], rendered[1][1]


def main():
    models = read_capture(RAW)
    agents = read_capture(AGENTS_RAW)
    rows = build_rows(models) + build_agent_rows(agents, models)
    intelligence_rows = [r for r in rows if r["metrics"]["intelligence"]]

    # Reported only -- the page recomputes this layer against whatever the
    # filters leave, so nothing is baked into the data.
    front = undominated(intelligence_rows)
    kept = {r["name"] for r in front}
    retired_and_beaten = sum(
        1 for r in intelligence_rows if r["dep"] and r["name"] not in kept
    )

    # What collapsing effort levels actually costs, measured rather than assumed.
    # Turning a model down makes it cheaper AND dumber, so a low-effort variant is
    # NOT dominated by its high-effort twin -- effort levels are real operating
    # points and collapsing them deletes genuine frontier positions.
    ceiling = {}
    for r in intelligence_rows:
        c = ceiling.get(r["base"])
        if not c or r["ii"] > c["ii"] or (r["ii"] == c["ii"] and r["cost"] < c["cost"]):
            ceiling[r["base"]] = r
    sib_beaten = sum(
        1 for r in intelligence_rows
        if any(o is not r and o["base"] == r["base"]
               and o["ii"] >= r["ii"] and o["cost"] <= r["cost"]
               and (o["ii"] > r["ii"] or o["cost"] < r["cost"])
               for o in intelligence_rows)
    )
    front_collapsed = undominated(list(ceiling.values()))

    # Written by fetch_aa.py when the capture was taken. The today-fallback
    # covers only a data directory with no capture in it; a capture that lost
    # its stamp is refused rather than relabelled with the build date (issue
    # #64), and the read validates the format because the stamp is
    # interpolated unescaped downstream (issue #40).
    captured = read_capture_stamp(RAW.parent / "captured-at.txt")
    stats = {
        "total": len(models),
        "plotted": len(intelligence_rows),
        "creators": len({r["creator"] for r in intelligence_rows}),
        "open": sum(1 for r in intelligence_rows if r["open"]),
        "prop": sum(1 for r in intelligence_rows if not r["open"]),
        "captured": captured,
        "evals": INDEX_EVALS,
        "bases": len(ceiling),
        "sibBeaten": sib_beaten,
        "frontFull": len(front),
        "frontCollapsed": len(front_collapsed),
        "metricCounts": {
            metric: sum(1 for r in rows if r["metrics"][metric])
            for metric in METRIC_ORDER
        },
        "metricFrontiers": {
            metric: len(undominated(rows, metric)) for metric in METRIC_ORDER
        },
        "parameterCount": sum(
            1 for r in rows
            if r["params"] is not None and r["metrics"]["intelligence"] is not None
        ),
    }
    # A rendered axis with nothing on it means the capture moved under us --
    # a renamed field, a dropped cost slug. The page must not be published in
    # that state: an empty scatter reads as "nothing qualifies" rather than
    # "the pipeline broke", and the browser tests can only report it as an
    # opaque locator timeout. The page renders FOUR axes: metricCounts
    # quantifies the three score/cost ones, parameterCount the fourth, which
    # pairs the Intelligence Index with model size rather than with a cost
    # (issue #60) -- so the enumeration here covers both stats, and a stale
    # capture (AA's totalParameters rename) fails red instead of publishing
    # an empty parameters chart.
    rendered = {**stats["metricCounts"], "parameters": stats["parameterCount"]}
    empty = [axis for axis, n in rendered.items() if not n]
    if empty:
        raise SystemExit(
            "no rows carry a score/cost pair for: " + ", ".join(sorted(empty))
            + " -- the AA capture changed shape; re-read the leaderboard rather "
            "than publishing an empty chart"
        )

    payload = json.dumps({"rows": rows, "stats": stats}, separators=(",", ":")).replace(
        "<", "\\u003c"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Provenance. The content hash is a sha256 over the two capture files,
    # whole bytes concatenated models-then-agents -- a reader holding the
    # committed data directory can verify it today, with no workflow change.
    # The source commit is known only to the build's caller, so it renders
    # only when the environment carries one; unset renders nothing extra.
    # Replaced FIRST so the payload, still inserted last, can never be
    # re-substituted by a captured string carrying this marker.
    digest = hashlib.sha256()
    for capture in (RAW, AGENTS_RAW):
        digest.update(capture.read_bytes())
    commit = os.environ.get("AA_SOURCE_COMMIT", "")
    # Only a SHA-shaped value renders. The env is build-machine input, and a
    # value carrying a template marker would otherwise be spliced by the
    # later __CAPTURED__/__DATA__ substitutions -- anything else renders
    # nothing, exactly as if the variable were unset.
    if not re.fullmatch(r"[0-9a-f]{7,40}", commit, re.I):
        commit = ""
    commit_note = (f" Source commit <code>{html.escape(commit)}</code>."
                   if commit else "")
    inputs_note = ("data/aa-raw-models.json then "
                   "data/aa-raw-coding-agents.json, whole files "
                   "concatenated in that order.")
    provenance = ("Capture <code>" + digest.hexdigest() + "</code> &mdash; sha256 over "
                  + inputs_note + commit_note)
    # The tbody substitutions run between the captured stamp and the payload:
    # the stamp's value is a validated ISO date and the provenance commit a
    # validated SHA, so nothing either carries can splice the bodies, and the
    # payload -- inserted LAST, exactly because captured strings flow through
    # it -- can never re-splice a rendered tbody. render_static_tbodies has
    # already refused any rendered body that carries a marker.
    frontier_tbody, main_tbody = render_static_tbodies(rows)
    OUT.write_text(TEMPLATE.replace("__PROVENANCE__", provenance)
                   .replace("__CAPTURED__", captured)
                   .replace("__TBODY_FRONTIER__", frontier_tbody)
                   .replace("__TBODY_MAIN__", main_tbody)
                   .replace("__DATA__", payload),
                   encoding="utf-8")
    dep = sum(1 for r in intelligence_rows if r["dep"])
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {stats['plotted']} models plotted "
          f"({stats['prop']} proprietary / {stats['open']} open-weights, "
          f"{stats['creators']} labs)")
    print(f"  {len(front)} undominated, "
          f"{len(intelligence_rows) - len(front)} superseded by metric")
    print(f"  of {dep} vendor-retired models, {retired_and_beaten} are also beaten on the "
          f"numbers ({'metric filter subsumes the vendor flag' if retired_and_beaten == dep else 'MISMATCH -- some retired model is still undominated'})")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Frontier models &mdash; capability vs cost per task</title>
<style>
  .viz-root, body {
    color-scheme: light;
    --surface-1:#fcfcfb; --plane:#f9f9f7;
    /* --muted and --accent are darkened one step from their original values
       (#898781, #2a78d6): at those values the table headers measured 3.50:1
       and the frontier tag 4.30:1, under the 4.5:1 WCAG AA floor. The dark
       theme keeps the originals and passes there. */
    --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#706e67;
    --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
    --series-prop:#2a78d6; --series-open:#eb6834; --dim:#a9a7a0;
    --accent:#2468c0;
    /* Dedicated token for the dashed frontier line: the line used to borrow
       --muted, which now also fills every superseded point on every chart.
       It keeps the original gray -- --muted itself was darkened to 4.5:1 for
       AA text contrast, which is exactly the retuning this token exists to
       absorb without silently restyling the line. */
    --frontier-line:#898781;
    --sans:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
    --mono:ui-monospace,'SF Mono',Menlo,Monaco,monospace;
    --radius:12px;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root,
    :root:where(:not([data-theme="light"])) body {
      color-scheme: dark;
      --surface-1:#1a1a19; --plane:#0d0d0d;
      --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
      --series-prop:#3987e5; --series-open:#d95926; --dim:#6f6d67;
      --accent:#3987e5;
    }
  }
  :root[data-theme="dark"] .viz-root, :root[data-theme="dark"] body {
    color-scheme: dark;
    --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
    --series-prop:#3987e5; --series-open:#d95926; --dim:#6f6d67;
    --accent:#3987e5;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:var(--sans);background:var(--plane);color:var(--text-secondary);
    line-height:1.58;padding:44px 24px 100px;-webkit-font-smoothing:antialiased}
  /* No width cap: the chart and tables use the whole monitor. Prose blocks keep
     their own max-width below, because a 3000px-wide paragraph is unreadable. */
  .page{margin:0 auto;max-width:none}
  .eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;
    color:var(--muted);margin-bottom:10px}
  h1{font-size:34px;line-height:1.15;color:var(--text-primary);font-weight:600;
    letter-spacing:-.015em;margin-bottom:12px}
  .lede{font-size:15.5px;max-width:860px;margin-bottom:26px}
  a{color:var(--accent)}

  .method{background:var(--surface-1);border:1px solid var(--border);border-radius:var(--radius);
    padding:16px 20px;margin-bottom:16px}
  .method .label{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;
    letter-spacing:.06em;color:var(--muted);margin-bottom:10px}
  .mgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;font-size:13.5px}
  @media (max-width:900px){.mgrid{grid-template-columns:repeat(2,1fr)}}
  .mgrid .k{font-family:var(--mono);font-size:10px;text-transform:uppercase;
    letter-spacing:.05em;color:var(--muted);margin-bottom:2px}
  .mgrid .v{color:var(--text-primary);font-weight:600}

  .callout{background:var(--surface-1);border:1px solid var(--border);
    border-left:3px solid var(--accent);border-radius:var(--radius);
    padding:13px 18px;margin-bottom:30px;font-size:13.5px;max-width:980px}
  .callout b{color:var(--text-primary)}

  .filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
  .chip{font-family:var(--mono);font-size:12px;padding:6px 13px;border-radius:999px;
    border:1px solid var(--border);background:var(--surface-1);color:var(--text-secondary);
    cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:7px}
  /* .chip sets display:inline-flex, and an author rule beats the UA sheet's
     [hidden]{display:none} -- so without this the pin chips render even when
     the hidden attribute is set. */
  .chip[hidden]{display:none}
  .chip:hover{border-color:var(--accent)}
  .chip[aria-pressed="true"]{border-color:var(--accent);color:var(--text-primary);
    box-shadow:0 0 0 1px var(--accent) inset}
  .chip .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
  .chip .dot.prop{background:var(--series-prop)}
  .chip .dot.open{background:var(--series-open)}
  /* Hollow, matching how these points draw: an absent value, not a third category. */
  .chip .dot.unk{background:none;border:2px solid var(--series-prop);box-sizing:border-box}
  select,input[type=search]{font-family:var(--mono);font-size:12px;padding:6px 11px;
    border-radius:999px;border:1px solid var(--border);background:var(--surface-1);
    color:var(--text-primary)}
  .count{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:auto}

  .card{background:var(--surface-1);border:1px solid var(--border);
    border-radius:var(--radius);padding:20px;margin-bottom:34px}
  .cap{font-family:var(--mono);font-size:10.5px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.06em;margin-bottom:6px}
  /* explicit: the tooltip is allowed to hang outside the plot and the card */
  .plotwrap{position:relative;overflow:visible}
  .card{overflow:visible}
  svg{display:block;width:100%;height:auto}
  svg text{font-family:var(--mono);font-size:10.5px;fill:var(--muted)}
  /* Boxed labels: the filled box hides the gridlines behind the lettering (so
     no halo is needed), and the leader line ties the text to its own dot. */
  svg text.lbl{font-size:10px;fill:var(--text-secondary)}
  svg rect.lblbox{fill:var(--surface-1);stroke:var(--border);stroke-width:1}
  svg line.lead{stroke:var(--muted);stroke-width:1}
  .pt{cursor:pointer}
  .pt.fade{opacity:.18}
  .pt:focus{outline:none;stroke:var(--accent);stroke-width:4}
  /* a pinned point keeps a dark ring so you can see what you have stuck down */
  .pt.pinned{stroke:var(--text-primary);stroke-width:2}
  svg rect.lblbox.pinned{stroke:var(--accent)}
  th[data-k]:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}

  .legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12.5px;margin:14px 0 2px;
    font-family:var(--mono);color:var(--text-secondary)}
  .legend .item{display:inline-flex;align-items:center;gap:7px}
  .legend .swatch{width:11px;height:11px;border-radius:50%;display:inline-block}
  .legend .swatch.hollow{background:none !important;border:2px solid var(--series-prop);box-sizing:border-box}
  .legend .line{width:20px;height:0;border-top:2px dashed var(--frontier-line);display:inline-block}

  .tip{position:absolute;pointer-events:none;opacity:0;
    background:var(--surface-1);border:1px solid var(--border);border-radius:9px;
    padding:9px 12px;font-size:12.5px;min-width:190px;max-width:280px;
    box-shadow:0 6px 22px rgba(0,0,0,.18);z-index:50}
  .tip.on{opacity:1}
  /* The fades are a nicety, not information: under prefers-reduced-motion
     the tooltip and the copy toast must appear and vanish instantly rather
     than animate. */
  @media (prefers-reduced-motion: no-preference) {
    .tip{transition:opacity 120ms ease}
    .toast{transition:opacity .2s}
  }
  .tip .tname{color:var(--text-primary);font-weight:600;font-size:13px;margin-bottom:5px}
  .tip .trow{display:flex;justify-content:space-between;gap:14px;font-family:var(--mono);font-size:11.5px}
  .tip .trow .tv{color:var(--text-primary);font-weight:600}
  .tip .tkey{display:inline-block;width:14px;height:2px;vertical-align:middle;margin-right:6px}

  table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
  th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border)}
  th{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;
    color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap;position:sticky;top:0;
    background:var(--surface-1);z-index:2}
  th:hover{color:var(--text-primary)}
  th .ar{opacity:.45}
  td.n{font-family:var(--mono);text-align:right;font-variant-numeric:tabular-nums;
    color:var(--text-primary)}
  td.name{color:var(--text-primary);font-weight:600}
  tbody tr:hover{background:var(--plane)}
  .tag{font-family:var(--mono);font-size:10px;padding:1px 7px;border-radius:999px;
    border:1px solid var(--border);color:var(--text-secondary);white-space:nowrap}
  .tag.f{border-color:var(--accent);color:var(--accent)}
  .scroll{max-height:560px;overflow:auto;border:1px solid var(--border);border-radius:var(--radius)}
  /* An empty filtered slice says so inside the table region instead of
     leaving a silent zero-row body; aria-live announces the change. */
  .empty-state{padding:28px 16px;font-size:13.5px;color:var(--text-secondary)}
  .empty-state[hidden]{display:none}

  h2{font-size:22px;color:var(--text-primary);font-weight:600;margin-bottom:6px;letter-spacing:-.01em}
  .sub{font-size:14px;margin-bottom:16px;max-width:880px}
  .toc{display:flex;gap:16px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;margin-bottom:30px}
  button.action{font-family:var(--mono);font-size:12px;padding:8px 15px;background:var(--surface-1);
    color:var(--accent);border:1px solid var(--accent);border-radius:8px;cursor:pointer}
  button.action:hover{background:var(--plane)}
  .toast{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-left:10px;
    opacity:0}
  .toast.show{opacity:1}
  .foot{color:var(--muted);font-size:12.5px;margin-top:56px;padding-top:20px;
    border-top:1px solid var(--border)}
  /* The global reset removes paragraph margins, so the footer's stacked
     lines would butt together without re-spacing them here. */
  .foot p+p{margin-top:8px}
</style>
</head>
<body class="viz-root">
<div class="page">

  <header>
    <div class="eyebrow">ai-researcher &middot; single-source &middot; captured __CAPTURED__</div>
    <h1>Frontier models &mdash; capability vs cost and size</h1>
    <p class="lede">Every number on this page comes from
      <a href="https://artificialanalysis.ai/leaderboards/models">artificialanalysis.ai</a> and nowhere else &mdash;
      the <a href="https://artificialanalysis.ai/leaderboards/models">model leaderboard</a> and the
      <a href="https://artificialanalysis.ai/agents/coding-agents">Coding Agent Index</a>.
      The first three charts pair an AA capability index with AA's measured cost to complete one task in
      that same index, so they share an axis and read against each other; the fourth swaps that axis for
      AA's reported total parameter count and so sits apart, last. Together they show both economic and
      parameter efficiency without stitching numbers from different sources.</p>
  </header>

  <div class="method">
    <div class="label">Method</div>
    <div class="mgrid">
      <div><div class="k">Source</div><div class="v">Artificial Analysis</div></div>
      <div><div class="k">Metric &middot; y</div><div class="v">Coding Agent &middot; Intelligence &middot; GDPval-AA</div></div>
      <div><div class="k">Metric &middot; x</div><div class="v">Matched $ / task &middot; total parameters</div></div>
      <div><div class="k">Models plotted</div><div class="v" id="mStat">&mdash;</div></div>
      <div><div class="k">Captured</div><div class="v">__CAPTURED__</div></div>
    </div>
  </div>

  <div class="callout">
    <b>Cost per task is measured, not quoted.</b> It is what Artificial Analysis actually spent running the
    model through each index &mdash; input, cached reads, output and reasoning tokens included &mdash; so a
    verbose reasoning model costs more than its per-token price suggests. That is also why the plot is
    smaller than the full catalogue: AA lists <span id="cTotal">&mdash;</span> models, while complete
    score-and-cost pairs cover <span id="cCoding">&mdash;</span> agent runs for Coding, <span id="cPlot">&mdash;</span>
    models for Intelligence and <span id="cAgentic">&mdash;</span> for GDPval-AA; <span id="cParams">&mdash;</span>
    models have both Intelligence Index and total parameters. Everything else is absent rather than estimated.
  </div>

  <div class="callout">
    <b>Two chips do the real work.</b> <em>Hide superseded</em> drops every model that another model beats
    on both axes at once &mdash; the metric's verdict, not the vendor's retirement flag, and recomputed
    against whatever else you have filtered to. <em>Dump effort levels</em> collapses each model's effort
    settings to a single row at its highest score for each chart, applied before that chart's superseded
    test so every frontier is drawn between models rather than knobs. Because a configuration can peak on
    one capability but not another, all four charts collapse and judge dominance independently.
  </div>

  <nav class="toc">
    <a href="#coding">1 &middot; Coding agents</a>
    <a href="#intelligence">2 &middot; Intelligence</a>
    <a href="#agentic">3 &middot; GDPval-AA</a>
    <a href="#parameters">4 &middot; Parameter efficiency</a>
    <a href="#frontier">5 &middot; Efficient frontiers</a>
    <a href="#table">6 &middot; Full table</a>
  </nav>

  <div class="filters" role="group" aria-label="Filters">
    <button class="chip" id="fProp" aria-pressed="true"><span class="dot prop"></span>Proprietary</button>
    <button class="chip" id="fOpen" aria-pressed="true"><span class="dot open"></span>Open-weights</button>
    <button class="chip" id="fUnk" aria-pressed="true"
      title="Coding-agent runs on a model AA's leaderboard does not carry, so its weights status is unpublished"><span class="dot unk"></span>Weights unpublished</button>
    <button class="chip" id="fSup" aria-pressed="false"
            title="Drop every model that some other model beats on both axes at once">Hide superseded</button>
    <button class="chip" id="fEff" aria-pressed="false"
            title="Collapse each model's effort settings to one row — its highest index">Dump effort levels</button>
    <button class="chip" id="fReas" aria-pressed="false">Reasoning only</button>
    <select id="fLab" aria-label="Filter by lab"><option value="">All labs</option></select>
    <input type="search" id="fQ" placeholder="search model&hellip;" aria-label="Search model name">
    <button class="chip" id="fOnly" aria-pressed="false" hidden>Only pinned</button>
    <button class="chip" id="fClear" hidden>Clear pinned names</button>
    <span class="count" id="count">&mdash;</span>
  </div>

  <noscript>
    <p class="sub">The charts, the filters and the sortable headers on this
      page require JavaScript; without it they do not render or respond. The
      two tables below are the fallback: both were rendered in full when this
      page was built, in the default view &mdash; every filter chip on, sorted
      by Intelligence Index, superseded models included.</p>
  </noscript>

  <section id="coding">
    <h2>1 &middot; Coding Agent Index</h2>
    <p class="sub">DeepSWE, Terminal-Bench v2.1 and SWE-Atlas-QnA, equally weighted. The unit here is an
      <b>agent plus a model</b> &mdash; Claude Code on Opus 5 (xhigh) is a different row from Codex on the
      same model &mdash; because the harness is part of what is being measured. Score and cost are both
      AA's, read off one run, so nothing is reweighted to put them on the same axis.
      AA no longer publishes the full table it once did, so this is every agent run still in its payload
      rather than the whole field it has measured &mdash; the frontier is drawn between the runs AA still
      reports.</p>
    <div class="card">
      <div class="cap">Coding Agent Index vs measured cost per task &middot; log cost axis &middot; up-and-left is better
        &middot; click any point to pin its name</div>
      <div class="plotwrap">
        <svg id="svg-coding" viewBox="0 0 980 560" role="img"
             aria-label="Scatter plot of Artificial Analysis Coding Agent Index against measured cost per task in US dollars"></svg>
        <div class="tip" id="tip-coding" role="status"></div>
      </div>
      <div class="legend">
        <span class="item"><span class="swatch" style="background:var(--series-prop)"></span>Proprietary</span>
        <span class="item"><span class="swatch" style="background:var(--series-open)"></span>Open-weights</span>
        <span class="item"><span class="swatch hollow"></span>Weights unpublished</span>
        <span class="item"><span class="swatch" style="background:var(--muted)"></span>Superseded</span>
        <span class="item"><span class="line"></span>Efficient frontier</span>
      </div>
    </div>
  </section>

  <section id="intelligence">
    <h2>2 &middot; Intelligence Index</h2>
    <p class="sub">AA's broad v4.3 synthesis across agentic work, coding, scientific reasoning and general capability.</p>
    <div class="card">
      <div class="cap">Intelligence Index vs cost per task &middot; log cost axis &middot; up-and-left is better
        &middot; click any point to pin its name</div>
      <div class="plotwrap">
        <svg id="svg-intelligence" viewBox="0 0 980 560" role="img"
             aria-label="Scatter plot of Artificial Analysis Intelligence Index against cost per task in US dollars"></svg>
        <div class="tip" id="tip-intelligence" role="status"></div>
      </div>
      <div class="legend">
        <span class="item"><span class="swatch" style="background:var(--series-prop)"></span>Proprietary</span>
        <span class="item"><span class="swatch" style="background:var(--series-open)"></span>Open-weights</span>
        <span class="item"><span class="swatch" style="background:var(--muted)"></span>Superseded</span>
        <span class="item"><span class="line"></span>Efficient frontier</span>
      </div>
    </div>
  </section>

  <section id="agentic">
    <h2>3 &middot; GDPval-AA v2</h2>
    <p class="sub">Agentic real-world work tasks, scored by a judge panel against human experts and
      anchored at an Elo of 1000. A single evaluation rather than a composite: AA publishes its score and
      the cost it measured running it, and both come off the same run.</p>
    <div class="card">
      <div class="cap">GDPval-AA v2 vs its measured cost per task &middot; log cost axis &middot; up-and-left is better
        &middot; click any point to pin its name</div>
      <div class="plotwrap">
        <svg id="svg-agentic" viewBox="0 0 980 560" role="img"
             aria-label="Scatter plot of GDPval-AA v2 against its measured cost per task in US dollars"></svg>
        <div class="tip" id="tip-agentic" role="status"></div>
      </div>
      <div class="legend">
        <span class="item"><span class="swatch" style="background:var(--series-prop)"></span>Proprietary</span>
        <span class="item"><span class="swatch" style="background:var(--series-open)"></span>Open-weights</span>
        <span class="item"><span class="swatch" style="background:var(--muted)"></span>Superseded</span>
        <span class="item"><span class="line"></span>Efficient frontier</span>
      </div>
    </div>
  </section>

  <section id="parameters">
    <h2>4 &middot; Parameter efficiency</h2>
    <p class="sub">AA Intelligence Index against AA's reported total parameter count. The logarithmic
      x-axis measures model size, not active parameters or inference compute; models missing either value
      are absent rather than estimated.</p>
    <div class="card">
      <div class="cap">Intelligence Index vs total parameters &middot; log parameter axis &middot; up-and-left is better
        &middot; click any point to pin its name</div>
      <div class="plotwrap">
        <svg id="svg-parameters" viewBox="0 0 980 560" role="img"
             aria-label="Scatter plot of Artificial Analysis Intelligence Index against total parameter count in billions"></svg>
        <div class="tip" id="tip-parameters" role="status"></div>
      </div>
      <div class="legend">
        <span class="item"><span class="swatch" style="background:var(--series-prop)"></span>Proprietary</span>
        <span class="item"><span class="swatch" style="background:var(--series-open)"></span>Open-weights</span>
        <span class="item"><span class="swatch" style="background:var(--muted)"></span>Superseded</span>
        <span class="item"><span class="line"></span>Parameter-efficiency frontier</span>
      </div>
    </div>
  </section>

  <section id="frontier">
    <h2>5 &middot; The cost-efficient frontiers</h2>
    <p class="sub">The models nothing else beats on both axes at once for each capability &mdash; no other model is
      simultaneously at least as smart <em>and</em> at least as cheap. Anything missing from this list is
      <b>superseded on that metric</b>. Each layer recomputes against the filters above.</p>
    <div class="card scroll" style="padding:0;overflow:auto">
      <table id="fTable"><thead><tr>
        <th>Metric</th><th>Model</th><th>Lab</th><th style="text-align:right">Index</th>
        <th style="text-align:right">$ / task</th><th style="text-align:right">$ per index point</th><th>Weights</th>
      </tr></thead><tbody>__TBODY_FRONTIER__</tbody></table>
    </div>
  </section>

  <section id="table">
    <h2>6 &middot; Full table</h2>
    <p class="sub">The union of the four filtered slices, as numbers &mdash; click any header to sort.
      This is the accessible twin of all four plots: nothing is reachable only by hovering.</p>
    <div style="margin-bottom:12px">
      <button class="action" id="copyMd">Copy as Markdown</button>
      <button class="action" id="copyJson"
        title="Raw captured data, unescaped — strings are copied exactly as AA published them, so names and labs may carry pipes, backticks or script tags">Copy as JSON</button>
      <span class="toast" id="toast"></span>
    </div>
    <div class="scroll">
      <table id="tbl"><thead><tr>
        <th data-k="name">Model <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="creator">Lab <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="codingScore" style="text-align:right">Coding Agent Index <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="codingCost" style="text-align:right">Coding Agent $ / task <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="ii" style="text-align:right">Intelligence Index <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="cost" style="text-align:right">Intelligence $ / task <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="params" style="text-align:right">Parameters <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="agenticScore" style="text-align:right">GDPval-AA v2 <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="agenticCost" style="text-align:right">GDPval $ / task <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="pin" style="text-align:right">$ / 1M in <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="pout" style="text-align:right">$ / 1M out <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="tps" style="text-align:right">tok/s <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="ctx" style="text-align:right">Context <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="rel">Released <span class="ar" aria-hidden="true">&#8597;</span></th>
        <th data-k="open">Weights <span class="ar" aria-hidden="true">&#8597;</span></th>
      </tr></thead><tbody>__TBODY_MAIN__</tbody></table>
      <div class="empty-state" id="tblEmpty" aria-live="polite" hidden></div>
    </div>
  </section>

  <div class="foot">
    <p>Sourced entirely from Artificial Analysis. Intelligence Index v4.3 comprises
      <span id="evals"></span>. The Coding Agent Index carries its own measured cost per task, and the
      Intelligence Index cost is AA's own total, and the model rows are the leaderboard's own records,
      widened only where the leaderboard omits a field the page needs by a value from a model detail
      page; where both carry a field, the leaderboard's value is the one published. GDPval-AA's cost is AA's figure for that evaluation with
      its 10% index weight divided back out &mdash; AA reports each component's task cost pre-weighted, and
      the components sum exactly to the published total. No score, token price or task measurement is
      estimated, and nothing is filled in from another source. Rebuild with
      <code>python3 scripts/fetch_aa.py &amp;&amp; python3 build.py</code>.</p>
    <p>__PROVENANCE__</p>
    <p>&copy; 2026 Peter Z (Nitjsefnie) &middot;
      <a href="https://github.com/Nitjsefnie/ai-researcher/blob/main/LICENSE">MIT licence</a></p>
  </div>
</div>

<script>
const DATA = __DATA__;
(function(){
  "use strict";
  const R = DATA.rows, S = DATA.stats;
  const $ = id => document.getElementById(id);
  const fmtCost = v => v >= 1 ? "$" + v.toFixed(2) : "$" + v.toFixed(3);
  const fmtParams = v => v == null ? "—" : v >= 1000 ? (v/1000).toFixed(v%1000?1:0)+"T"
                                              : v >= 1 ? v.toFixed(v<10?1:0)+"B"
                                              : Math.round(v*1000)+"M";
  const fmtCtx  = v => v == null ? "—" : v >= 1e6 ? (v/1e6).toFixed(v%1e6?1:0)+"M"
                                            : v >= 1e3 ? Math.round(v/1e3)+"K" : String(v);
  const show = v => (v == null || v === "") ? "—" : String(v);
  // A markdown table cell cannot carry a literal pipe (it would close the
  // cell), backtick (it would open a code span), backslash (it would read as
  // an escape) or newline (it would break the row). The backslash goes first
  // so the escapes added here are not themselves re-escaped, and a newline
  // becomes the space a markdown renderer folds it to inside a cell.
  const mdCell = s => String(s).replace(/\\/g, "\\\\").replace(/\|/g, "\\|")
    .replace(/`/g, "\\`").replace(/\r?\n/g, " ");

  $("mStat").textContent = S.plotted + " of " + S.total;
  $("cTotal").textContent = S.total;
  $("cPlot").textContent  = S.plotted;
  $("cCoding").textContent = S.metricCounts.coding;
  $("cAgentic").textContent = S.metricCounts.agentic;
  $("cParams").textContent = S.parameterCount;
  $("evals").textContent  = S.evals.join(", ");

  // An empty lab (some coding-agent runs do not name one) is not a category:
  // skip it here so no blank entry reaches the dropdown, and show() renders
  // it as the em dash on every surface that reads it.
  const labs = [...new Set(R.map(r => r.creator))].filter(Boolean).sort((a,b)=>a.localeCompare(b));
  for (const l of labs) {
    const o = document.createElement("option");
    o.value = l; o.textContent = l; $("fLab").appendChild(o);
  }

  const st = { prop:true, open:true, unk:true, sup:false, eff:false, reas:false, only:false,
               lab:"", q:"", sortK:"ii", sortDir:-1 };
  // Names whose labels the reader has stuck down by clicking. Keyed by name so
  // a pin survives filtering and resizing, and returns when the model does.
  const pins = new Set();
  let focusAfterRender=null;

  function filteredBase(){
    const q = st.q.trim().toLowerCase();
    return R.filter(r =>
      (unknownWeights(r) ? st.unk : (r.open ? st.open : st.prop)) &&
      (!st.only || pins.has(r.name)) &&
      (!st.reas || r.reas) &&
      (!st.lab || r.creator === st.lab) &&
      (!q || r.name.toLowerCase().includes(q) || r.creator.toLowerCase().includes(q)));
  }

  function baseSlice(metric="intelligence"){
    return filteredBase().filter(r=>r.metrics[metric]);
  }

  // "Superseded" is decided by the metric, evaluated against whatever the other
  // filters left -- so it always means "beaten inside the view you are looking
  // at", never "retired by its vendor". A model is superseded when another is
  // at least as smart AND at least as cheap, strictly better on one of the two;
  // exact ties survive together.

  const METRICS={
    coding:{label:"Coding Agent Index",svg:"svg-coding",tip:"tip-coding"},
    intelligence:{label:"Intelligence Index",svg:"svg-intelligence",tip:"tip-intelligence"},
    agentic:{label:"GDPval-AA v2",svg:"svg-agentic",tip:"tip-agentic"},
  };
  const PLOTS={
    coding:METRICS.coding,
    parameters:{label:"Parameter efficiency",svg:"svg-parameters",tip:"tip-parameters"},
    agentic:METRICS.agentic,
  };
  const metricOf=(r,key)=>key==="parameters"
    ? (r.params!=null && r.ii!=null ? {score:r.ii,cost:r.params} : null)
    : r.metrics[key];

  // Collapse a model's effort settings to one row: its ceiling (highest index,
  // cheapest variant if two tie there). Deliberately runs BEFORE the dominance
  // test, so "superseded" is judged between models rather than between a model
  // and its own turned-down settings -- otherwise every low-effort variant is
  // trivially beaten by its high-effort twin and the frontier says nothing.
  function collapseMetric(rows,key){
    const by=new Map();
    for(const r of rows){
      const cur=by.get(r.base), m=metricOf(r,key), cm=cur&&metricOf(cur,key);
      if(!cur || m.score>cm.score || (m.score===cm.score && m.cost<cm.cost)) by.set(r.base,r);
    }
    return [...by.values()];
  }

  function frontierMetric(rows,key){
    return rows.filter(r=>{
      const m=metricOf(r,key);
      return !rows.some(o=>{
        if(o===r) return false;
        const om=metricOf(o,key);
        return om.score>=m.score && om.cost<=m.cost &&
          (om.score>m.score || om.cost<m.cost);
      });
    }).sort((a,b)=>metricOf(a,key).cost-metricOf(b,key).cost ||
                    metricOf(b,key).score-metricOf(a,key).score);
  }

  function metricSlice(key){
    let rows=key==="parameters"
      ? filteredBase().filter(r=>metricOf(r,key))
      : baseSlice(key);
    if(st.eff) rows=collapseMetric(rows,key);
    return st.sup ? frontierMetric(rows,key) : rows;
  }

  // colour follows the entity, never its rank or row order
  const colourOf = r => r.open ? "var(--series-open)" : "var(--series-prop)";
  // Weights status belongs to a MODEL. A coding-agent row inherits it from the
  // model that run used, and some of those models are not on AA's leaderboard
  // at all (unreleased codenames), so the honest value is "unknown" rather than
  // "proprietary". Unknown draws HOLLOW -- same hue, no fill -- because the
  // palette has no room for a third categorical colour on an all-pairs form.
  const unknownWeights = r => r.open === null || r.open === undefined;
  const fillOf   = r => unknownWeights(r) ? "var(--surface-1)" : colourOf(r);
  const strokeOf = r => unknownWeights(r) ? colourOf(r) : "var(--surface-1)";
  const weightsOf = r => unknownWeights(r) ? "not published"
                       : (r.open ? (r.lic || "open") : "proprietary");
  // Secondary tooltip rows shared by every chart, so one record reads the
  // same wherever it is hovered; the chart's own metric rows stay
  // chart-specific and come first. Each value goes through show(), so a
  // field the record does not carry renders as the em dash, never blank.
  const secondaryRows = r => [
    ["Lab", show(r.creator)],
    ["Weights", weightsOf(r)],
    ["Output speed", show(r.tps == null ? null : r.tps + " tok/s")],
    ["Context", fmtCtx(r.ctx)],
  ];

  /* ---------- scatter ---------- */
  // The plot fills whatever width the page gives it. The viewBox width tracks
  // the container in CSS pixels while the height stays fixed, so a wide monitor
  // buys a WIDER chart rather than a proportionally taller one -- and the extra
  // horizontal room is exactly what the label placer needs.
  let W=980, H=560; const L=62, Rr=22, T=20, B=52;

  // A chart label identifies exactly one row (#85): two rows on one chart
  // never render the same text. Labels prefer the build-time compact form
  // (r.label: effort re-attached right after the model name, so the word that
  // distinguishes effort variants survives the 34-char cap); a row whose
  // compact form is ambiguous (two rows compact to the same text) or whose
  // truncated text is already taken on this chart is re-truncated from the
  // full AA name; if that collides too, a numeric suffix disambiguates.
  const truncLabel = n => n.length > 34 ? n.slice(0, 33) + "…" : n;
  function assignLabels(queue, wideOf){
    // Wide labels render the full r.name, never clipped -- current behaviour
    // for pins and the frontier-only view, preserved. Seeding `taken` with
    // every wide row's full name is what stops a narrow label from
    // duplicating one.
    const taken = new Set();
    const compactCounts = new Map();
    for(const q of queue){
      if(wideOf(q)) taken.add(q.r.name);
      else{
        const c = q.r.label || q.r.name;
        compactCounts.set(c, (compactCounts.get(c)||0)+1);
      }
    }
    // One text per queue entry, aligned to queue order: pins first, then the
    // frontier -- the queue array order is the deterministic allocation
    // order, and every decision is over the chart's own queue.
    return queue.map(q => {
      if(wideOf(q)) return q.r.name;
      const compact = q.r.label || q.r.name;
      let text = truncLabel(compact);
      if(compactCounts.get(compact) > 1 || taken.has(text)){
        text = truncLabel(q.r.name);
        if(taken.has(text)){
          let n = 2;                          // first free number, queue order
          while(taken.has(text + " (" + n + ")")) n++;
          text = text + " (" + n + ")";
        }
      }
      taken.add(text);
      return text;
    });
  }

  let pts=[], frontSet=new Set();
  // The row each chart's tooltip was last built for, keyed by chart
  // ("intelligence" for the main chart). A tooltip's content is a pure
  // function of the chart and its row between renders, so a pointermove that
  // resolves to the same row re-fades and re-positions but skips the DOM
  // rebuild (#109). Nulled by the hide paths, which every render calls, so a
  // fresh pass always rebuilds once.
  const lastHovered={};
  function draw(rows,frontier){
    const svg = $("svg-intelligence");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const NS="http://www.w3.org/2000/svg";
    const el=(n,a)=>{const e=document.createElementNS(NS,n);
      for(const k in a) e.setAttribute(k,a[k]); return e;};

    W=Math.max(720,Math.round(svg.parentElement.getBoundingClientRect().width));
    // Fit the plot to the viewport less the docs-hub header (measured at 110px)
    // and 50px of breathing room, so the whole chart is on screen without
    // scrolling and does not butt against the edge.
    H=Math.max(380,(window.innerHeight||900)-160);
    svg.setAttribute("viewBox","0 0 "+W+" "+H);
    const px=W-L-Rr, py=H-T-B;

    if(!rows.length){
      const t=el("text",{x:W/2,y:H/2,"text-anchor":"middle"});
      t.textContent="No models match these filters.";
      svg.appendChild(t); pts=[]; frontSet=new Set(); return;
    }

    const costs=rows.map(r=>r.cost), iis=rows.map(r=>r.ii);
    const lo=Math.log10(Math.min(...costs)), hi=Math.log10(Math.max(...costs));
    const p=(hi-lo)*0.06 || 0.3, x0=lo-p, x1=hi+p;
    const yMax=Math.min(100,Math.ceil((Math.max(...iis)+4)/10)*10);
    const yMin=Math.max(0,Math.floor((Math.min(...iis)-4)/10)*10);
    const X=c=>L+(Math.log10(c)-x0)/(x1-x0)*px;
    const Y=v=>T+py-(v-yMin)/(yMax-yMin)*py;

    // gridlines: solid hairlines, one shade off the surface
    for(let v=yMin; v<=yMax; v+=10){
      svg.appendChild(el("line",{x1:L,y1:Y(v),x2:L+px,y2:Y(v),
        stroke:"var(--grid)","stroke-width":1}));
      const t=el("text",{x:L-9,y:Y(v)+3.5,"text-anchor":"end"});
      t.textContent=String(v); svg.appendChild(t);
    }
    const ty=el("text",{x:14,y:T+py/2,"text-anchor":"middle",
      transform:"rotate(-90 14 "+(T+py/2)+")"});
    ty.textContent="Intelligence Index →"; svg.appendChild(ty);

    for(let e=Math.floor(x0); e<=Math.ceil(x1); e++){
      for(const m of [1,2,5]){
        const c=m*Math.pow(10,e), lx=Math.log10(c);
        if(lx<x0||lx>x1) continue;
        svg.appendChild(el("line",{x1:X(c),y1:T,x2:X(c),y2:T+py,
          stroke:"var(--grid)","stroke-width":1}));
        const t=el("text",{x:X(c),y:T+py+17,"text-anchor":"middle"});
        t.textContent = c>=1 ? "$"+c : "$"+c.toFixed(c<0.01?3:2);
        svg.appendChild(t);
      }
    }
    svg.appendChild(el("line",{x1:L,y1:T+py,x2:L+px,y2:T+py,
      stroke:"var(--axis)","stroke-width":1}));
    const tx=el("text",{x:L+px/2,y:H-13,"text-anchor":"middle"});
    tx.textContent="Cost per task (USD, log scale) →"; svg.appendChild(tx);

    // Frontier: straight segments between consecutive points. (A stepped
    // staircase is the technically truer "attainment surface" -- at a given
    // budget, the most you can get -- but it reads as broken rather than as a
    // trend, so the direct line wins.)
    // The pass's frontier arrives already computed (#109): frontierMetric is a
    // pure function of (rows, key), and render used to re-run it here over the
    // very rows this receives.
    frontSet=new Set(frontier);
    const segs=[];
    if(frontier.length>1){
      let d="M "+X(frontier[0].cost)+" "+Y(frontier[0].ii);
      for(let i=1;i<frontier.length;i++){
        const x1=X(frontier[i-1].cost), y1=Y(frontier[i-1].ii);
        const x2=X(frontier[i].cost),   y2=Y(frontier[i].ii);
        segs.push([x1,y1,x2,y2]);
        d+=" L "+x2+" "+y2;
      }
      svg.appendChild(el("path",{d:d,fill:"none",stroke:"var(--frontier-line)",
        "stroke-width":1.5,"stroke-dasharray":"5 4","stroke-linejoin":"round"}));
    }

    // marks: r=5 (10px), 2px surface ring so overlaps stay separable
    pts=[];
    for(const r of rows){
      const cx=X(r.cost), cy=Y(r.ii), on=frontSet.has(r);
      // the de-emphasis gray is page-wide, matching drawCapability: a point
      // off this chart's frontier draws var(--muted); a frontier point keeps
      // its weights fill.
      const c=el("circle",{cx:cx,cy:cy,r:on?6:5,
        fill:on?fillOf(r):"var(--muted)",stroke:strokeOf(r),"stroke-width":2,
        class:"pt"+(pins.has(r.name)?" pinned":""),role:"button",tabindex:0,
        "aria-label":"Pin "+r.name+" on the Intelligence Index chart",
        "aria-pressed":String(pins.has(r.name))});
      svg.appendChild(c);
      pts.push({r:r,x:cx,y:cy,el:c});
    }

    // ---- direct labels, placed only where they collide with NOTHING ----
    // Real collision detection against every dot, every frontier segment, every
    // already-placed label and the plot edges. A label that cannot find a clear
    // slot is dropped entirely rather than shipped overlapping -- the tooltip
    // and the table still carry it, so nothing becomes unreachable. The one
    // exception is a pinned name, which falls back to a clamped placement that
    // accepts overlap: the reader asked for that label by name.
    const PAD=3, boxes=[];
    const hitsBox=(a,b)=> a.x < b.x+b.w+PAD && a.x+a.w+PAD > b.x &&
                          a.y < b.y+b.h+PAD && a.y+a.h+PAD > b.y;
    const hitsDot=(a,p)=>{                       // rect vs circle (r6 + 2 ring)
      const nx=Math.max(a.x,Math.min(p.x,a.x+a.w));
      const ny=Math.max(a.y,Math.min(p.y,a.y+a.h));
      return (p.x-nx)**2 + (p.y-ny)**2 < 81;
    };
    // Exact segment-vs-rectangle (Liang-Barsky). This was point-sampling along
    // the segment, which aliases: a line clipping a box corner between two
    // samples reads as clear, and one did at 1280px wide. Sampling cannot be
    // made safe by shrinking the step -- only by not sampling.
    const hitsSeg=(a,[x1,y1,x2,y2])=>{
      let t0=0, t1=1;
      const dx=x2-x1, dy=y2-y1;
      const p=[-dx,dx,-dy,dy];
      const q=[x1-a.x, a.x+a.w-x1, y1-a.y, a.y+a.h-y1];
      for(let i=0;i<4;i++){
        if(p[i]===0){ if(q[i]<0) return false; continue; }
        const r=q[i]/p[i];
        if(p[i]<0){ if(r>t1) return false; if(r>t0) t0=r; }
        else       { if(r<t0) return false; if(r<t1) t1=r; }
      }
      return true;
    };
    // exact squared distance from a point to a segment
    const segDist2=(x1,y1,x2,y2,px,py)=>{
      const dx=x2-x1, dy=y2-y1, L=dx*dx+dy*dy;
      let t = L ? ((px-x1)*dx+(py-y1)*dy)/L : 0;
      t = t<0 ? 0 : t>1 ? 1 : t;
      const qx=x1+t*dx, qy=y1+t*dy;
      return (px-qx)**2 + (py-qy)**2;
    };
    // Showing only the frontier means few enough points to name every one in
    // full. The empty regions a Pareto curve creates -- nothing is cheaper AND
    // smarter, so up-and-left of the curve is vacant -- are what make room for
    // long names. Labels may use the plot margins, but never leave the canvas.
    const full = st.sup;
    const PADX=4, PADY=2, leaders=[];
    const clear = a =>
      a.x>=4 && a.x+a.w<=W-4 && a.y>=T && a.y+a.h<=T+py &&
      !boxes.some(b=>hitsBox(a,b)) &&
      !pts.some(p=>hitsDot(a,p)) &&
      !segs.some(s=>hitsSeg(a,s)) &&
      !leaders.some(s=>hitsSeg(a,s));

    // A leader must not graze another dot or another label on its way across,
    // or the line appears to point at the wrong model -- which is exactly the
    // ambiguity the leaders exist to remove.
    const leaderClear=(x1,y1,x2,y2,own)=>{
      for(const p of pts){
        if(p===own) continue;
        if(segDist2(x1,y1,x2,y2,p.x,p.y) < 56) return false;
      }
      return !boxes.some(b=>hitsSeg(b,[x1,y1,x2,y2]));
    };

    // Pinned names first -- the reader asked for those explicitly, so they get
    // first claim on space; then the frontier, smartest first.
    const queue=[
      ...rows.filter(r=>pins.has(r.name)).map(r=>({r,pin:true})),
      ...[...frontier].sort((a,b)=> b.ii-a.ii)
                .filter(r=>!pins.has(r.name)).map(r=>({r,pin:false})),
    ];
    // The wide flag is pin||full (full = the st.sup frontier-only view) --
    // same predicate the capability charts spell pin||st.sup.
    const texts=assignLabels(queue, q=>q.pin||full);
    let dropped=0;
    for(const [i,{r,pin}] of queue.entries()){
      const cx=X(r.cost), cy=Y(r.ii), own=pts.find(p=>p.r===r);
      const wide=pin||full;                    // pinned names are never clipped
      const t=el("text",{class:"lbl"});
      t.textContent = texts[i];
      svg.appendChild(t);
      const w=t.getComputedTextLength(), h=11;

      // Candidates ordered by how far they sit from the dot, so a label only
      // drifts when its neighbourhood is genuinely occupied.
      // Offsets on both sides at several distances, then sorted so the nearest
      // clear slot wins -- a leader only gets long when everything closer is
      // genuinely occupied. The wide reach is what lets the frontier view name
      // all 21 points at narrower window sizes.
      const cands=[];
      const dyMax = wide ? 240 : 32;
      const dxs   = wide ? [18,70,130] : [18];
      for(let dy=-dyMax; dy<=dyMax; dy+=16)
        for(const dx of dxs){
          const d=Math.hypot(dx,dy);
          cands.push([cx+dx,   cy-h/2+dy, d]);   // to the right
          cands.push([cx-dx-w, cy-h/2+dy, d]);   // to the left
        }
      for(const dy of [-20,20,-34,34]) cands.push([cx-w/2, cy-h/2+dy, Math.abs(dy)]);
      cands.sort((a,b)=> a[2]-b[2]);

      let put=null;
      for(const [bx,by] of cands){
        const box={x:bx-PADX, y:by-PADY, w:w+2*PADX, h:h+2*PADY};
        if(!clear(box)) continue;
        // leader runs from the dot's edge to the nearest point on the box
        const nx=Math.max(box.x,Math.min(cx,box.x+box.w));
        const ny=Math.max(box.y,Math.min(cy,box.y+box.h));
        const d=Math.hypot(nx-cx,ny-cy)||1;
        const sx=cx+(nx-cx)/d*7, sy=cy+(ny-cy)/d*7;
        if(!leaderClear(sx,sy,nx,ny,own)) continue;
        put={bx,by,box,sx,sy,nx,ny}; break;
      }
      // A pin is an explicit reader request: when every clear candidate is
      // taken, clamp the label somewhere visible and accept the overlap --
      // the same last resort the capability charts extend to their pins.
      // Unpinned labels keep the refuse-and-drop behaviour above, so the
      // dropped counter only ever counts labels nobody asked for by name.
      if(!put&&pin){
        const bx=Math.max(7,Math.min(W-w-7,cx+10));
        const by=Math.max(T+PADY,Math.min(T+py-h-PADY,cy-h-6.5));
        const box={x:bx-PADX,y:by-PADY,w:w+2*PADX,h:h+2*PADY};
        const nx=Math.max(box.x,Math.min(cx,box.x+box.w));
        const ny=Math.max(box.y,Math.min(cy,box.y+box.h));
        const d=Math.hypot(nx-cx,ny-cy)||1;
        put={bx,by,box,sx:cx+(nx-cx)/d*7,sy:cy+(ny-cy)/d*7,nx,ny};
      }
      if(!put){ svg.removeChild(t); dropped++; continue; }

      // leader and box go behind the text, which was appended to measure it
      svg.insertBefore(el("line",{x1:put.sx,y1:put.sy,x2:put.nx,y2:put.ny,class:"lead"}),t);
      svg.insertBefore(el("rect",{x:put.box.x,y:put.box.y,width:put.box.w,
        height:put.box.h,rx:3,class:"lblbox"+(pin?" pinned":"")}),t);
      t.setAttribute("x",put.bx);
      t.setAttribute("y",put.by+h-2.5);        // y is the baseline
      boxes.push(put.box); leaders.push([put.sx,put.sy,put.nx,put.ny]);
    }
    if(dropped) console.warn("labels dropped for want of clear space:",dropped);
  }

  /* ---------- nearest-point hover (no pinpoint targets) ---------- */
  const tip=$("tip-intelligence"), svg=$("svg-intelligence");
  // nearest mark to the pointer, in viewBox units -- shared by hover and click
  // so both are as forgiving as each other
  function nearestAt(ev){
    if(!pts.length) return null;
    const b=svg.getBoundingClientRect(), sx=W/b.width, sy=H/b.height;
    const mx=(ev.clientX-b.left)*sx, my=(ev.clientY-b.top)*sy;
    let best=null, bd=Infinity;
    for(const p of pts){
      const d=(p.x-mx)**2+(p.y-my)**2;
      if(d<bd){ bd=d; best=p; }
    }
    return (best && bd<=60**2) ? best : null;
  }
  function moveTip(ev){
    const best=nearestAt(ev);
    if(!best){ hideTip(); return; }
    const b=svg.getBoundingClientRect();
    for(const p of pts) p.el.classList.toggle("fade", p!==best);
    const r=best.r;
    if(lastHovered.intelligence!==r){
      lastHovered.intelligence=r;
      tip.innerHTML="";
      const n=document.createElement("div"); n.className="tname";
      n.textContent=r.name; tip.appendChild(n);
      const rows=[["Intelligence Index",r.ii.toFixed(1)],
                  ["Cost per task",fmtCost(r.cost)],
                  ...secondaryRows(r)];
      rows.push(["On frontier", frontSet.has(r) ? "yes" : "no — superseded"]);
      if(r.dep) rows.push(["Vendor status","retired"]);
      for(const [k,v] of rows){
        const d=document.createElement("div"); d.className="trow";
        const a=document.createElement("span"); a.textContent=k;
        const c=document.createElement("span"); c.className="tv"; c.textContent=v;
        d.appendChild(a); d.appendChild(c); tip.appendChild(d);
      }
    }
    tip.classList.add("on");
    // Snap to the quadrant furthest from the pointer. The box therefore never
    // sits under the cursor, and its position depends only on which half of the
    // plot the pointer is in -- so it parks in a corner instead of jittering
    // along with every mouse move. Deliberately unclamped: it may hang outside
    // the plot rather than be squeezed back inside it.
    const M=14;
    const farRight=(ev.clientX-b.left) < b.width/2;
    const farDown =(ev.clientY-b.top)  < b.height/2;
    tip.style.left=(farRight ? b.width -tip.offsetWidth -M : M)+"px";
    tip.style.top =(farDown  ? b.height-tip.offsetHeight-M : M)+"px";
  }
  function hideTip(){
    tip.classList.remove("on");
    for(const p of pts) p.el.classList.remove("fade");
    lastHovered.intelligence=null;
  }
  svg.addEventListener("pointermove",moveTip);
  svg.addEventListener("pointerleave",hideTip);
  // click a point to stick its name on permanently; click again to release
  svg.addEventListener("click",ev=>{
    const hit=nearestAt(ev);
    if(!hit) return;
    if(pins.has(hit.r.name)) pins.delete(hit.r.name); else pins.add(hit.r.name);
    render();
  });
  svg.addEventListener("keydown",ev=>{
    if((ev.key!=="Enter"&&ev.key!==" ")||!ev.target.classList.contains("pt")) return;
    ev.preventDefault();
    const hit=pts.find(p=>p.el===ev.target); if(!hit) return;
    if(pins.has(hit.r.name)) pins.delete(hit.r.name); else pins.add(hit.r.name);
    focusAfterRender={key:"intelligence",name:hit.r.name};
    render();
  });

  /* ---------- coding, parameter-efficiency + agentic scatters ---------- */
  const extraPlots={};
  function drawCapability(key,rows,frontier){
    const cfg=PLOTS[key], chart=$(cfg.svg), NS="http://www.w3.org/2000/svg";
    while(chart.firstChild) chart.removeChild(chart.firstChild);
    const el=(n,a)=>{const e=document.createElementNS(NS,n);
      for(const k in a) e.setAttribute(k,a[k]); return e;};
    const w=Math.max(720,Math.round(chart.parentElement.getBoundingClientRect().width));
    const h=Math.max(380,(window.innerHeight||900)-160), l=62, rr=22, t=20, b=52;
    const px=w-l-rr, py=h-t-b;
    chart.setAttribute("viewBox","0 0 "+w+" "+h);
    if(!rows.length){
      const msg=el("text",{x:w/2,y:h/2,"text-anchor":"middle"});
      msg.textContent="No models match these filters."; chart.appendChild(msg);
      extraPlots[key]={w,h,pts:[],front:new Set()}; return;
    }
    const values=rows.map(r=>metricOf(r,key));
    const costs=values.map(m=>m.cost), scores=values.map(m=>m.score);
    const lo=Math.log10(Math.min(...costs)), hi=Math.log10(Math.max(...costs));
    const pad=(hi-lo)*.06||.3, x0=lo-pad, x1=hi+pad;
    const yMax=Math.min(100,Math.ceil((Math.max(...scores)+4)/10)*10);
    const yMin=Math.max(0,Math.floor((Math.min(...scores)-4)/10)*10);
    const X=c=>l+(Math.log10(c)-x0)/(x1-x0)*px;
    const Y=v=>t+py-(v-yMin)/(yMax-yMin)*py;
    for(let v=yMin;v<=yMax;v+=10){
      chart.appendChild(el("line",{x1:l,y1:Y(v),x2:l+px,y2:Y(v),
        stroke:"var(--grid)","stroke-width":1}));
      const tick=el("text",{x:l-9,y:Y(v)+3.5,"text-anchor":"end"});
      tick.textContent=String(v); chart.appendChild(tick);
    }
    const ylabel=el("text",{x:14,y:t+py/2,"text-anchor":"middle",
      transform:"rotate(-90 14 "+(t+py/2)+")"});
    ylabel.textContent=(key==="parameters"?"Intelligence Index":cfg.label)+" →";
    chart.appendChild(ylabel);
    for(let e=Math.floor(x0);e<=Math.ceil(x1);e++) for(const mult of [1,2,5]){
      const c=mult*Math.pow(10,e), lx=Math.log10(c);
      if(lx<x0||lx>x1) continue;
      chart.appendChild(el("line",{x1:X(c),y1:t,x2:X(c),y2:t+py,
        stroke:"var(--grid)","stroke-width":1}));
      const tick=el("text",{x:X(c),y:t+py+17,"text-anchor":"middle"});
      tick.textContent=key==="parameters"?fmtParams(c)
        :(c>=1?"$"+c:"$"+c.toFixed(c<.01?3:2));
      chart.appendChild(tick);
    }
    chart.appendChild(el("line",{x1:l,y1:t+py,x2:l+px,y2:t+py,
      stroke:"var(--axis)","stroke-width":1}));
    const xlabel=el("text",{x:l+px/2,y:h-13,"text-anchor":"middle"});
    xlabel.textContent=key==="parameters"
      ? "Total parameters (billions, log scale) →"
      : "Cost per "+cfg.label+" task (USD, log scale) →";
    chart.appendChild(xlabel);

    // The pass's frontier arrives already computed (#109); the Set keeps the
    // row-object membership the marks and tooltips read.
    const front=new Set(frontier);
    if(frontier.length>1){
      let d="M "+X(metricOf(frontier[0],key).cost)+" "+Y(metricOf(frontier[0],key).score);
      for(let i=1;i<frontier.length;i++){
        const m=metricOf(frontier[i],key); d+=" L "+X(m.cost)+" "+Y(m.score);
      }
      chart.appendChild(el("path",{d,fill:"none",stroke:"var(--frontier-line)",
        "stroke-width":1.5,"stroke-dasharray":"5 4","stroke-linejoin":"round"}));
    }
    const pts=[];
    for(const r of rows){
      const m=metricOf(r,key), x=X(m.cost), y=Y(m.score), on=front.has(r);
      // the de-emphasis gray is page-wide: a point off THIS chart's frontier
      // draws var(--muted) here and on the other three charts alike, while a
      // frontier point keeps its weights fill.
      const fill=on?fillOf(r):"var(--muted)";
      const mark=el("circle",{cx:x,cy:y,r:on?6:5,fill:fill,
        stroke:strokeOf(r),"stroke-width":2,
        class:"pt"+(pins.has(r.name)?" pinned":""),role:"button",tabindex:0,
        "aria-label":"Pin "+r.name+" on the "+cfg.label+" chart",
        "aria-pressed":String(pins.has(r.name))});
      chart.appendChild(mark); pts.push({r,x,y,el:mark});
    }

    // Pinned names get first claim on space, followed by frontier names. A pin
    // is an explicit request, so its full name is retained and a last-resort
    // placement remains visible even when the clear candidates are exhausted.
    const boxes=[];
    const queue=[
      ...rows.filter(r=>pins.has(r.name)).map(r=>({r,pin:true})),
      ...[...frontier].sort((a,b)=>metricOf(b,key).score-metricOf(a,key).score)
        .filter(r=>!pins.has(r.name)).map(r=>({r,pin:false})),
    ];
    // Same predicate as the intelligence chart: pin||st.sup. Only the text
    // source changes here -- placement (candidates, clear-checks, wide
    // offsets, drop-if-no-clear-slot) is untouched (#85).
    const texts=assignLabels(queue, q=>q.pin||st.sup);
    for(const [i,{r,pin}] of queue.entries()){
      const m=metricOf(r,key), x=X(m.cost), y=Y(m.score);
      const label=el("text",{class:"lbl"});
      label.textContent=texts[i];
      chart.appendChild(label);
      const tw=label.getComputedTextLength(), th=15;
      const candidates=[];
      const dyMax=pin?192:16, dxs=pin?[10,60,120]:[10];
      for(let dy=-dyMax;dy<=dyMax;dy+=16) for(const dx of dxs){
        candidates.push([x+dx,y+dy,Math.hypot(dx,dy)]);          // right
        candidates.push([x-tw-dx,y+dy,Math.hypot(tw+dx,dy)]);   // left
      }
      // Candidates ordered by how far they sit from the dot, so a label only
      // drifts as far as the crowd genuinely forces it. Walking generation
      // order instead let one blocked slot throw a label to the far side of
      // its dot while nearer slots on the same side sat clear (#84). Unlike
      // the intelligence chart's placer (9c74397), a left candidate scores
      // its far end rather than its near edge -- deliberate: these charts
      // draw no leader lines, so a label reaching across its dot to name it
      // from the left reads as another point's label, and stays the last
      // resort here.
      candidates.sort((a,b)=>a[2]-b[2]);
      let chosen=null;
      for(const [bx,by] of candidates){
        const box={x:bx-3,y:by-th+3,w:tw+6,h:th};
        if(box.x<4||box.x+box.w>w-4||box.y<t||box.y+box.h>t+py) continue;
        if(boxes.some(q=>box.x<q.x+q.w&&box.x+box.w>q.x&&box.y<q.y+q.h&&box.y+box.h>q.y)) continue;
        if(pts.some(p=>p.r!==r&&p.x>=box.x-7&&p.x<=box.x+box.w+7&&p.y>=box.y-7&&p.y<=box.y+box.h+7)) continue;
        chosen={bx,by,box}; break;
      }
      if(!chosen&&pin){
        const bx=Math.max(7,Math.min(w-tw-7,x+10));
        const by=Math.max(t+th-3,Math.min(t+py,y-9));
        chosen={bx,by,box:{x:bx-3,y:by-th+3,w:tw+6,h:th}};
      }
      if(!chosen){chart.removeChild(label);continue;}
      chart.insertBefore(el("rect",{x:chosen.box.x,y:chosen.box.y,width:chosen.box.w,
        height:chosen.box.h,rx:3,class:"lblbox"+(pin?" pinned":"")}),label);
      label.setAttribute("x",chosen.bx); label.setAttribute("y",chosen.by);
      boxes.push(chosen.box);
    }
    extraPlots[key]={w,h,pts,front};
  }

  function nearestCapability(key,ev){
    const plot=extraPlots[key], chart=$(PLOTS[key].svg);
    if(!plot||!plot.pts.length) return null;
    const box=chart.getBoundingClientRect(), sx=plot.w/box.width, sy=plot.h/box.height;
    const mx=(ev.clientX-box.left)*sx, my=(ev.clientY-box.top)*sy;
    let best=null, distance=Infinity;
    for(const p of plot.pts){
      const d=(p.x-mx)**2+(p.y-my)**2;
      if(d<distance){distance=d;best=p;}
    }
    return best&&distance<=60**2?best:null;
  }

  function hideCapabilityTip(key){
    $(PLOTS[key].tip).classList.remove("on");
    const plot=extraPlots[key]; if(plot) for(const p of plot.pts) p.el.classList.remove("fade");
    lastHovered[key]=null;
  }

  function moveCapabilityTip(key,ev){
    const hit=nearestCapability(key,ev), cfg=PLOTS[key], chart=$(cfg.svg), box=chart.getBoundingClientRect();
    if(!hit){hideCapabilityTip(key);return;}
    const plot=extraPlots[key], m=metricOf(hit.r,key), popup=$(cfg.tip);
    for(const p of plot.pts) p.el.classList.toggle("fade",p!==hit);
    if(lastHovered[key]!==hit.r){
      lastHovered[key]=hit.r;
      popup.innerHTML="";
      const name=document.createElement("div"); name.className="tname"; name.textContent=hit.r.name; popup.appendChild(name);
      const lines=key==="parameters"
        ? [["Intelligence Index",m.score.toFixed(1)],["Parameters",fmtParams(m.cost)],
           ...secondaryRows(hit.r)]
        : [[cfg.label,m.score.toFixed(1)],["Cost per task",fmtCost(m.cost)],
           ...secondaryRows(hit.r)];
      lines.push([key==="parameters" ? "On parameter frontier" : "On frontier",
                  plot.front.has(hit.r) ? "yes" : "no — superseded"]);
      if(hit.r.dep) lines.push(["Vendor status","retired"]);
      for(const [k,v] of lines){
        const row=document.createElement("div"); row.className="trow";
        const a=document.createElement("span"); a.textContent=k;
        const b=document.createElement("span"); b.className="tv"; b.textContent=v;
        row.appendChild(a); row.appendChild(b); popup.appendChild(row);
      }
    }
    popup.classList.add("on");
    const margin=14, right=(ev.clientX-box.left)<box.width/2, down=(ev.clientY-box.top)<box.height/2;
    popup.style.left=(right?box.width-popup.offsetWidth-margin:margin)+"px";
    popup.style.top=(down?box.height-popup.offsetHeight-margin:margin)+"px";
  }

  for(const key of ["coding","agentic","parameters"]){
    const chart=$(PLOTS[key].svg);
    chart.addEventListener("pointermove",ev=>moveCapabilityTip(key,ev));
    chart.addEventListener("pointerleave",()=>hideCapabilityTip(key));
    chart.addEventListener("click",ev=>{
      const hit=nearestCapability(key,ev); if(!hit) return;
      if(pins.has(hit.r.name)) pins.delete(hit.r.name); else pins.add(hit.r.name);
      render();
    });
    chart.addEventListener("keydown",ev=>{
      if((ev.key!=="Enter"&&ev.key!==" ")||!ev.target.classList.contains("pt")) return;
      ev.preventDefault();
      const plot=extraPlots[key], hit=plot&&plot.pts.find(p=>p.el===ev.target);
      if(!hit) return;
      if(pins.has(hit.r.name)) pins.delete(hit.r.name); else pins.add(hit.r.name);
      focusAfterRender={key,name:hit.r.name};
      render();
    });
  }

  /* ---------- tables ---------- */
  function fillFrontiers(metricRows,fronts){
    const tb=$("fTable").querySelector("tbody");
    tb.innerHTML="";
    for(const key of Object.keys(METRICS)){
      for(const r of fronts[key].slice().reverse()){
        const m=metricOf(r,key), tr=document.createElement("tr");
        const add=(txt,cls)=>{const td=document.createElement("td");
          if(cls) td.className=cls; td.textContent=txt; tr.appendChild(td);};
        add(METRICS[key].label); add(r.name,"name"); add(show(r.creator));
        add(m.score.toFixed(1),"n"); add(fmtCost(m.cost),"n");
        // Zero is a legal AA score (#146); $/point at 0 capability is not
        // a number -- em dash, matching the static render, never
        // "$Infinity".
        add(m.score?"$"+(m.cost/m.score).toFixed(4):"—","n");
        const td=document.createElement("td");
        const sp=document.createElement("span"); sp.className="tag";
        sp.textContent=weightsOf(r);
        td.appendChild(sp); tr.appendChild(td); tb.appendChild(tr);
      }
    }
  }

  function sortValue(r,key){
    const fields={
      codingScore:["coding","score"],codingCost:["coding","cost"],
      ii:["intelligence","score"],cost:["intelligence","cost"],
      agenticScore:["agentic","score"],agenticCost:["agentic","cost"],
    };
    if(fields[key]){
      const [metric,field]=fields[key], m=metricOf(r,metric);
      return m?m[field]:null;
    }
    if(key==="params") return r.params;
    return r[key];
  }

  function fillTable(metricRows,fronts){
    // The pass's frontier arrives already computed (#109); one Set per metric
    // over the threaded arrays replaces fillTable's own four recomputations
    // (coding, intelligence and agentic in the METRICS loop, parameters
    // spelled out after it).
    const frontSets={};
    for(const key of Object.keys(fronts)) frontSets[key]=new Set(fronts[key]);
    const rows=[...new Set(Object.values(metricRows).flat())];
    const k=st.sortK, dir=st.sortDir;
    $("tbl").querySelectorAll("th[data-k]").forEach(th=>
      th.setAttribute("aria-sort",th.dataset.k===k?(dir===1?"ascending":"descending"):"none"));
    const sorted=[...rows].sort((a,b)=>{
      let x=sortValue(a,k), y=sortValue(b,k);
      if(x==null&&y==null) return 0;
      if(x==null) return 1;
      if(y==null) return -1;
      if(typeof x==="string") return dir*x.localeCompare(y);
      return dir*(x-y);
    });
    const tb=$("tbl").querySelector("tbody");
    tb.innerHTML="";
    // An empty filtered slice must say so where the table was: a silent
    // zero-row body reads as a broken page. The live region announces the
    // state change rather than leaving the reader to count headers.
    const empty=$("tblEmpty");
    if(sorted.length){ empty.hidden=true; empty.textContent=""; }
    else { empty.textContent="No models match the current filters"; empty.hidden=false; }
    for(const r of sorted){
      const tr=document.createElement("tr");
      const add=(txt,cls)=>{const td=document.createElement("td");
        if(cls) td.className=cls; td.textContent=txt; tr.appendChild(td);};
      const nameTd=document.createElement("td");
      nameTd.className="name";
      nameTd.appendChild(document.createTextNode(r.name+" "));
      if(r.dep){const s=document.createElement("span");
        s.className="tag"; s.textContent="vendor-retired"; nameTd.appendChild(s);}
      tr.appendChild(nameTd);
      add(show(r.creator));
      for(const key of Object.keys(METRICS)){
        const m=metricOf(r,key), score=document.createElement("td"), cost=document.createElement("td");
        score.className="n"; cost.className="n";
        score.textContent = m ? m.score.toFixed(1) : "—";
        cost.textContent = m ? fmtCost(m.cost) : "—";
        if(m&&frontSets[key].has(r)){
          score.appendChild(document.createTextNode(" "));
          const tag=document.createElement("span"); tag.className="tag f";
          tag.textContent="frontier"; score.appendChild(tag);
        }
        tr.appendChild(score); tr.appendChild(cost);
        if(key==="intelligence"){
          const parameters=document.createElement("td");
          parameters.className="n";
          parameters.textContent = fmtParams(r.params);
          if(metricOf(r,"parameters")&&frontSets.parameters.has(r)){
            parameters.appendChild(document.createTextNode(" "));
            const tag=document.createElement("span"); tag.className="tag f";
            tag.textContent="parameter frontier"; parameters.appendChild(tag);
          }
          tr.appendChild(parameters);
        }
      }
      add(r.pin==null?"—":"$"+r.pin,"n");
      add(r.pout==null?"—":"$"+r.pout,"n");
      add(r.tps==null?"—":String(r.tps),"n");
      add(fmtCtx(r.ctx),"n");
      add(show(r.rel));
      add(weightsOf(r));
      tb.appendChild(tr);
    }
  }

  $("tbl").querySelectorAll("th[data-k]").forEach(th=>{
    th.setAttribute("tabindex","0");
    const activate=()=>{
      const k=th.dataset.k;
      if(st.sortK===k) st.sortDir*=-1;
      else { st.sortK=k; st.sortDir = (k==="name"||k==="creator"||k==="rel") ? 1 : -1; }
      // A sort reorders rows, not points: the four charts are a pure function
      // of the filter state, which a sort never touches, so their DOM is
      // provably identical and redrawing it is pure loss (#84's no-op pin --
      // labels must not move -- holds trivially). Only the tables refill
      // here; fillTable rewrites aria-sort, and the count line is
      // sort-invariant. An open tooltip closes exactly as render() closes
      // it -- row identity is sort-invariant, but a reader who just
      // reordered the table is no longer pointing at a chart. The chips,
      // lab, search and pin paths keep the full render(), which stays the
      // only place charts are drawn.
      const {views,fronts}=computePass();
      fillFrontiers(views,fronts); fillTable(views,fronts);
      hideTip(); hideCapabilityTip("coding"); hideCapabilityTip("parameters"); hideCapabilityTip("agentic");
    };
    th.addEventListener("click",activate);
    th.addEventListener("keydown",ev=>{
      if(ev.key!=="Enter"&&ev.key!==" ") return;
      ev.preventDefault(); activate();
    });
  });

  /* ---------- copy ---------- */
  function flash(m){const t=$("toast"); t.textContent=m; t.classList.add("show");
    setTimeout(()=>t.classList.remove("show"),1700);}
  function clip(text,label){
    if(navigator.clipboard&&navigator.clipboard.writeText)
      navigator.clipboard.writeText(text).then(()=>flash(label),()=>fb(text,label));
    else fb(text,label);
  }
  function fb(text,label){
    const ta=document.createElement("textarea"); ta.value=text;
    document.body.appendChild(ta); ta.select();
    try{document.execCommand("copy");}catch(_){}
    document.body.removeChild(ta); flash(label);
  }
  $("copyMd").addEventListener("click",()=>{
    const views=metricViews(), rows=[...new Set(Object.values(views).flat())];
    const val=(r,key,field)=>metricOf(r,key)?(field==="score"?metricOf(r,key).score.toFixed(1):fmtCost(metricOf(r,key).cost)):"—";
    const head="| Model | Lab | Coding Agent | Coding Agent $/task | Intelligence | Intelligence $/task | Parameters | GDPval-AA | GDPval $/task | $/1M in | $/1M out | Context | Weights |\n"
              +"|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n";
    // Every cell goes through mdCell, so a captured name or lab carrying a
    // pipe, backtick or newline round-trips as text instead of restructuring
    // the pasted row.
    const body=rows.map(r=>"| "+[r.name,show(r.creator),
      val(r,"coding","score"),val(r,"coding","cost"),
      val(r,"intelligence","score"),val(r,"intelligence","cost"),
      fmtParams(r.params),
      val(r,"agentic","score"),val(r,"agentic","cost"),
      r.pin==null?"—":"$"+r.pin, r.pout==null?"—":"$"+r.pout,
      fmtCtx(r.ctx), weightsOf(r)].map(mdCell).join(" | ")+" |").join("\n");
    clip(head+body+"\n\nSource: Artificial Analysis (artificialanalysis.ai), captured __CAPTURED__.",
         "✓ "+rows.length+" rows copied");
  });
  $("copyJson").addEventListener("click",()=>{
    const views=metricViews(), rows=[...new Set(Object.values(views).flat())];
    // same em dash as the page: an absent lab exports as "—", not ""
    clip(JSON.stringify({source:"artificialanalysis.ai",captured:"__CAPTURED__",
      models:rows.map(r=>Object.assign({},r,{creator:show(r.creator)}))},null,2),
      "✓ JSON copied");
  });

  /* ---------- wiring ---------- */
  function metricViews(){
    return {
      coding:metricSlice("coding"),
      intelligence:metricSlice("intelligence"),
      parameters:metricSlice("parameters"),
      agentic:metricSlice("agentic"),
    };
  }

  // One frontier computation per metric per render pass (#109). These arrays
  // are the page's single definition of the undominated layer -- the chart
  // line, the frontier table, the table tag and the Hide-superseded chip all
  // read them, so they cannot disagree the way a separately precomputed flag
  // could. frontierMetric is a pure function of (rows, key), and every
  // consumer used to recompute it over the very views this reads -- draw, each
  // drawCapability, fillFrontiers and fillTable (twice for parameters) -- so
  // threading the result down changes where the work runs, not which rows it
  // returns: a subset of the same row objects reaches every consumer, and the
  // Set-of-row-objects semantics are untouched. The pure function itself is
  // unchanged; only the recomputation went away.
  function computePass(){
    const views=metricViews();
    const fronts={};
    for(const key of Object.keys(views)) fronts[key]=frontierMetric(views[key],key);
    return {views,fronts};
  }

  function render(){
    // Unpinning the last model would leave "Only pinned" showing an empty plot
    // with no visible way out, since the chip itself hides with the pins.
    if(!pins.size && st.only){
      st.only=false; $("fOnly").setAttribute("aria-pressed","false");
    }
    const {views,fronts}=computePass(), union=[...new Set(Object.values(views).flat())];
    const bits=[views.coding.length+" coding",views.intelligence.length+" intelligence",
      views.parameters.length+" parameter",views.agentic.length+" agentic"];
    if(st.eff) bits.push("effort levels dumped per metric");
    if(st.sup) bits.push("frontiers only");
    // Pins are never cleared by filtering or searching -- they are keyed by
    // name, so a model that is filtered out keeps its pin and gets its label
    // back the moment it returns to the view. Only the button clears them.
    if(pins.size){
      const shown=union.filter(r=>pins.has(r.name)).length;
      bits.push(pins.size+" pinned"+(shown<pins.size ? " ("+shown+" in view)" : ""));
    }
    $("fClear").hidden = pins.size===0;
    $("fOnly").hidden  = pins.size===0;
    $("count").textContent=bits.join(" · ");
    drawCapability("coding",views.coding,fronts.coding);
    draw(views.intelligence,fronts.intelligence);
    drawCapability("parameters",views.parameters,fronts.parameters);
    drawCapability("agentic",views.agentic,fronts.agentic);
    fillFrontiers(views,fronts); fillTable(views,fronts); hideTip();
    hideCapabilityTip("coding"); hideCapabilityTip("parameters"); hideCapabilityTip("agentic");
    if(focusAfterRender){
      const request=focusAfterRender;
      focusAfterRender=null;
      const plot=request.key==="intelligence"?{pts}:extraPlots[request.key];
      const replacement=plot&&plot.pts.find(p=>p.r.name===request.name);
      if(replacement) replacement.el.focus();
    }
  }
  const toggle=(id,key)=>$(id).addEventListener("click",()=>{
    st[key]=!st[key]; $(id).setAttribute("aria-pressed",String(st[key])); render();});
  toggle("fProp","prop"); toggle("fOpen","open"); toggle("fUnk","unk");
  toggle("fSup","sup");   toggle("fEff","eff");   toggle("fReas","reas");
  toggle("fOnly","only");
  $("fClear").addEventListener("click",()=>{ pins.clear(); render(); });
  $("fLab").addEventListener("change",e=>{st.lab=e.target.value; render();});
  $("fQ").addEventListener("input",e=>{st.q=e.target.value; render();});
  // re-render on resize so the plot re-fits and labels re-place for the new width
  let rzT=null;
  window.addEventListener("resize",()=>{
    hideTip(); hideCapabilityTip("coding"); hideCapabilityTip("parameters"); hideCapabilityTip("agentic");
    clearTimeout(rzT); rzT=setTimeout(render,150);
  });
  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    # Argparse lives here rather than in main() so that the direct main()
    # callers -- the test suite drives it with pytest's argv still live --
    # keep building whatever capture they point the module paths at.
    ap = argparse.ArgumentParser(
        description="Build out/frontier-models.html from the AA captures "
                    "in data/ (no arguments needed).")
    ap.parse_args()
    main()
