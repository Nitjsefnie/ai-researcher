#!/usr/bin/env python3
"""Build out/frontier-models.html from data/aa-raw-models.json.

Single deliverable: intelligence (AA Intelligence Index) vs cost per task,
sourced exclusively from artificialanalysis.ai.

Usage:  python3 build.py
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "data" / "aa-raw-models.json"
OUT = ROOT / "out" / "frontier-models.html"

# AA Intelligence Index v4.1 component evals, as listed on the source site.
INDEX_EVALS = [
    "GDPval-AA v2", "τ³-Banking", "Terminal-Bench v2.1", "SciCode",
    "Humanity's Last Exam", "GPQA Diamond", "CritPt", "AA-Omniscience", "AA-LCR",
]


# AA encodes the effort knob in the model name; there is no field for it. The
# trailing parenthetical is one of three things -- a bare effort level "(high)",
# an effort clause inside a config list "(Adaptive Reasoning, Max Effort)", or
# something that is not effort at all "(Reasoning)", "(Non-reasoning)",
# "(Jan '25)". Only the effort component is stripped; the rest identifies a
# genuinely different configuration and must survive.
EFFORT = re.compile(r"^(minimal|low|medium|high|xhigh|max)(\s+effort)?$", re.I)


def split_effort(name):
    """-> (base name without the effort knob, effort label or None)"""
    found = []

    def fix(m):
        kept = []
        for part in m.group(1).split(","):
            part = part.strip()
            if EFFORT.match(part):
                found.append(part)
            else:
                kept.append(part)
        return " (" + ", ".join(kept) + ")" if kept else ""

    base = re.sub(r"\s*\(([^)]*)\)", fix, name).strip()
    label = found[0].lower().replace(" effort", "") if found else None
    return base, label


def num(v):
    return v if isinstance(v, (int, float)) else None


def cost_per_task(m):
    """AA nests this: intelligenceIndexCostPerTask.cost.total (USD)."""
    outer = m.get("intelligenceIndexCostPerTask")
    if not isinstance(outer, dict):
        return None
    inner = outer.get("cost")
    if not isinstance(inner, dict):
        return None
    return num(inner.get("total"))


def build_rows(models):
    rows = []
    for m in models:
        ii, ct = num(m.get("intelligenceIndex")), cost_per_task(m)
        if ii is None or ct is None or ct <= 0:
            continue
        base, eff = split_effort(m.get("name") or "")
        rows.append({
            "name": m.get("name") or "",
            "base": base,
            "eff": eff,
            "creator": m.get("modelCreatorName") or "",
            "country": m.get("modelCreatorCountry") or "",
            "ii": round(ii, 2),
            "cost": round(ct, 4),
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
        })
    rows.sort(key=lambda r: (-r["ii"], r["cost"]))
    return rows


def undominated(rows):
    """The single Pareto layer -- the page's one and only definition of
    'superseded'. A model is superseded when some other model is at least as
    smart AND at least as cheap (strictly better on one of the two). Exact ties
    survive together: neither strictly beats the other."""
    return [
        r for r in rows
        if not any(
            o is not r
            and o["ii"] >= r["ii"] and o["cost"] <= r["cost"]
            and (o["ii"] > r["ii"] or o["cost"] < r["cost"])
            for o in rows
        )
    ]


def main():
    models = json.loads(RAW.read_text(encoding="utf-8"))
    rows = build_rows(models)

    # Reported only -- the page recomputes this layer against whatever the
    # filters leave, so nothing is baked into the data.
    front = undominated(rows)
    kept = {r["name"] for r in front}
    retired_and_beaten = sum(1 for r in rows if r["dep"] and r["name"] not in kept)

    # What collapsing effort levels actually costs, measured rather than assumed.
    # Turning a model down makes it cheaper AND dumber, so a low-effort variant is
    # NOT dominated by its high-effort twin -- effort levels are real operating
    # points and collapsing them deletes genuine frontier positions.
    ceiling = {}
    for r in rows:
        c = ceiling.get(r["base"])
        if not c or r["ii"] > c["ii"] or (r["ii"] == c["ii"] and r["cost"] < c["cost"]):
            ceiling[r["base"]] = r
    sib_beaten = sum(
        1 for r in rows
        if any(o is not r and o["base"] == r["base"]
               and o["ii"] >= r["ii"] and o["cost"] <= r["cost"]
               and (o["ii"] > r["ii"] or o["cost"] < r["cost"])
               for o in rows)
    )
    front_collapsed = undominated(list(ceiling.values()))

    captured = dt.date.today().isoformat()
    stats = {
        "total": len(models),
        "plotted": len(rows),
        "creators": len({r["creator"] for r in rows}),
        "open": sum(1 for r in rows if r["open"]),
        "prop": sum(1 for r in rows if not r["open"]),
        "captured": captured,
        "evals": INDEX_EVALS,
        "bases": len(ceiling),
        "sibBeaten": sib_beaten,
        "frontFull": len(front),
        "frontCollapsed": len(front_collapsed),
    }
    payload = json.dumps({"rows": rows, "stats": stats}, separators=(",", ":"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__DATA__", payload).replace("__CAPTURED__", captured),
                   encoding="utf-8")
    dep = sum(1 for r in rows if r["dep"])
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {stats['plotted']} models plotted "
          f"({stats['prop']} proprietary / {stats['open']} open-weights, "
          f"{stats['creators']} labs)")
    print(f"  {len(front)} undominated, {len(rows) - len(front)} superseded by metric")
    print(f"  of {dep} vendor-retired models, {retired_and_beaten} are also beaten on the "
          f"numbers ({'metric filter subsumes the vendor flag' if retired_and_beaten == dep else 'MISMATCH -- some retired model is still undominated'})")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Frontier models &mdash; intelligence vs cost per task</title>
<style>
  .viz-root, body {
    color-scheme: light;
    --surface-1:#fcfcfb; --plane:#f9f9f7;
    --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
    --series-prop:#2a78d6; --series-open:#eb6834; --dim:#a9a7a0;
    --accent:#2a78d6;
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
  .chip:hover{border-color:var(--accent)}
  .chip[aria-pressed="true"]{border-color:var(--accent);color:var(--text-primary);
    box-shadow:0 0 0 1px var(--accent) inset}
  .chip .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
  .chip .dot.prop{background:var(--series-prop)}
  .chip .dot.open{background:var(--series-open)}
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
  /* a pinned point keeps a dark ring so you can see what you have stuck down */
  .pt.pinned{stroke:var(--text-primary);stroke-width:2}
  svg rect.lblbox.pinned{stroke:var(--accent)}

  .legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12.5px;margin:14px 0 2px;
    font-family:var(--mono);color:var(--text-secondary)}
  .legend .item{display:inline-flex;align-items:center;gap:7px}
  .legend .swatch{width:11px;height:11px;border-radius:50%;display:inline-block}
  .legend .line{width:20px;height:0;border-top:2px dashed var(--muted);display:inline-block}

  .tip{position:absolute;pointer-events:none;opacity:0;transition:opacity 120ms ease;
    background:var(--surface-1);border:1px solid var(--border);border-radius:9px;
    padding:9px 12px;font-size:12.5px;min-width:190px;max-width:280px;
    box-shadow:0 6px 22px rgba(0,0,0,.18);z-index:50}
  .tip.on{opacity:1}
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

  h2{font-size:22px;color:var(--text-primary);font-weight:600;margin-bottom:6px;letter-spacing:-.01em}
  .sub{font-size:14px;margin-bottom:16px;max-width:880px}
  .toc{display:flex;gap:16px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;margin-bottom:30px}
  button.action{font-family:var(--mono);font-size:12px;padding:8px 15px;background:var(--surface-1);
    color:var(--accent);border:1px solid var(--accent);border-radius:8px;cursor:pointer}
  button.action:hover{background:var(--plane)}
  .toast{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-left:10px;
    opacity:0;transition:opacity .2s}
  .toast.show{opacity:1}
  .foot{color:var(--muted);font-size:12.5px;margin-top:56px;padding-top:20px;
    border-top:1px solid var(--border)}
</style>
</head>
<body class="viz-root">
<div class="page">

  <header>
    <div class="eyebrow">ai-researcher &middot; single-source &middot; captured __CAPTURED__</div>
    <h1>Frontier models &mdash; intelligence vs cost per task</h1>
    <p class="lede">Every number on this page comes from
      <a href="https://artificialanalysis.ai/leaderboards/models">artificialanalysis.ai</a> and nowhere else.
      The two axes are their Intelligence Index and their measured cost to complete one index task &mdash;
      so &ldquo;how smart&rdquo; and &ldquo;what it costs to be that smart&rdquo; are read off the same run,
      not stitched together from a benchmark table and a price list.</p>
  </header>

  <div class="method">
    <div class="label">Method</div>
    <div class="mgrid">
      <div><div class="k">Source</div><div class="v">Artificial Analysis</div></div>
      <div><div class="k">Metric &middot; y</div><div class="v">Intelligence Index v4.1</div></div>
      <div><div class="k">Metric &middot; x</div><div class="v">Cost per task (USD)</div></div>
      <div><div class="k">Models plotted</div><div class="v" id="mStat">&mdash;</div></div>
      <div><div class="k">Captured</div><div class="v">__CAPTURED__</div></div>
    </div>
  </div>

  <div class="callout">
    <b>Cost per task is measured, not quoted.</b> It is what Artificial Analysis actually spent running the
    model through the index &mdash; input, cached reads, output and reasoning tokens included &mdash; so a
    verbose reasoning model costs more than its per-token price suggests. That is also why the plot is
    smaller than the full catalogue: AA lists <span id="cTotal">&mdash;</span> models but only publishes a
    cost per task for the <span id="cPlot">&mdash;</span> it has run through the index harness itself.
    Everything else is genuinely unmeasured here, so it is absent rather than estimated.
  </div>

  <div class="callout">
    <b>Two chips do the real work.</b> <em>Hide superseded</em> drops every model that another model beats
    on both axes at once &mdash; the metric's verdict, not the vendor's retirement flag, and recomputed
    against whatever else you have filtered to. <em>Dump effort levels</em> collapses each model's effort
    settings to a single row at its highest index, applied before the superseded test so the frontier is
    then drawn between models rather than between knobs.
    <br><br>
    Worth knowing what collapsing costs, because it is not free: effort levels are genuine operating
    points, not redundancy. Turning a model down makes it cheaper <em>and</em> dumber, so it is not beaten
    by its own high-effort twin &mdash; only <b><span id="cSib">&mdash;</span></b> of the
    <span id="cPlot2">&mdash;</span> variants here are beaten by another setting of the same model.
    Collapsing therefore deletes real frontier points (<b><span id="cF1">&mdash;</span> drops to
    <span id="cF2">&mdash;</span></b>), including cheap ones worth knowing about. Expanded answers &ldquo;which
    configuration should I run&rdquo;; collapsed answers &ldquo;which model is best&rdquo;. Vendor-retired
    models stay visible and tagged either way &mdash; the metric decides what is worth looking at.
  </div>

  <nav class="toc">
    <a href="#chart">1 &middot; The chart</a>
    <a href="#frontier">2 &middot; Efficient frontier</a>
    <a href="#table">3 &middot; Full table</a>
  </nav>

  <div class="filters" role="group" aria-label="Filters">
    <button class="chip" id="fProp" aria-pressed="true"><span class="dot prop"></span>Proprietary</button>
    <button class="chip" id="fOpen" aria-pressed="true"><span class="dot open"></span>Open-weights</button>
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

  <section id="chart">
    <div class="card">
      <div class="cap">Intelligence Index vs cost per task &middot; log cost axis &middot; up-and-left is better
        &middot; click any point to pin its name</div>
      <div class="plotwrap">
        <svg id="svg" viewBox="0 0 980 560" role="img"
             aria-label="Scatter plot of Artificial Analysis Intelligence Index against cost per task in US dollars"></svg>
        <div class="tip" id="tip" role="status"></div>
      </div>
      <div class="legend">
        <span class="item"><span class="swatch" style="background:var(--series-prop)"></span>Proprietary</span>
        <span class="item"><span class="swatch" style="background:var(--series-open)"></span>Open-weights</span>
        <span class="item"><span class="line"></span>Efficient frontier</span>
      </div>
    </div>
  </section>

  <section id="frontier">
    <h2>2 &middot; The efficient frontier</h2>
    <p class="sub">The models nothing else beats on both axes at once &mdash; no other model is
      simultaneously at least as smart <em>and</em> at least as cheap. Anything missing from this list is
      <b>superseded</b>: strictly beaten, so there is no budget at which it is the right pick. Read down
      until the intelligence is enough for the job, then stop &mdash; paying past that buys nothing on
      this metric. This layer recomputes against the filters above, so selecting one lab gives you that
      lab's frontier, and the <em>Hide superseded</em> chip collapses every view to exactly this set.</p>
    <div class="card" style="padding:0;overflow:hidden">
      <table id="fTable"><thead><tr>
        <th>Model</th><th>Lab</th><th style="text-align:right">Index</th>
        <th style="text-align:right">$ / task</th><th style="text-align:right">$ per index point</th><th>Weights</th>
      </tr></thead><tbody></tbody></table>
    </div>
  </section>

  <section id="table">
    <h2>3 &middot; Full table</h2>
    <p class="sub">The same slice the chart is showing, as numbers &mdash; click any header to sort.
      This is the accessible twin of the plot: nothing is reachable only by hovering.</p>
    <div style="margin-bottom:12px">
      <button class="action" id="copyMd">Copy as Markdown</button>
      <button class="action" id="copyJson">Copy as JSON</button>
      <span class="toast" id="toast"></span>
    </div>
    <div class="scroll">
      <table id="tbl"><thead><tr>
        <th data-k="name">Model <span class="ar">&#8597;</span></th>
        <th data-k="creator">Lab <span class="ar">&#8597;</span></th>
        <th data-k="ii" style="text-align:right">Index <span class="ar">&#8597;</span></th>
        <th data-k="cost" style="text-align:right">$ / task <span class="ar">&#8597;</span></th>
        <th data-k="pin" style="text-align:right">$ / 1M in <span class="ar">&#8597;</span></th>
        <th data-k="pout" style="text-align:right">$ / 1M out <span class="ar">&#8597;</span></th>
        <th data-k="tps" style="text-align:right">tok/s <span class="ar">&#8597;</span></th>
        <th data-k="ctx" style="text-align:right">Context <span class="ar">&#8597;</span></th>
        <th data-k="rel">Released <span class="ar">&#8597;</span></th>
        <th data-k="open">Weights <span class="ar">&#8597;</span></th>
      </tr></thead><tbody></tbody></table>
    </div>
  </section>

  <div class="foot">
    <p>Sourced entirely from Artificial Analysis &mdash; Intelligence Index v4.1, whose components are
      <span id="evals"></span>. Cost per task and the index are AA's own measurements; this page reproduces
      them without adjustment and adds no numbers of its own. Rebuild with
      <code>python3 scripts/fetch_aa.py &amp;&amp; python3 build.py</code>.</p>
  </div>
</div>

<script>
const DATA = __DATA__;
(function(){
  "use strict";
  const R = DATA.rows, S = DATA.stats;
  const $ = id => document.getElementById(id);
  const fmtCost = v => v >= 1 ? "$" + v.toFixed(2) : "$" + v.toFixed(3);
  const fmtCtx  = v => v == null ? "—" : v >= 1e6 ? (v/1e6).toFixed(v%1e6?1:0)+"M"
                                            : v >= 1e3 ? Math.round(v/1e3)+"K" : String(v);
  const show = v => (v == null || v === "") ? "—" : String(v);

  $("mStat").textContent = S.plotted + " of " + S.total;
  $("cTotal").textContent = S.total;
  $("cPlot").textContent  = S.plotted;
  $("cPlot2").textContent = S.plotted;
  $("cSib").textContent   = S.sibBeaten;
  $("cF1").textContent    = S.frontFull;
  $("cF2").textContent    = S.frontCollapsed;
  $("evals").textContent  = S.evals.join(", ");

  const labs = [...new Set(R.map(r => r.creator))].sort((a,b)=>a.localeCompare(b));
  for (const l of labs) {
    const o = document.createElement("option");
    o.value = l; o.textContent = l; $("fLab").appendChild(o);
  }

  const st = { prop:true, open:true, sup:false, eff:false, reas:false, only:false,
               lab:"", q:"", sortK:"ii", sortDir:-1 };
  // Names whose labels the reader has stuck down by clicking. Keyed by name so
  // a pin survives filtering and resizing, and returns when the model does.
  const pins = new Set();

  function baseSlice(){
    const q = st.q.trim().toLowerCase();
    return R.filter(r =>
      (r.open ? st.open : st.prop) &&
      (!st.only || pins.has(r.name)) &&
      (!st.reas || r.reas) &&
      (!st.lab || r.creator === st.lab) &&
      (!q || r.name.toLowerCase().includes(q) || r.creator.toLowerCase().includes(q)));
  }

  // "Superseded" is decided by the metric, evaluated against whatever the other
  // filters left -- so it always means "beaten inside the view you are looking
  // at", never "retired by its vendor".
  // Collapse a model's effort settings to one row: its ceiling (highest index,
  // cheapest variant if two tie there). Deliberately runs BEFORE the dominance
  // test, so "superseded" is judged between models rather than between a model
  // and its own turned-down settings -- otherwise every low-effort variant is
  // trivially beaten by its high-effort twin and the frontier says nothing.
  function collapse(rows){
    const by=new Map();
    for(const r of rows){
      const cur=by.get(r.base);
      if(!cur || r.ii>cur.ii || (r.ii===cur.ii && r.cost<cur.cost)) by.set(r.base,r);
    }
    return [...by.values()];
  }

  function slice(){
    let b = baseSlice();
    if(st.eff) b = collapse(b);
    return st.sup ? frontierOf(b) : b;
  }

  // colour follows the entity, never its rank or row order
  const colourOf = r => r.open ? "var(--series-open)" : "var(--series-prop)";

  /* ---------- scatter ---------- */
  // The plot fills whatever width the page gives it. The viewBox width tracks
  // the container in CSS pixels while the height stays fixed, so a wide monitor
  // buys a WIDER chart rather than a proportionally taller one -- and the extra
  // horizontal room is exactly what the label placer needs.
  let W=980, H=560; const L=62, Rr=22, T=20, B=52;

  // The single definition of the undominated layer, shared by the chart line,
  // the frontier table, the table tag and the Hide-superseded chip -- so they
  // cannot disagree the way a separately precomputed flag could. A model is
  // superseded when another is at least as smart AND at least as cheap, strictly
  // better on one of the two; exact ties survive together.
  function frontierOf(rows){
    return rows
      .filter(r => !rows.some(o => o !== r &&
        o.ii >= r.ii && o.cost <= r.cost && (o.ii > r.ii || o.cost < r.cost)))
      .sort((a,b) => a.cost - b.cost || b.ii - a.ii);
  }

  let pts=[], frontSet=new Set();
  function draw(rows){
    const svg = $("svg");
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
    const fr=frontierOf(rows);
    frontSet=new Set(fr);
    const segs=[];
    if(fr.length>1){
      let d="M "+X(fr[0].cost)+" "+Y(fr[0].ii);
      for(let i=1;i<fr.length;i++){
        const x1=X(fr[i-1].cost), y1=Y(fr[i-1].ii);
        const x2=X(fr[i].cost),   y2=Y(fr[i].ii);
        segs.push([x1,y1,x2,y2]);
        d+=" L "+x2+" "+y2;
      }
      svg.appendChild(el("path",{d:d,fill:"none",stroke:"var(--muted)",
        "stroke-width":1.5,"stroke-dasharray":"5 4","stroke-linejoin":"round"}));
    }

    // marks: r=5 (10px), 2px surface ring so overlaps stay separable
    pts=[];
    for(const r of rows){
      const cx=X(r.cost), cy=Y(r.ii), on=frontSet.has(r);
      const c=el("circle",{cx:cx,cy:cy,r:on?6:5,fill:colourOf(r),
        stroke:"var(--surface-1)","stroke-width":2,
        class:"pt"+(pins.has(r.name)?" pinned":"")});
      svg.appendChild(c);
      pts.push({r:r,x:cx,y:cy,el:c});
    }

    // ---- direct labels, placed only where they collide with NOTHING ----
    // Real collision detection against every dot, every frontier segment, every
    // already-placed label and the plot edges. A label that cannot find a clear
    // slot is dropped entirely rather than shipped overlapping -- the tooltip
    // and the table still carry it, so nothing becomes unreachable.
    const PAD=3, boxes=[];
    const hitsBox=(a,b)=> a.x < b.x+b.w+PAD && a.x+a.w+PAD > b.x &&
                          a.y < b.y+b.h+PAD && a.y+a.h+PAD > b.y;
    const hitsDot=(a,p)=>{                       // rect vs circle (r6 + 2 ring)
      const nx=Math.max(a.x,Math.min(p.x,a.x+a.w));
      const ny=Math.max(a.y,Math.min(p.y,a.y+a.h));
      return (p.x-nx)**2 + (p.y-ny)**2 < 81;
    };
    const hitsSeg=(a,[x1,y1,x2,y2])=>{
      if(Math.max(x1,x2)<a.x || Math.min(x1,x2)>a.x+a.w ||
         Math.max(y1,y2)<a.y || Math.min(y1,y2)>a.y+a.h) return false;
      const n=Math.max(2,Math.ceil(Math.hypot(x2-x1,y2-y1)/2));
      for(let i=0;i<=n;i++){
        const t=i/n, sx=x1+(x2-x1)*t, sy=y1+(y2-y1)*t;
        if(sx>=a.x && sx<=a.x+a.w && sy>=a.y && sy<=a.y+a.h) return true;
      }
      return false;
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
      const n=Math.max(2,Math.ceil(Math.hypot(x2-x1,y2-y1)/3));
      for(let i=0;i<=n;i++){
        const t=i/n, sx=x1+(x2-x1)*t, sy=y1+(y2-y1)*t;
        for(const p of pts){
          if(p===own) continue;
          if((sx-p.x)**2+(sy-p.y)**2 < 56) return false;
        }
      }
      return !boxes.some(b=>hitsSeg(b,[x1,y1,x2,y2]));
    };

    // Pinned names first -- the reader asked for those explicitly, so they get
    // first claim on space; then the frontier, smartest first.
    const queue=[
      ...rows.filter(r=>pins.has(r.name)).map(r=>({r,pin:true})),
      ...[...fr].sort((a,b)=> b.ii-a.ii)
                .filter(r=>!pins.has(r.name)).map(r=>({r,pin:false})),
    ];
    let dropped=0;
    for(const {r,pin} of queue){
      const cx=X(r.cost), cy=Y(r.ii), own=pts.find(p=>p.r===r);
      const wide=pin||full;                    // pinned names are never clipped
      const t=el("text",{class:"lbl"});
      t.textContent = wide ? r.name
                     : (r.name.length>34 ? r.name.slice(0,33)+"…" : r.name);
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
  const tip=$("tip"), svg=$("svg");
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
    tip.innerHTML="";
    const n=document.createElement("div"); n.className="tname";
    n.textContent=r.name; tip.appendChild(n);
    const rows=[["Intelligence Index",r.ii.toFixed(1)],
                ["Cost per task",fmtCost(r.cost)],
                ["Lab",r.creator],
                ["Weights",r.open?(r.lic||"open"):"proprietary"],
                ["Output speed",r.tps==null?"—":r.tps+" tok/s"],
                ["Context",fmtCtx(r.ctx)]];
    rows.push(["On frontier", frontSet.has(r) ? "yes" : "no — superseded"]);
    if(r.dep) rows.push(["Vendor status","retired"]);
    for(const [k,v] of rows){
      const d=document.createElement("div"); d.className="trow";
      const a=document.createElement("span"); a.textContent=k;
      const c=document.createElement("span"); c.className="tv"; c.textContent=v;
      d.appendChild(a); d.appendChild(c); tip.appendChild(d);
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

  /* ---------- tables ---------- */
  function fillFrontier(rows){
    const tb=$("fTable").querySelector("tbody");
    tb.innerHTML="";
    for(const r of frontierOf(rows).slice().reverse()){
      const tr=document.createElement("tr");
      const add=(txt,cls)=>{const td=document.createElement("td");
        if(cls) td.className=cls; td.textContent=txt; tr.appendChild(td);};
      add(r.name,"name"); add(r.creator);
      add(r.ii.toFixed(1),"n"); add(fmtCost(r.cost),"n");
      add("$"+(r.cost/r.ii).toFixed(4),"n");
      const td=document.createElement("td");
      const sp=document.createElement("span"); sp.className="tag";
      sp.textContent=r.open?(r.lic||"open"):"proprietary";
      td.appendChild(sp); tr.appendChild(td);
      tb.appendChild(tr);
    }
  }

  function fillTable(rows){
    // same frontier function the chart uses, over the same slice -- the tag and
    // the drawn line cannot disagree
    const fset=new Set(frontierOf(rows));
    const k=st.sortK, dir=st.sortDir;
    const sorted=[...rows].sort((a,b)=>{
      let x=a[k], y=b[k];
      if(x==null&&y==null) return 0;
      if(x==null) return 1;
      if(y==null) return -1;
      if(typeof x==="string") return dir*x.localeCompare(y);
      return dir*(x-y);
    });
    const tb=$("tbl").querySelector("tbody");
    tb.innerHTML="";
    for(const r of sorted){
      const tr=document.createElement("tr");
      const add=(txt,cls)=>{const td=document.createElement("td");
        if(cls) td.className=cls; td.textContent=txt; tr.appendChild(td);};
      const nameTd=document.createElement("td");
      nameTd.className="name";
      nameTd.appendChild(document.createTextNode(r.name+" "));
      if(fset.has(r)){const s=document.createElement("span");
        s.className="tag f"; s.textContent="frontier"; nameTd.appendChild(s);}
      if(r.dep){const s=document.createElement("span");
        s.className="tag"; s.textContent="vendor-retired"; nameTd.appendChild(s);}
      tr.appendChild(nameTd);
      add(r.creator);
      add(r.ii.toFixed(1),"n"); add(fmtCost(r.cost),"n");
      add(r.pin==null?"—":"$"+r.pin,"n");
      add(r.pout==null?"—":"$"+r.pout,"n");
      add(r.tps==null?"—":String(r.tps),"n");
      add(fmtCtx(r.ctx),"n");
      add(show(r.rel));
      add(r.open?(r.lic||"open"):"proprietary");
      tb.appendChild(tr);
    }
  }

  $("tbl").querySelectorAll("th[data-k]").forEach(th=>{
    th.addEventListener("click",()=>{
      const k=th.dataset.k;
      if(st.sortK===k) st.sortDir*=-1;
      else { st.sortK=k; st.sortDir = (k==="name"||k==="creator"||k==="rel") ? 1 : -1; }
      render();
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
    const rows=slice();
    const head="| Model | Lab | Index | $/task | $/1M in | $/1M out | Context | Weights |\n"
              +"|---|---|---:|---:|---:|---:|---:|---|\n";
    const body=rows.map(r=>"| "+[r.name,r.creator,r.ii.toFixed(1),fmtCost(r.cost),
      r.pin==null?"—":"$"+r.pin, r.pout==null?"—":"$"+r.pout,
      fmtCtx(r.ctx), r.open?(r.lic||"open"):"proprietary"].join(" | ")+" |").join("\n");
    clip(head+body+"\n\nSource: Artificial Analysis (artificialanalysis.ai), captured __CAPTURED__.",
         "✓ "+rows.length+" rows copied");
  });
  $("copyJson").addEventListener("click",()=>{
    clip(JSON.stringify({source:"artificialanalysis.ai",captured:"__CAPTURED__",
      models:slice()},null,2),"✓ JSON copied");
  });

  /* ---------- wiring ---------- */
  function render(){
    // Unpinning the last model would leave "Only pinned" showing an empty plot
    // with no visible way out, since the chip itself hides with the pins.
    if(!pins.size && st.only){
      st.only=false; $("fOnly").setAttribute("aria-pressed","false");
    }
    const base=baseSlice();
    const coll=st.eff ? collapse(base) : base;
    const rows=st.sup ? frontierOf(coll) : coll;
    const bits=[rows.length+" model"+(rows.length===1?"":"s")];
    if(st.eff) bits.push((base.length-coll.length)+" effort variants dumped");
    if(st.sup) bits.push((coll.length-rows.length)+" superseded hidden");
    // Pins are never cleared by filtering or searching -- they are keyed by
    // name, so a model that is filtered out keeps its pin and gets its label
    // back the moment it returns to the view. Only the button clears them.
    if(pins.size){
      const shown=rows.filter(r=>pins.has(r.name)).length;
      bits.push(pins.size+" pinned"+(shown<pins.size ? " ("+shown+" in view)" : ""));
    }
    $("fClear").hidden = pins.size===0;
    $("fOnly").hidden  = pins.size===0;
    $("count").textContent=bits.join(" · ");
    draw(rows); fillFrontier(rows); fillTable(rows); hideTip();
  }
  const toggle=(id,key)=>$(id).addEventListener("click",()=>{
    st[key]=!st[key]; $(id).setAttribute("aria-pressed",String(st[key])); render();});
  toggle("fProp","prop"); toggle("fOpen","open");
  toggle("fSup","sup");   toggle("fEff","eff");   toggle("fReas","reas");
  toggle("fOnly","only");
  $("fClear").addEventListener("click",()=>{ pins.clear(); render(); });
  $("fLab").addEventListener("change",e=>{st.lab=e.target.value; render();});
  $("fQ").addEventListener("input",e=>{st.q=e.target.value; render();});
  // re-render on resize so the plot re-fits and labels re-place for the new width
  let rzT=null;
  window.addEventListener("resize",()=>{
    hideTip(); clearTimeout(rzT); rzT=setTimeout(render,150);
  });
  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
