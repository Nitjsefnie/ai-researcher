#!/usr/bin/env python3
"""Semantic diff between two artificialanalysis.ai captures.

`git diff data/aa-raw-models.json` is useless for a refresh review: AA re-samples
throughput and latency on every crawl, so ~half the records churn on numbers that
mean nothing for this page. This differ compares captures *by model id* and sorts
every changed field into a class, then reports only the classes that can change
what the page says:

  significant  intelligence index, cost per task, price, context, deprecation,
               release date, licence, and the component benchmark scores that
               explain an index move -- always reported
  jitter       re-sampled speed/latency. Only the two speed numbers the page
               actually renders (see SPEED_SHOWN) survive at all, and only above
               --speed-tol; every other percentile/TTFT/e2e field is discarded
               outright because nothing downstream reads it
  derived      breakdowns strictly beneath a headline already reported -- token
               counts, per-eval cost splits, blended prices, gdpval CIs.
               Discarded unless --derived
  cosmetic     lab branding (colour, logo) -- always discarded, counted only

It also recomputes every Pareto layer the page draws -- one per scatter, in page order:
coding, intelligence, agentic and parameter-efficiency -- on either side, using build.py's
own `undominated`, so "who entered / left the frontier" is answered by the same
function the page uses rather than a second implementation of the rule. The four
move independently: a model can join one while sitting dominated on the rest.

Usage:
    python3 scripts/diff_aa.py                    # HEAD's capture vs the working tree
    python3 scripts/diff_aa.py OLD.json NEW.json  # two files
    python3 scripts/diff_aa.py --speed-tol 0.1    # loosen the speed filter
    python3 scripts/diff_aa.py --derived          # add the component breakdowns
    python3 scripts/diff_aa.py --all              # show every class, no filtering
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import build_rows, undominated  # noqa: E402

RAW = ROOT / "data" / "aa-raw-models.json"

# Re-measured every crawl; a different number is a new sample of the same thing,
# not news. Matched against the LAST segment of the flattened field path.
JITTER = re.compile(
    r"(TokensPerSecond|TimeToFirst\w*Seconds|ResponseTimeSeconds"
    r"|ReasoningTimeSeconds|OutputSpeed|TimePerTask)$"
)

# The only two re-sampled speed numbers build_rows() carries onto the page
# (build.py: "tps" and "secs"). Every other jitter field is invisible downstream,
# so a change in one cannot alter the artifact and is dropped without a threshold.
SPEED_SHOWN = {"medianOutputTokensPerSecond", "intelligenceIndexTimePerTask"}

# Lab branding churn -- AA reshuffles logo colours; never a finding.
COSMETIC = {"modelCreatorColor", "modelCreatorLogo"}

# Components of a headline this differ already reports. They move whenever the
# headline moves, so listing them restates one finding a dozen times.
DERIVED_ROOTS = {
    "evalTokenCounts",                    # per-eval token tallies -> cost
    "intelligenceIndexTokenCounts",       # their sum
    "intelligenceIndexOutputTokensPerTask",
    "gdpvalBreakdown",                    # elo + CIs behind gdpvalNormalized
}
DERIVED_EXACT = {
    # Whole-run cost, in dollars-per-index-run; cost.total per task is the headline.
    "intelligenceIndexCostTotal", "intelligenceIndexCostInput",
    "intelligenceIndexCostOutput", "intelligenceIndexCostReasoning",
    "intelligenceIndexCostAnswer",
}


def is_derived(path):
    head = path.split(".", 1)[0]
    if head in DERIVED_ROOTS or path in DERIVED_EXACT:
        return True
    # Five fixed input:output blends of price1mInput/OutputTokens, both reported.
    if head.startswith("price1mBlended"):
        return True
    # cost.total is the metric; every sibling is one of its addends.
    if path.startswith("intelligenceIndexCostPerTask.") and path != \
            "intelligenceIndexCostPerTask.cost.total":
        return True
    return False


def load(spec):
    """A path, or `git:REV` for a blob out of history."""
    if spec.startswith("git:"):
        rev = spec[4:]
        out = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{rev}:data/aa-raw-models.json"],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            sys.exit(f"cannot read {spec}: {out.stderr.strip()}")
        return json.loads(out.stdout)
    return json.loads(Path(spec).read_text(encoding="utf-8"))


def flatten(value, prefix=""):
    """Dotted leaf paths. Lists stay whole -- their order is AA's, not ours."""
    if isinstance(value, dict):
        flat = {}
        for k, v in value.items():
            flat.update(flatten(v, f"{prefix}.{k}" if prefix else k))
        return flat
    return {prefix: value}


def classify(path):
    leaf = path.rsplit(".", 1)[-1]
    if leaf in COSMETIC:
        return "cosmetic"
    if JITTER.search(leaf):
        return "jitter" if leaf in SPEED_SHOWN else "jitter-unused"
    if is_derived(path):
        return "derived"
    return "significant"


def rel_change(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if a == 0:
            return None if b == 0 else float("inf")
        return abs(b - a) / abs(a)
    return None


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"))
    return str(v)


def delta_note(a, b):
    rc = rel_change(a, b)
    if rc is None or rc == float("inf"):
        return ""
    return f"  ({b - a:+.6g}, {rc * 100:+.2f}%)" if rc else ""


def frontier_names(models, collapse=False):
    rows = build_rows(models)
    if collapse:
        ceiling = {}
        for r in rows:
            c = ceiling.get(r["base"])
            if not c or r["ii"] > c["ii"] or (r["ii"] == c["ii"] and r["cost"] < c["cost"]):
                ceiling[r["base"]] = r
        rows = list(ceiling.values())
    return {r["name"]: r for r in undominated(rows)}, rows


# The page draws four scatters (sections 1-4), each with its own Pareto layer,
# and they move independently -- a model can join one while sitting dominated on
# the others. Diffing only the headline left three of the four unreviewed.
# label -> (metric key, x-axis formatter)
CHART_FRONTIERS = (
    ("coding", "coding", lambda v: f"${v:.2f}/task"),
    ("agentic", "agentic", lambda v: f"${v:.2f}/task"),
    ("parameter-efficiency", "parameters", lambda v: fmt_params(v)),
)


def fmt_params(b):
    return f"{b / 1000:.1f}T".replace(".0T", "T") if b >= 1000 else f"{b:g}B"


def chart_frontier(models, metric):
    """One chart's Pareto layer, via build.py's own `undominated`.

    build_rows() seats metrics entries for the three cost-based scatters but not
    for the parameter one, so size stands in for cost there. Either way the
    dominance rule itself is never spelled a second time. Eligibility differs per
    chart -- the parameter layer only sees models AA discloses a size for, so it
    is drawn over a much smaller set than the cost layers.
    """
    rows = build_rows(models)
    if metric == "parameters":
        rows = [r for r in rows if r.get("params") and r.get("ii") is not None]
        for r in rows:
            r["metrics"]["parameters"] = {"score": r["ii"], "cost": r["params"]}
    else:
        rows = [r for r in rows if r["metrics"].get(metric)]
    return {r["name"]: r for r in undominated(rows, metric)}, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", nargs="?", default="git:HEAD",
                    help="old capture: a path, or git:REV (default git:HEAD)")
    ap.add_argument("new", nargs="?", default=str(RAW),
                    help=f"new capture (default {RAW.relative_to(ROOT)})")
    ap.add_argument("--speed-tol", type=float, default=0.25, metavar="X",
                    help="report a rendered speed field (%s) only when it moved by "
                         "more than X relative (default 0.25 = 25%%; 0 shows all). "
                         "Speed fields the page never renders are dropped regardless."
                         % ", ".join(sorted(SPEED_SHOWN)))
    ap.add_argument("--tol", type=float, default=0.0, metavar="X",
                    help="same threshold for significant numeric fields (default 0 = "
                         "report any change)")
    ap.add_argument("--derived", action="store_true",
                    help="also show breakdowns beneath a reported headline")
    ap.add_argument("--all", action="store_true",
                    help="no filtering at all -- every changed field, every class")
    args = ap.parse_args()

    old, new = load(args.old), load(args.new)
    O = {m["id"]: m for m in old}
    N = {m["id"]: m for m in new}

    print(f"old: {args.old}  ({len(old)} models)")
    print(f"new: {args.new}  ({len(new)} models)")

    added = [N[i] for i in N if i not in O]
    removed = [O[i] for i in O if i not in N]

    def line(m):
        rows = {r["name"]: r for r in build_rows([m])}
        r = rows.get(m.get("name"))
        ii = f"{r['ii']:.1f}" if r else fmt(m.get("intelligenceIndex"))
        cost = f"${r['cost']:.2f}" if r else "—"
        return (f"{m.get('name')}  [{m.get('modelCreatorName')}]  "
                f"II {ii}  cost/task {cost}"
                f"{'  open-weights' if m.get('isOpenWeights') else ''}"
                f"{'  RETIRED' if m.get('deprecated') else ''}")

    print(f"\n== models added: {len(added)}")
    for m in sorted(added, key=lambda m: -(m.get("intelligenceIndex") or 0)):
        print(f"  + {line(m)}")
    print(f"== models removed: {len(removed)}")
    for m in sorted(removed, key=lambda m: -(m.get("intelligenceIndex") or 0)):
        print(f"  - {line(m)}")

    suppressed = dict.fromkeys(
        ("jitter", "jitter-unused", "cosmetic", "derived", "below-tol"), 0)
    changed_models = 0
    speed_moves = []
    print("\n== field changes")
    for i in sorted(N, key=lambda i: -(N[i].get("intelligenceIndex") or 0)):
        if i not in O:
            continue
        fa, fb = flatten(O[i]), flatten(N[i])
        hits = []
        for path in sorted(set(fa) | set(fb)):
            a, b = fa.get(path), fb.get(path)
            if a == b:
                continue
            cls = classify(path)
            if not args.all:
                if cls in ("cosmetic", "jitter-unused") or (
                        cls == "derived" and not args.derived):
                    suppressed[cls] += 1
                    continue
                rc = rel_change(a, b)
                tol = args.speed_tol if cls == "jitter" else args.tol
                if rc is not None and rc <= tol:
                    suppressed["jitter" if cls == "jitter" else "below-tol"] += 1
                    continue
                # A surviving speed re-sample is still a different KIND of news
                # from a price or score move -- report it apart, not interleaved.
                if cls == "jitter":
                    speed_moves.append((N[i], path, a, b))
                    continue
            hits.append((path, cls, a, b))
        if not hits:
            continue
        changed_models += 1
        print(f"\n  {N[i].get('name')}  [{N[i].get('modelCreatorName')}]")
        for path, cls, a, b in hits:
            tag = "" if cls == "significant" else f" <{cls}>"
            print(f"    {path}{tag}: {fmt(a)} -> {fmt(b)}{delta_note(a, b)}")
    if not changed_models:
        print("  (none)")

    if speed_moves:
        print(f"\n== rendered speed re-sampled by more than "
              f"{args.speed_tol * 100:.0f}%: {len(speed_moves)} value(s), "
              f"{len({m['id'] for m, _, _, _ in speed_moves})} model(s)")
        for m, path, a, b in speed_moves:
            print(f"  {m.get('name')}  [{m.get('modelCreatorName')}]  "
                  f"{path}: {fmt(a)} -> {fmt(b)}{delta_note(a, b)}")

    for collapse, label in ((False, "expanded"), (True, "effort-collapsed")):
        fo, rows_o = frontier_names(old, collapse)
        fn, rows_n = frontier_names(new, collapse)
        entered = [n for n in fn if n not in fo]
        left = [n for n in fo if n not in fn]
        print(f"\n== efficient frontier ({label}): {len(fo)} -> {len(fn)} "
              f"of {len(rows_o)} -> {len(rows_n)} plotted")
        for n in sorted(entered, key=lambda n: -fn[n]["ii"]):
            r = fn[n]
            print(f"  + {n}  II {r['ii']:.1f}  ${r['cost']:.2f}/task")
        for n in sorted(left, key=lambda n: -fo[n]["ii"]):
            r = fo[n]
            print(f"  - {n}  II {r['ii']:.1f}  ${r['cost']:.2f}/task")
        if not entered and not left:
            print("  (unchanged)")

    for label, metric, fmt_x in CHART_FRONTIERS:
        fo, rows_o = chart_frontier(old, metric)
        fn, rows_n = chart_frontier(new, metric)
        entered = [n for n in fn if n not in fo]
        left = [n for n in fo if n not in fn]
        print(f"\n== {label} frontier: {len(fo)} -> {len(fn)} "
              f"of {len(rows_o)} -> {len(rows_n)} plotted")
        for sign, names, side in (("+", entered, fn), ("-", left, fo)):
            for n in sorted(names, key=lambda n: -side[n]["metrics"][metric]["score"]):
                m = side[n]["metrics"][metric]
                print(f"  {sign} {n}  {m['score']:.1f}  {fmt_x(m['cost'])}")
        if not entered and not left:
            print("  (unchanged)")

    if not args.all:
        print(f"\ndiscarded: {suppressed['jitter-unused']} re-sampled speed/latency "
              f"values the page never renders, "
              f"{suppressed['jitter']} rendered speed moves <= "
              f"{args.speed_tol * 100:.0f}%, "
              f"{suppressed['derived']} derived breakdown values, "
              f"{suppressed['cosmetic']} cosmetic, "
              f"{suppressed['below-tol']} other numeric moves <= {args.tol * 100:.0f}%")


if __name__ == "__main__":
    main()
