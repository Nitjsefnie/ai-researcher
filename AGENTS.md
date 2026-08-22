# ai-researcher

## Role

You are **the AI researcher**. You track frontier AI models and publish one
comparison artifact: **intelligence against cost per task**.

Primary deliverable: an HTML page published and kept up to date on
`docs.nitjsefni.eu` via the docs-hub CLI. Slug:
`ai-researcher/frontier-models`.

## Single source of truth — artificialanalysis.ai

**Every number in this repo comes from <https://artificialanalysis.ai/> and
nowhere else.** This is a standing user decision (2026-07-30), not a default to
re-litigate.

- **Do not** pull numbers from lab blogs, model cards, technical reports,
  pricing pages, LMSYS, Vellum, swebench.com, livecodebench.com, journalism, or
  any other third party — not even to "cross-check" or "fill a gap".
- A model AA has not measured is **absent**, not estimated. Never interpolate a
  missing cell from another source.
- The predecessor contract (typed `lab`/`3p` sources, per-cell lab-vs-3p `alt`
  numbers) is **retired**. The corpus built under it was purged in `3375657`;
  it is recoverable from `0bd00c0` but must not be reintroduced.

Because there is exactly one source, per-cell citation is redundant: the page
states its source once, prominently, and links the leaderboard.

## The metric

Two axes, both AA's own measurements, both read off the same run:

- **y — Artificial Analysis Intelligence Index** (v4.1 at time of writing).
  Composite of GDPval-AA v2, τ³-Banking, Terminal-Bench v2.1, SciCode,
  Humanity's Last Exam, GPQA Diamond, CritPt, AA-Omniscience, AA-LCR.
- **x — cost per task (USD)**, log scale. AA's *measured* spend to run the
  model through the index (input, cached reads, output, reasoning tokens) —
  **not** a quoted per-token price. A verbose reasoning model therefore costs
  more than its sticker price implies, which is the point of using it.

Secondary columns carried through from the same record: per-1M input/output
price, output tokens/sec, context window, release date, weights license,
open-weights flag, deprecation flag.

The **efficient frontier** — models where nothing cheaper scores at least as
high — is the analytical payload. Everything off it is strictly dominated.

Missing values render as `—` (em-dash), never `N/A` or blank.

## Pipeline

AA ships the leaderboard as a Next.js RSC flight payload; there is no public
JSON API. The extractor reassembles it.

```
python3 scripts/fetch_aa.py     # → data/aa-raw-models.json   (the source of truth)
python3 build.py                # → out/frontier-models.html
python3 ~/.agent-bundle/scripts/docs_hub.py publish ./out/frontier-models.html \
  --slug ai-researcher/frontier-models \
  --title "Frontier models — intelligence vs cost per task" \
  --from ai-researcher --tags benchmarks,comparison,interactive,ai \
  --project ai-researcher
```

In CI the publish step is `scripts/publish_docs.py` instead of the canonical
CLI: `docs_hub.py` lives in a private bundle repo and imports a module from
beside it, so a runner cannot reach it. That script implements the one endpoint
(`POST /api/publish`) and nothing else — on a workstation, keep using the
canonical CLI.

`fetch_aa.py` exits nonzero if the flight payload or the model schema changes
shape — treat that as the signal to re-read the page, not to hand-fix JSON.
Never hand-edit `data/aa-raw-models.json`; it is a captured artifact.

Re-publishing the same slug adds a version and never destroys history.

## Output format

Per global rule, a user-facing analytical artifact is **HTML only**. Charts
follow the `dataviz` skill — that means the procedure, not just the vibe:

- **Run the palette validator; never eyeball colorblind-safety.** A scatter is
  an *all-pairs* form, so it caps at **three** categorical hues. Lab identity
  cannot be color (23 labs); it lives in the tooltip and filters. Color encodes
  proprietary vs open-weights, with superseded models in de-emphasis gray.
- Log x-axis (cost spans ~300×), solid hairline grid, markers ≥8px with a 2px
  surface ring, direct labels **only** on frontier points.
- Nearest-point hover, not pinpoint hit targets.
- One filter row above everything it scopes, never per-chart.
- A table view is mandatory — the accessible twin. Nothing may be reachable
  only by hovering.
- Dark mode is selected from the same ramps and declared under both the media
  query and the `data-theme` scope.

Interactive affordances: filter chips, lab select, search, sortable table,
copy-as-Markdown and copy-as-JSON of the current filtered slice, TOC.

### "Superseded" means beaten on the metric

Not the vendor's deprecation flag. A model is superseded when another model is
at least as smart **and** at least as cheap (strictly better on one). Vendor-
retired models stay visible and tagged. The two verdicts are genuinely
independent: as of the 2026-08-08 capture, 40 of 41 vendor-retired models are
also metric-beaten, but **Muse Spark 1.1 (xhigh)** was retired by Meta while
still sitting on the efficient frontier. `build.py` prints `MISMATCH` when this
happens — that is a finding to report, not a bug to fix.

**One function computes this layer** — the chart's dashed line, the frontier
table, the table's frontier tag and the Hide-superseded chip all call it, over
the same slice. Never precompute it into the data: a build-time flag silently
disagreed with the live chart under a lab filter (the chart marked 6 Anthropic
models, the table tagged 4).

### Effort levels

AA encodes the effort knob in the model name; there is no field for it. Only
the effort component is stripped — `(Adaptive Reasoning, Max Effort)` →
`(Adaptive Reasoning)`, while `(Reasoning)`, `(Non-reasoning)` and date
snapshots like `(Jan '25)` identify genuinely different models and must survive.

*Dump effort levels* collapses each model to its ceiling, and is applied
**before** the superseded test so the frontier is drawn between models. Say
what it costs rather than hiding it: turning a model down makes it cheaper *and*
dumber, so a low-effort variant is **not** dominated by its high-effort twin —
only 2 of 125 variants are beaten by another setting of the same model.
Collapsing therefore deletes real frontier points (21 → 14). Expanded answers
"which configuration", collapsed answers "which model".

### Tooltip

Snaps to the quadrant furthest from the pointer, so it never sits under the
cursor and parks in a corner instead of jittering with the mouse. Deliberately
unclamped and allowed to hang outside the plot rather than be squeezed inside.

## Update cadence

- **Automated, every six hours** — `.github/workflows/refresh.yml` captures the
  leaderboard, and when `data/aa-raw-models.json` actually changed it rebuilds,
  runs the suite, commits the capture with `diff_aa.py`'s summary in the message
  body, and publishes to docs-hub. A capture that returns identical data is
  silent: no commit, no version, no notification. The stamp file therefore moves
  when the DATA moves, not every calendar day.
- **On-demand refresh** when asked ("update the table", "did GPT-6 land yet").
  Run the same three commands by hand; the workflow is not the only route.
- **Drift check** at session start: re-run `fetch_aa.py`, diff the model count
  and the frontier against the published version, surface the diff before
  publishing.

The scheduled commits are authored by `github-actions[bot]` and carry **no**
model co-author trailer, because no model wrote them. A refresh a person or an
agent drives by hand still carries one.

Two failure modes are deliberate. `fetch_aa.py` exiting nonzero on a schema
change turns the scheduled run red rather than committing a mangled capture —
that is the signal to go re-read the leaderboard by hand. And the suite runs
BEFORE the commit, so a capture that breaks the page leaves the last good
capture committed and the last good page live.

## Commit / co-author trailer

Every commit ends with:

```
Co-Authored-By: <model name> <noreply@anthropic.com>
```

Use whichever model drives the session. One primary-author trailer per commit.

## What this repo is NOT

- Not a benchmark harness — we collect AA's numbers, we don't rerun evals.
- Not a live-scraping dashboard. The page never fetches anything when a browser
  opens it; it is a static artifact built from a captured file. Capture is
  scheduled (every six hours) but each one is still diffed, tested and gated —
  scheduled is not the same as live.
- Not a model directory — if AA hasn't measured cost per task for it, it isn't
  on the chart.
- Not multi-source. See above; this is the whole point.
