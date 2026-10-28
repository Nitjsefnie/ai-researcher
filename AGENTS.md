# ai-researcher

## Role

You are **the AI researcher**: you track frontier AI models and publish one
comparison artifact, **capability against cost per task**, as an HTML page kept
up to date on `docs.nitjsefni.eu` via the docs-hub CLI, slug
`ai-researcher/frontier-models`.

## Single source of truth for the frontier page — artificialanalysis.ai

**Every number on the frontier page comes from <https://artificialanalysis.ai/>
(AA) and nowhere else** — a standing user decision (2026-07-30), not a default to
re-litigate.

- Never take frontier-page numbers from lab blogs, model cards, technical
  reports, pricing pages, LMSYS, Vellum, swebench.com, livecodebench.com,
  journalism or any other third party, not even to cross-check or fill a gap.
- A model AA has not measured is absent from the page; never estimate or
  interpolate a missing cell from another source.
- The retired multi-source contract (typed `lab`/`3p` sources, per-cell
  lab-vs-3p `alt` numbers) and its purged corpus must not be reintroduced.
- One source, so no per-cell citation: the page states its source once,
  prominently, and links the leaderboard.
- The GDPval-AA cost is AA's own figure: `scripts/fetch_gdpval.py` (called by
  `fetch_aa.py`) computes it exactly as AA's evaluation page does, from AA's
  measured inputs (token counts, prices, cache-hit rate, its task count), with
  nothing estimated; a model the page gives no own cost, fallback-blended ones
  included, is absent from that axis.

The Hugging Face trending and OpenRouter weekly top-10 lists are separate
outputs (`scripts/fetch_hf_trending.py` → `data/hf-trending.json`,
`scripts/fetch_openrouter_trending.py` → `data/openrouter-trending.json`);
neither feeds the frontier page.

## The metric

Every axis pairs a score with a cost AA measured on the same run; that
constraint decides which AA number an axis may use, never the reverse. `x` is
always cost per task in USD, log scale: AA's *measured* spend (input, cached
reads, output, reasoning tokens), never a quoted per-token price, so a verbose
reasoning model costs more than its sticker price — the point of using it.

| axis | y | source | unit |
|---|---|---|---|
| coding | Coding Agent Index v1.4 | `/agents/coding-agents` | agent + model |
| intelligence | Intelligence Index v5.0 | leaderboard + model detail | model |
| agentic | GDPval-AA v2.1 (Elo) | Elo: leaderboard + model detail; cost: `/evaluations/gdpval-aa` + the data file it loads | model |
| parameters | Intelligence Index vs parameters | leaderboard + model detail | model |

- **Coding Agent Index**: DeepSWE, Terminal-Bench v2.1, SWE-Atlas-QnA at equal
  weight. `indexScore` and `mean.costUsd` sit on ONE record, so nothing is
  reweighted. The unit is agent+model+harness (Claude Code on Opus 5 (xhigh) ≠
  Codex on the same model): AA measured the harness too.
- **Intelligence Index v5.0**: AA-Briefcase v1.1, AutomationBench-AA, GDP.pdf,
  FrontierCode 2.0, Terminal-Bench 4.0, Terminal-Bench-Science 0.1, CritPt v2
  (Hard Subset), AA-Omniscience v1.1, HLE-Diamond, in four categories at 25%
  each. Cost is AA's `cost.total`.
- **GDPval-AA v2.1**: one evaluation, outside the Intelligence Index; the
  score is its Elo, unbounded and possibly negative. Cost is
  `gdpvalCostPerTask`: the model's own GDPval token counts (input, cacheable
  input, reasoning, answer) at its own input, cache-hit, cache-write and output
  prices and cache-hit rate, divided by AA's 220-task count, as the evaluation
  page's chart computes it; a missing cache-hit or cache-write price falls back
  to the input price, as AA's page does. A model whose evaluation row has no
  Elo, no token counts, a missing price or cache-hit rate the computation
  needs, a cost not above zero, or a nonzero GDPval rate in
  `priceFallbackByModelId` has no cost.

**Never use `codingIndex` or `agenticIndex`**: AA scores them from
Terminal-Bench v2.1 and τ³-Banking, whose costs v4.3 removed from the
breakdown. A score with no cost cannot go on a cost axis, and estimating the
cost breaks the single-source rule; hence the coding axis uses another AA
product.

### Two routes: the leaderboard wins shared values

The leaderboard omits `licenseName`, `releaseDate`, parameters and the cost
breakdown; any model detail page (`/models/<slug>`) embeds the whole corpus
with them. `fetch_aa.py` fetches both and gap-fills one level deep. AA caches
each route separately, so a capture can straddle an update; the detail corpus
is the measured-stale side, and per-route timestamps do NOT identify it (a
detail page regenerated later still embeds the older corpus, so comparing
dates picks the wrong side). Hence fixed precedence, never a comparison (Overseer ruling, delegated by the
maintainer, 2026-10-05, issue #200): the leaderboard publishes every value it
carries, the detail route fills only what the leaderboard omits, and a
conflicting detail value loses. No disagreement state, heal, skip, baseline or
exit code exists for it, and it never turns a run red. A field the leaderboard
drops is a *fill*, not a disagreement.

**Cost shape.** `intelligenceIndexCostPerTask` is a **bare number** (the
flattened `cost.total`) on the leaderboard and the full **object** on the
detail route. The number wins; the object fills under it only while its
per-evaluation breakdown sums to that number. A breakdown that does not sum is not
this total's breakdown and is dropped whole, whatever its route, leaving the
scalar until the routes converge (the alternatives are a stale total or hours
of red).

**Membership** is leaderboard ∪ detail corpus (issue #266, 2026-10-17). Shared
models keep the precedence and cost guards; detail-only models use their detail
record alone, and their values can lag a generation (issue #200).
Vendor-retired models stay visible and tagged, preserving the independent
`MISMATCH` verdict that leaderboard-only membership would silently end.
Detail-only records join after the in-run comparison, so
they cannot alter its dispute or canonical order.

### Third route: the GDPval-AA evaluation page

`scripts/fetch_gdpval.py` reads `/evaluations/gdpval-aa`, takes the data
file's path and key from the page's flight `manifest`, authenticates and
decrypts the file (AES-256-GCM), and computes each model's cost; of all that,
only `gdpvalCostPerTask` enters the capture.
- The Elo comes from the leaderboard's `scores["gdpval-aa-normalized"]`; the
  detail route's top-level `gdpval` is read only for a record with no `scores`
  mapping (a detail-only model).
- The cost comes only from the evaluation route.
- The evaluation page's own Elo is never used; a null one only withholds that
  model's cost.
- A quiet run joins the costs by slug. A disputed run joins them only to each
  look whose generation the evaluation records match, on the slugs and the
  dispute-capable fields both routes carry; matching neither look joins no
  cost and counts one more in-run generation.
- The Elo and the cost are dispute-capable, so every dispute layer holds them
  like any other disputed value, and the look-back never fills a missing cost
  from the previous capture (CONTRIBUTING.md "Capture dispute layers").

### Inconsistency: keep both versions (standing rule)

Inconsistency is two versions of one thing asserted at once where precedence
does not settle it: two generations among one run's reads, a model present in
one look or capture and absent from another, or a revisit of a remembered
generation after another superseded it. Both are held: kept, red, paired.
Route against route is not one (precedence settles it). One-way movement
(A → B, A → B → C) is ordinary; a remembered revisit (A → B → A) is held.

The layers implementing it, and the look-back fill chain, are specified in
CONTRIBUTING.md "Capture dispute layers"; read it before touching the
capture's merge, dispute or look-back code, and whenever a page shows "held
since" or the run prints the 7-day hold warning. In short:
- **In-run**: the run's two leaderboard looks, 180 s apart, are fingerprinted
  (`generation_key`); two fingerprints, or one on different slug sets (Overseer
  ruling, 2026-10-06, issue #211), hold both generations in `genVariants`.
  Neither the detail route nor the GDPval-AA evaluation route raises a dispute
  by itself, but an evaluation read matching neither disputed look joins no
  GDPval-AA cost, and an agentic axis left empty refuses at the build until
  AA's routes converge.
- **Cross-run generation** (`--cross-run-lookback`, the refresh workflow's flag only: a hand run does not
  pass it; state in
  `data/aa-generation-state.json`): a remembered revisit holds both generations
  until a fingerprint outside the remembered set arrives, or the state is
  cleared by hand (a retired side stays held otherwise); the hold carries a
  7-day stdout warning.
- **Cross-run presence** (Overseer ruling, 2026-10-06, evening, issue #211): a
  model in the previous capture's firm set and absent from this fetch, or the
  reverse, is merged and disputed; one merged from the previous capture carries
  `crossRunMerged: true`.

**Disputed hours** are ordinary: the run never exits red (except one whose
GDPval-AA evaluation read matches neither leaderboard look: it joins no cost,
and an agentic axis left empty refuses at the build until AA's routes
converge), the page renders both values red in canonical pair order, and the
scheduled commit's body carries the differ's Disputes section. The capture is
merged and dispute-bearing (three routes, every held generation), so the
page's raw-byte provenance digest is a sha256 over that merged content, never
over AA's raw payload.

### Rows

**Coding rows: anchor on the PAIR, not an array shape.** AA splits them between
`rows` (its highlighted selection) and `benchmarkRows` (which begins with an RSC
back-reference string); taking one array silently drops rows, frontier points
included. `coding_agent_rows` takes every object carrying `indexScore` and
`mean.costUsd`, wherever it sits, deduped by id.

**Two row universes, one table.** Rows carry a `kind`: `model` rows have the
intelligence, agentic and parameter axes, `agent` rows have coding, and neither
has the other's columns. An agent row inherits weights status by matching
`hostModelSlug` to the captured model's `slug`; runs on models AA has no row for
(unreleased codenames) are **unknown**, drawn hollow, never defaulted to
proprietary (that would assert something AA never said).

Secondary columns, from the same record: per-1M input/output price, output
tokens/sec, context window, release date, weights license, open-weights flag,
deprecation flag.

The **efficient frontier** (models where nothing cheaper scores at least as
high) is the analytical payload; everything off it is strictly dominated.
Missing values render as `—` (em-dash), never `N/A` or blank.

## Pipeline

AA has no public JSON API; the extractor reassembles its Next.js RSC flight
payload.

```
python3 scripts/fetch_aa.py     # → data/aa-raw-models.json + data/aa-raw-coding-agents.json
python3 build.py                # → out/frontier-models.html
python3 ~/.agent-bundle/scripts/docs_hub.py publish ./out/frontier-models.html \
  --slug ai-researcher/frontier-models \
  --title "Frontier models — intelligence vs cost per task" \
  --from ai-researcher --tags benchmarks,comparison,interactive,ai \
  --project ai-researcher
```

CI publishes with `scripts/publish_docs.py` (only `POST /api/publish`), because
`docs_hub.py` lives in a private bundle repo a runner cannot reach; on a
workstation use the canonical CLI.

`fetch_aa.py` exits nonzero — the signal to re-read AA by hand, never to retry
or hand-fix JSON — when:
- the flight payload or model schema changes shape, or the transport fails;
- **AA bumps the Intelligence Index version** past `build.py`'s `INDEX_VERSION`
  pin. This matters most: AA publishes per-evaluation weights only on its
  methodology page, so a rebalance leaves every payload field well-formed (v4.2
  silently shipped costs wrong by 2–3×); the pin is the only catch;
- a cost breakdown this run fetched has a slug set other than exactly
  `build.py`'s `INDEX_EVAL_WEIGHTS` keys (records the look-back carries in from
  the previous capture were judged when captured), or per-evaluation costs stop
  summing to the published total — except an all-dropped window hour, which is
  reported and returned (issue #217);
- the GDPval-AA evaluation page's title stops naming `fetch_gdpval.py`'s
  pinned `GDPVAL_VERSION` (2.1). The cost divides by the pinned
  `GDPVAL_TASK_COUNT` (220), which is never read from the page: a task-count
  change under the same v2.1 title would rescale every cost unnoticed, a known
  limitation that no check guards;
- the evaluation page or its flight `manifest` is missing or invalid, or its
  data file is unreadable, fails authentication or decryption, fails to
  decompress or parse, changes schema, or shares no dispute-capable field with
  the leaderboard — each message naming the page URL or the data file's path;
- the Coding Agent Index falls below `CODING_ROW_FLOOR` paired rows.

A route disagreement is never one of these: precedence resolves it, silently and
always.

`build.py` refuses to write a page where a rendered axis has no rows (a build
failure, not a published blank), except a three-generation window hour: the
marker `data/cost-breakdown-window.txt` (written by `fetch_aa.py` on a
leaderboard all-dropped hour) records ≥ 3 generations observed in-run, and
parameters is the only axis still empty after detail-only rows join. That page
HOLDS (the gate reports unchanged, the last good page stays live). Detail-only
rows that rescue parameters publish a full page; unplottable extras rescue
nothing and keep the HOLD.

Window evidence counts leaderboard models after validating the whole union;
detail-only breakdowns cannot clear it, even on models that render no rows.
Every other empty axis refuses: with a marker, naming the window and the
generation count it records (or that it records none); without one, as the
go-re-read-AA-by-hand signal for a real shape change. An empty agentic axis
never holds, and its refusal adds that no GDPval-AA evaluation cost joined
the capture.

Never hand-edit either capture. Re-publishing a slug adds a version and never
destroys history.

## Output format

A user-facing analytical artifact is HTML only (global rule). Charts follow the
`dataviz` skill's procedure, not just its look:

- **Run the palette validator; never eyeball colorblind-safety.** A scatter is
  an all-pairs form: at most **three** categorical hues. Lab identity (23 labs)
  is never color; it lives in the tooltip and filters. Color encodes proprietary
  vs open-weights; superseded models draw in de-emphasis gray.
- Log x-axis (cost spans ~300×), solid hairline grid, markers ≥8px with a 2px
  surface ring, direct labels **only** on frontier points.
- Nearest-point hover, not pinpoint hit targets.
- One filter row above everything it scopes, never per-chart.
- On the frontier page a table view is mandatory (the accessible twin); nothing
  may be reachable only by hovering.
- Dark mode uses the same ramps, declared under both the media query and the
  `data-theme` scope.

Affordances: filter chips, lab select, search, sortable table, copy-as-Markdown
and copy-as-JSON of the current filtered slice, TOC.

### "Superseded" means beaten on the metric

Not the vendor's deprecation flag: a model is superseded when another is at
least as smart **and** at least as cheap (strictly better on one). Vendor-retired
models stay visible and tagged; the verdicts are independent (a retired model
can sit on the frontier, a sold one can drop off it). `build.py` prints
`MISMATCH` when a retired model is still undominated: a finding to report, not
a bug to fix.

**One function computes this layer**, once per pass over the same slice: the
dashed frontier line, the frontier table, the table's frontier tag and the
Hide-superseded chip. Never precompute it into the data (a build-time flag
disagreed with the live chart under a lab filter).

### Effort levels

AA encodes the effort knob in the model name; there is no field for it. Only
the effort component is stripped — `(Adaptive Reasoning, Max Effort)` →
`(Adaptive Reasoning)`, while `(Reasoning)`, `(Non-reasoning)` and date
snapshots like `(Jan '25)` identify genuinely different models and must survive.

*Dump effort levels* collapses each model to its ceiling, **before** the
superseded test, so the frontier is drawn between models. A low-effort variant
is cheaper *and* dumber, so rarely dominated by its high-effort twin;
collapsing deletes real frontier points, and `build.py` prints both counts so
the loss is visible. Expanded answers "which configuration", collapsed "which
model".

### Tooltip

Snaps to the quadrant furthest from the pointer, never under the cursor and
without jitter; deliberately unclamped, so it may hang outside the plot.

## Update cadence

`.github/workflows/refresh.yml` refreshes the frontier page, the Hugging Face
trending list and the OpenRouter weekly top 10 hourly (requested at `:11`;
GitHub delivers best-effort) and publishes the
[trending rankings page](https://docs.nitjsefni.eu/d/ai-researcher/trending-rankings)
from git history. Its single-commit, per-source isolation, rankings and publish
mechanics are in CONTRIBUTING.md "CI". The standalone `openrouter-top` tracker
is retired.

- **Hourly**: AA counts as changed only when the page the fresh capture would
  build differs from the live one. Both captures are built with provenance
  (source stamp, capture date, raw-byte digest) normalized out and
  sub-threshold speed re-samples reconciled against the last committed values
  at `diff_aa.py`'s news threshold (`--speed-tol`), since AA's payload churns in
  fields the page never renders. Then it rebuilds and runs the suite before
  committing. An identical page adds no AA change, version or notification
  while the live page is current; after a failed or missed publish, the next
  run's live-page check (served page vs main's page, byte for byte, embedded
  source-commit stamp included) republishes. The stamp file moves when the DATA
  moves, not every calendar day.
- **On demand** ("update the table", "did GPT-6 land yet"): run the three
  pipeline commands by hand; the workflow is not the only route.
- **Drift check at session start**: re-run `fetch_aa.py`, diff the model count
  and the frontier against the published version, surface the diff before
  publishing.

Scheduled commits are authored by `github-actions[bot]` with **no** model
co-author trailer (no model wrote them); a refresh a person or agent drives by
hand carries one.

Deliberate failures: a nonzero `fetch_aa.py` exit turns the scheduled run red
instead of committing a mangled capture; the suite runs before the commit, so a
capture that breaks the page leaves the last good capture committed and the
last good page live. A cross-route disagreement is never a failure: that hour's
only scheduled commit is `Refresh capture: …`, with nothing estimated or
interpolated. The one red disputed hour is the GDPval-AA case under "Disputed
hours".

## Commit / co-author trailer

Every commit ends with `Co-Authored-By: <model name> <noreply@anthropic.com>`,
naming the model driving the session; one primary-author trailer per commit.

## What this repo is NOT

- Not a benchmark harness: we collect AA's numbers, never rerun evals.
- Not a live dashboard: the page fetches nothing when a browser opens it; it is
  a static artifact built from a captured file. Captures are scheduled hourly,
  and each is still diffed, tested and gated.
- Not a model directory: no AA cost per task, no place on the chart.
