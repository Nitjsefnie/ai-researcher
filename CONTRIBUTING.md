# Contributing to ai-researcher

Issues and pull requests are welcome — especially if the page shows a model
wrong. This repo republishes numbers Artificial Analysis measured, so the most
valuable report is "AA's leaderboard says X for this model, the page says Y",
with a link to the model on <https://artificialanalysis.ai/>.

## LLM and agent contributions are welcome

You may use an LLM or a coding agent to write your contribution. There is no
penalty, no separate review queue, and no expectation that you rewrite its
output by hand. Most of this repo was built that way.

Two conditions, and they are about honesty rather than provenance:

1. **Disclose the model** with a trailer on each commit it authored:

   ```
   Co-Authored-By: <Model Name> <noreply@example.com>
   ```

   e.g. `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. One
   primary-author trailer per commit, and the plain model name — no
   context-window or deployment suffixes.

2. **Do not submit claims you have not verified.** Paste the command and its
   real output. "Tests pass" without the run is not evidence, and a change to
   the page is easy to check — rebuild it and open it.

If a maintainer's reply reads like it was drafted by an agent, it probably was.
That is fine in both directions.

## The constraints that reject the most patches

- **Every number on the frontier page comes from artificialanalysis.ai, and
  nowhere else.** Not lab blogs, model cards, technical reports, pricing pages,
  LMSYS, Vellum, swebench.com, livecodebench.com or journalism — not even to
  cross-check or to fill one gap on the frontier page. A model AA has not
  measured is **absent from the frontier page**, not interpolated. A patch that
  adds a second source to the frontier page will be declined no matter how
  good the source is: two sources with different harnesses produce numbers
  that cannot be compared on one axis, which is the only thing the frontier
  page does.

  The Hugging Face trending and OpenRouter weekly top-10 lists are separate
  tracked outputs: `scripts/fetch_hf_trending.py` writes `data/hf-trending.json`,
  and `scripts/fetch_openrouter_trending.py` writes `data/openrouter-trending.json`.
  The joined `.github/workflows/refresh.yml` updates both hourly and publishes
  [rankings over time](https://docs.nitjsefni.eu/d/ai-researcher/trending-rankings)
  from their git history. Neither tracker feeds the frontier page.

- **`data/aa-raw-models.json` is a captured artifact — never hand-edit it.**
  `scripts/fetch_aa.py` reassembles it from the leaderboard's Next.js RSC
  flight payload and exits nonzero when that payload or the model schema
  changes shape. That exit status is the signal to go re-read the page, not to
  patch the JSON into passing.

- **Cost is measured, not quoted.** The x-axis is AA's own spend running the
  model through the index — input, cached reads, output and reasoning tokens.
  A verbose reasoning model therefore lands well right of its sticker price,
  which is the entire reason the page uses the measured figure. Do not
  substitute per-1M pricing.

- **One function computes the frontier layer.** The chart's dashed line, the
  frontier table, the table's frontier tag and the Hide-superseded chip all
  call it, over the same slice. Never precompute that into the data: a
  build-time flag once disagreed with the live chart under a lab filter, and
  the two views silently reported different frontiers.

- **"Superseded" means beaten on the metric**, not retired by the vendor —
  another model at least as smart *and* at least as cheap. The two verdicts are
  independent, and `build.py` prints `MISMATCH` when a vendor-retired model is
  still on the frontier. That is a finding to report in the PR, not a bug to
  make quiet.

- **Effort levels live in the model name**, because AA has no field for them.
  Only the effort component may be stripped — `(Adaptive Reasoning, Max
  Effort)` → `(Adaptive Reasoning)`. `(Reasoning)`, `(Non-reasoning)` and date
  snapshots like `(Jan '25)` identify genuinely different models and must
  survive.

- **Charts follow the house dataviz rules.** Three categorical hues maximum in
  a scatter (lab identity is 23 labs — it lives in the tooltip and the filters,
  never in color), log x-axis, direct labels only on frontier points,
  nearest-point hover, and one filter row above everything it scopes. **On the frontier page, the
  table view is mandatory**: nothing may be reachable only by hovering.
  Dark mode is declared under both the media query and the `data-theme` scope.

## Getting it running

The runtime is pure stdlib — no install step to build the page:

```sh
python3 scripts/fetch_aa.py     # → data/aa-raw-models.json
python3 scripts/diff_aa.py      # what moved since the last capture
python3 build.py                # → out/frontier-models.html
```

`diff_aa.py` takes `git:REV` for either side, so `python3 scripts/diff_aa.py
git:HEAD~5` diffs the working capture against an older one.

**A page committed to the repository carries its source-commit stamp.** The
footer stamp is rendered only when `AI_RESEARCHER_AA_SOURCE_COMMIT` is set at build time,
and nothing but the refresh workflow sets it for you. Build with

```sh
AI_RESEARCHER_AA_SOURCE_COMMIT="$(git rev-parse HEAD)" python3 build.py
```

immediately before committing, and change no build input afterwards. CI (the
`page` job) refuses a committed page that lacks the stamp or differs from its
own stamp-less rebuild (issue #105).

## Tests

```sh
python3 -m pytest -q
```

**The runner is `python3 -m pytest`, from the repo root — not the bare `pytest`
binary.** `tests/` has no `__init__.py` and the tests `import build` from the
root, so the root has to be on `sys.path`; only the `-m` form puts the cwd
there. The bare binary collects the same files and every test errors on the
import. `unittest discover` refuses outright.

`tests/test_browser.py` drives the built page in a real headless Chromium
through playwright. It prefers a system browser at `/usr/bin/chromium` and
falls back to playwright's own download (`python3 -m playwright install
chromium`); `AI_RESEARCHER_CHROMIUM_PATH` overrides both. Half the page's behaviour — the
frontier line, the tooltip, the filter chips, the sortable table — is only
reachable through those tests, so a change to the emitted JavaScript needs one.

## CI

Sixteen workflows run. Five of them you can run locally:

```sh
python3 -m pytest -q                                             # tests
python3 -m coverage run --source=. --omit='tests/*' \
  -m pytest -q && python3 -m coverage report                     # coverage
git ls-files '*.py' | xargs python3 -m pylint                    # lint
git ls-files '*.py' | xargs python3 -m pycodestyle               # lint
python3 -m pyright                                               # types
pip-audit -r requirements-dev.txt -r requirements-test.txt       # audit
actionlint .github/workflows/*.yml && zizmor .github/workflows/  # actionlint
```

`python3 -m pip install -r requirements-dev.txt -r requirements-test.txt` gets
the pinned toolchain. Coverage is gated by a **ratchet**, not a fixed target:
the floors live in `.github/ci-thresholds.json`, each seeded 1.5 points under
the coverage of the run that recorded it. CI never lowers them: the automated
raise is the only writer on main, and it lands through the top-level
`ratchet-push` workflow's write deploy key (the `main-push` environment) —
a workflow_call callee cannot read an environment secret, which is why the
push is not a job in tests.yml (issue #133 part 2b). There are two floors: Python statement
coverage from the pytest run,
and JavaScript physical code-line coverage of the page's inline script,
measured through the browser suite (`tests/test_browser.py` records V8
coverage when `AI_RESEARCHER_JS_COVERAGE_OUT` is set, and `scripts/ci/js_coverage.py` folds
the dump). A push to `main` whose coverage climbs more than 1.5 points past
the recorded measurement raises the floor automatically; nothing can relax
the file — a guard step compares it against the merge base on a pull request
and against AI_RESEARCHER_BEFORE (the previous tip) on a push to `main`, including a
non-fast-forward push, and refuses any change that lowers a value.
`thresholds.py --check` refuses a working-tree copy below the committed one.
Scripts are counted deliberately — `--omit` leaves out only `tests/*` —
because they run unattended in CI. Note what the numbers can and cannot speak
to: what coverage counts as statements in `build.py` is a small fraction of
its size, because most of its lines are HTML, CSS and JavaScript in string
literals. The browser tests are what cover those.

The page carries a second ratchet: **performance budgets** in
`.github/perf-budgets.json`, and every budgeted number is code-only. The
page's budgeted byte count is `code_bytes` — the page's weight once every
build-time-rendered row region (the `const DATA` payload and the two static
tbody bodies) is excised — so capture growth moves nothing the ratchet gates.
Of the reader journeys (load, filter, sort, hover) only hover's DOM mutation
count and every journey's long-task count are gated; the load/filter/sort DOM
counts are measured and reported by `scripts/ci/perf_budgets.py --measure`
but never gated, because they carry the capture's frontier geometry (the
frontier tables refill one node-set per frontier row, and frontier sizes are
data, not code). Long-task budgets are absolute: a count is threshold physics,
not a per-row cost, and normalizing it would blind the guard to real
regressions. The ratchet is **tighten-only**: `--check` measures fresh and
fails on any budget exceeded, a budget may only fall, and **there is no
automated raise** — the coverage ratchet's auto-raise has no perf analogue, by
design. A deliberate raise has exactly one route onto `main` (issue #120): it
lands **as its own commit** — nothing else rides along — and the commit
message carries one declaration line per raised leaf,

    Budget-Raise: <document> <key> <from> -> <to>

naming the exact values the diff carries. The guard honors the lines on a
main **push** and on a **pull request** whose raise commit touches nothing
outside the two budget documents (issue #133 part 3), with both routes
requiring a `feat: ` or `feat(<scope>): ` commit subject in
`base..head` (issue #271) — a raise cannot ride
feature work onto main on either shape; a declaration whose values do not
match the diff exactly refuses too. Merge a raise pull request with **rebase**:
the lines live in the raise commit's message. A squash merge may replace them
with the pull request's title — GitHub's squash message can also prefill the
commit's own message — and a squash that drops them makes the raise refuse on
main's push; the rebase merge is the deterministic route. Seeding
headroom: code_bytes at the measured value exactly (builds are
byte-deterministic), hover DOM at measured + 2% (rounded up), long tasks at
measured + 1 (machine-load flap). The browser suite's `PerfBudgetTests` is
the gate CI actually runs — it measures the same journeys through the same
harness and asserts the same committed budgets, so the ratchet and its gate
cannot drift.

The pipeline carries a third ratchet: **instruction budgets** in
`.github/instruction-budgets.json`. `scripts/ci/instruction_budgets.py`
measures `build.py`, `scripts/capture_gate.py` and `scripts/diff_aa.py`
under valgrind callgrind on the committed miniature capture in
`tests/fixtures/pipeline/` — never the live `data/` captures, so the
budgets are invariant to capture size — subtracts the bare interpreter
startup (`python3 -c pass` under the same harness) from every count, and
holds each target under its integer maximum. Tighten-only like the perf
budgets: the default check mode fails on any budget exceeded, the ratchet
guard refuses a budget that rises, and there is no automated raise. A
deliberate raise follows the perf budgets' route (issue #120): its own
commit, one `Budget-Raise: <document> <key> <from> -> <to>` line
per raised leaf with the exact values the diff carries — the lines count
on a main push or a pull request's own raise commit, from a commit
touching nothing outside the two budget documents, with both routes
requiring a `feat: ` or `feat(<scope>): ` commit subject in
`base..head` (issue #271). Budgets are pinned to
the CI cell that runs the gate —
the coverage job's ubuntu-latest runner, CPython 3.15.1 / valgrind
3.22.0 — and were seeded from that cell's measured counts
(build 215,934,993, capture_gate 316,217,922, diff_aa 282,204,262
startup-subtracted Ir), each plus 3% rounded up to the next million.
Authoring-box counts (CPython 3.15.1 / valgrind 3.24.0) sit about 5%
above them; the budgets follow the CI cell because it is the only place the
gate runs. The observed run-to-run spread under the pinned environment
(`PYTHONDONTWRITEBYTECODE`, `PYTHONHASHSEED=0`, `PYTHONNOUSERSITE=1` —
without the first, a .pyc compile-then-load pair was measured swinging
1.6%) was under 0.002%; the 3% margin covers that jitter. CI's coverage
job still prints its own measured counts in the step summary, so a
tighten-only PR calibrates against fresh CI numbers. Re-measure with
`python3 scripts/ci/instruction_budgets.py --measure`. The fixture is
regenerated only through the generator functions in
`tests/test_ci_instruction_budgets.py` (a test pins its exact bytes) and
is never hand-edited.

Four run only on GitHub. `ci gate` aggregates every merge gate into one
`aggregate` verdict (issue #133): it starts on every push and pull request,
classifies the changed paths, and narrows the legs a documentation-only or
bot-data-only change skips while its `ci gate / aggregate` check still
reports — the one context a required-check ruleset can require, so a
docs-only pull request can still merge once that ruleset exists. `codeql` is
gated on repository visibility, because
code scanning is free on public repositories and needs Code Security on private
ones. `claim` watches issue comments: `/claim` assigns the commenter to an
unassigned open issue, and `/unclaim` and `/release` remove the commenter's own
assignment — self-service issue claiming for contributors without write access.

The joined `.github/workflows/refresh.yml` captures, commits and publishes the
frontier page and refreshes both trending trackers. Its `schedule` requests
hourly runs (`11 * * * *`); GitHub delivers schedules best-effort. Each run
captures AA and fetches both trackers, then pushes at most one bot commit
carrying every changed source: the AA capture with its rebuilt
`out/frontier-models.html`, the two trending lists, and
`out/trending-rankings.html`. The commit keeps one subject line; each changed
source contributes its full message as a block under its own subject line:
AA's `diff_aa.py` report and HF/OR's MOVE lines under each tracker's own line.
A failed source fetch, or a red AA gate or suite, leaves that source out while
the sources that succeeded still commit. A run in which nothing changed
pushes nothing. The single push job uses its write deploy key (the `main-push`
environment, restricted to main), so bot commits start workflow runs and get
a real `ci gate` aggregate verdict (issue #133).

Before the commit, `rankings` runs `python3 scripts/build_rankings.py` with full
git history and this run's changed tracker snapshots, with no network input.
The builder keeps up to ten columns per list; each changed list's newest
column uses the run and its fetch time, since a commit cannot contain its own
SHA and committer time. Each page is published to docs-hub after the commit lands;
`rankings-hub` publishes the same-run artifact to the
[rankings page](https://docs.nitjsefni.eu/d/ai-researcher/trending-rankings),
skipping an upload when the live bytes already match. The upload job executes
no repository code and holds the docs-hub key only in its inline upload step.

For a build-only frontier change, `workflow_dispatch` with `force: true`
rebuilds and republishes even when the fresh capture would render the identical
page. The workflow also repairs a stale live frontier page on an unchanged
capture; its header explains both the rendered no-change gate and the
republish check.

One hourly-flow case reads differently since #200: AA's two routes are
independently cached and can serve two generations of the same data, and the
refresh used to react to that with a skip, a heal, or a **disputed page** whose
cells showed both routes' values. It no longer reacts at all, because there is
nothing to react to: the leaderboard route is the fresh one and is published,
the detail route fills fields a shared leaderboard record omits. A disagreement
is resolved by fixed precedence rather than by a state. So the only scheduled
commit is `Refresh capture: N models, …`, there is no disagreement that turns a
run red, and the published document only moves forward. The two rules that
matter when you touch the capture are in AGENTS.md — the leaderboard-wins
precedence and the breakdown-drop guard at the cost shape split. The dispute-layer
detail is in "Capture dispute layers" below.
Membership is the union of both routes (issue #266): detail-only retired models
remain visible, with their detail lab and no leaderboard-only speed; their
values can lag a generation.

The window marker counts leaderboard models after validating the whole union,
so a detail-only breakdown cannot erase a route window (issue #266). In the
marked three-generation corner, empty parameters (alone or with agentic) hold the
last good page. Detail-only rows that rescue parameters leave an agentic-only
gap, which publishes with a window note; rescuing both axes publishes fully.
Unplottable extras leave the original hold intact. Other empty axes still refuse.

**Actions are hash-pinned**, with the version in a trailing comment. Do not
"tidy" one back to `@v4`: a tag is a moving pointer, and these jobs hold a
repository token. Dependabot keeps the hashes current.

**`.gitignore` is deny-by-default**: `*` first, then each shipped path named
back, with every kept directory re-opened and its contents denied again. A new
file of an unlisted type is invisible to git and will NOT appear in `git
status` as untracked — it simply never appears. `git check-ignore -v <path>`
names the rule hiding it.

## Capture dispute layers

How `fetch_aa.py` merges and disputes `data/aa-raw-models.json`. AGENTS.md
carries the rules these implement (single source, leaderboard-wins precedence,
the cost-shape guard, keep both versions of an inconsistency); this section is
binding detail for anyone touching the capture's merge, dispute or look-back
code.

**Routes.** The leaderboard ships scored records in `initialModels` beside a
three-field `models` index and omits `licenseName`, `releaseDate`, parameters
and the cost breakdown; any model detail page (`/models/<slug>`) embeds the
whole corpus as rich `models` arrays, including those. Gap-fills go one level
deep: the split runs *through* the cost object (the leaderboard drops its
`evaluations`), so a key-level merge would let a surviving stub shadow the
complete breakdown. Detail-only models (membership is leaderboard ∪ detail
corpus, issue #266): leaderboard-only speed stays absent; `creator.name`, when
a string on a mapping, fills an absent `modelCreatorName`; retired values rarely
change. Union membership lets the presence layer see genuinely new models
instead of about 430 retirements going red.

A detail page lists every model **except** its own, so the host slug loses its
detail-only fields: `detail_host_slug` picks a model with no measured cost (it
cannot be on any chart), deterministically, so the capture does not churn.
Field renames absorbed: `totalParameters` → `parameters` (identical values);
`name` falls back to `shortName`. `modelCreatorCountry` is gone from every
route; nothing rendered it.

**Look-back fills** (`--cross-run-lookback`): the chain is leaderboard > this
run's detail route > the previous committed capture's carried detail fill.
- A final pass, after every in-run, presence and revisit decision, fills absent
  detail keys from the previous record with the same string `slug`; it changes
  neither decision inputs nor `run_corpora`.
- A key in this run's leaderboard universe stays absent when the current record
  lacks it (serving movement, owned by the dispute layers). Present values,
  including null and `$undefined`, keep precedence.
- `build.merge_captures` supplies the nested cost fill under the current total
  and its `SUM_TOLERANCE` guard; a carried breakdown failing the sum check is
  dropped whole.
- `genVariants`, `crossRunMerged` and `carriedDetailFills` are synthetic and
  never carried as fills. Records receiving fills list their keys, sorted, in
  `carriedDetailFills`; the marker stays outside generation fingerprints,
  universes, variants and held state, changes no rendered field, and the news
  summary counts carries in one clause.
- `intelligenceIndexTimePerTask` is eligible as a detail fill and stays
  never-red. While a revisit hold renders, both `HELD_SPEED_FIELDS` retain their
  frozen values or canonical absence and are excluded from carry-forward.

**In-run dispute layer.** AA serves the leaderboard from its own Vercel cache,
so the run's two looks, `DISPUTE_LOOK_SPACING_SECONDS` (180 seconds) apart, can
land on different generations while a publish window is live. Each read is
fingerprinted by `generation_key`: a 16-hex sha256 prefix over the slug-sorted
records normalized on the leaderboard field universe minus the never-red
speed/latency family; absent, null, `""` and `$undefined` fold to one missing
marker before any comparison, and a cost object compares as the scalar of its
own `cost.total`. Reads sharing a fingerprint are one generation; the detail
route joins whichever generation it IS and never raises a dispute by itself (a
stale detail corpus is the known, precedence-handled state). One fingerprint on
the same slug set → the plain merge, byte for byte. Two fingerprints, or one
fingerprint on different slug sets (a model present in one look and absent from
the other: an inconsistency between the generations, Overseer ruling,
2026-10-06, issue #211) → the capture holds both, and leaderboard records carry
`genVariants`: one flat map per generation whose fields are that generation's
own published values.

**`genVariants` encoding: canonical order, canonical-first silence.**
- Variants are ordered by ascending `generation_key`, so the corpus bytes do not
  depend on which look a run read first. A record's plain fields are the first
  carrying variant's (the canonical generation's) value, gap-filled only where
  it lacks the field (a missing marker is a fill, never a winner). The
  cross-run generation hold has one exception: a rendered speed missing from the
  canonical carrying generation stays absent, never filled from another held
  generation.
- The map list is padded to one entry per generation, with `{}` at every
  generation that does not carry the model: `{}` means *not carried* (rendered
  as an em-dash side), and a carried variant is never `{}` (a carried record
  always publishes at least one variant field).
- Presence in one look and absence from the other keeps the model in the union,
  disputed by presence; this supersedes the reading that a model AA added or
  retired between the looks is a corpus union, never a conflict (Overseer
  ruling, 2026-10-06, issue #211).
- Never disputed, rendering the canonical value silently (the PM-approved
  canonical-first rule): identity and flag fields (`name`, `shortName`, `slug`,
  `creator`, `modelCreatorName`, `isOpenWeights`, `deprecated`, `isReasoning`,
  `intelligenceIndexIsEstimated`) and everything outside the variant map's
  fields (`ii`, `cost`, `gdpval`, `gdpvalCost`, `ctx`, `pin`, `pout`).
  Parameters, licence and release date are detail-fills with a single in-run
  source, so they cannot dispute either.
- The never-red family (`NEVER_RED_FIELDS`, hardcoded, never widened silently:
  a new speed-shaped field joins it only by a reviewed change) is the
  speed/latency set. It re-samples every hour, so two looks of the SAME
  generation routinely disagree on it and a dispute there would hold the page
  red permanently.
- `gdpvalCost` is recovered from each variant's own cost breakdown and is absent
  when that breakdown does not sum to its own total; never supplied from another
  generation's parts.

**Cross-run generation layer** (`--cross-run-lookback`):
- Remembers the newest 1000 distinct fingerprints in
  `data/aa-generation-state.json`, beside the capture. `revisit_key`
  fingerprints the published merged corpus over `DISPUTE_CAPABLE` only,
  excluding speed and unrendered payload churn.
- One-way movement (A → B, A → B → C) stays ordinary; a remembered revisit
  (A → B → A) holds both generations with `genVariants`. The state stores their
  AA-published `HELD_FIELDS`, including each side's cost breakdown, and renders
  their union in ascending revisit-key order. Other fields follow the current
  capture, so a hold does not manufacture payload removals in the differ;
  capture bytes may change while built rows stay fixed.
- Both rendered speed fields (`medianOutputTokensPerSecond` and
  `intelligenceIndexTimePerTask`) stay frozen for the length of a hold,
  including canonical absence.
- Alternating held members leaves the state and held render unchanged; a
  remembered nonmember joins without resetting the hold date. Only a fingerprint
  outside the remembered set ends the hold automatically and publishes alone;
  an evicted fingerprint counts as new. A retired side stays held until a new
  generation arrives or the state is cleared by hand.
- In-run disagreements leave this state unchanged: they render the frozen hold
  only if all their revisit keys are held, otherwise the in-run dispute renders.
- The date is written once at hold entry and rendered as "held since <date>"
  beside the dispute explanation; no state or no hold renders no such text. A
  hold older than 7 days prints a stdout warning without changing state.
- The repository tracks a bootstrap generated from its committed capture, so a
  quiet refresh's `git checkout -- data/` restores state too and a republish
  does not commit an untracked bootstrap. Later state changes are committed with
  data-moving hours, so runs remember the published hold without deriving it
  from git history. A missing state bootstraps from the previous capture; a
  no-hold `last` inconsistent with that capture is re-bootstrapped before a
  clean run's transition.
- The flag always writes state atomically on success; without it state is
  neither read nor written. The gate stages HEAD's state from git and fresh
  state from disk, including the fresh-only `--fresh-held` probe; unchanged
  held alternation answers `false`, while hold entry and a new generation change
  the page.

**Cross-run presence layer** (Overseer ruling, 2026-10-06, evening, on the
reopened issue #211). The in-run layer cannot see a flip between runs: a run
whose looks agree holds one generation, and an AA-side serving change lands as a
one-model flip of the published set. So the hourly refresh
(`fetch_aa.py --cross-run-lookback`, the refresh workflow's flag) reads the
previous committed capture before the fetch overwrites it, and a model present
in that capture's **firm set** (records without the `crossRunMerged` marker)
and absent from this run's fetch, or the reverse, is merged and marked disputed:
kept, both generations shown, red, paired.
- Presence-only: the previous corpus participates only through the diff slugs,
  and shared models take no previous-generation slot here.
- A record merged from the previous capture carries `crossRunMerged: true`: this
  run's fetch did not serve it, and the marker lets the NEXT run read its
  look-back correctly. A marked record is dispute state, not serving evidence,
  so this layer neither merges nor disputes it again. Outside a generation hold,
  a stable retirement settles within one further hour; the hold's frozen union
  can retain a retired side until its exit rule fires.
- A re-added model (served now, absent from the firm set; a brand-new model
  included, which therefore disputes red for its first hour) takes the
  empty-map previous slot and carries no marker: it is serving evidence the
  moment the run's own fetch returned it.
- A cross-run-disputed record's `genVariants` extends to one entry per
  generation the record is disputed across (the run's own generations plus the
  previous run's), the previous slot positioned by ascending `generation_key`
  over the joint field universe.

**Disputed hours.** The three-generation corner (the looks disagree AND the
detail route matches neither fingerprint) gives shared models no detail fills
from that run; the final look-back pass can restore their previous fills.
Without the cross-run look-back, a run whose looks agree writes no `genVariants`
key anywhere and is byte-identical to the single-generation capture; with it,
the same holds when the two slug sets agree, no generation hold renders and no
detail fill needs carrying. A caught presence flip or generation revisit writes
the disputed shape above.

## Commit subjects

There is no enforced commit grammar here — the merged history is written in
plain-English subjects. A subject written in conventional-commit shape
(`type(scope): summary`) carries one rule, enforced on every pull request by
`scripts/ci/commit_scopes.py`: a workflow's `name:` is allowed as a scope
only with the `ci` type. The type disambiguates shared names: `ci(refresh)`
changes the refresh workflow, while `fix(refresh)` would be a change no
reader can place. A subject that does not parse is listed by the check and
is never a failure.

## House style

- **Python** — stdlib only in the runtime, type hints where they help, no
  framework. Third-party packages belong in the toolchain files, not in
  `build.py` or the scripts.
- **The page is emitted as plain strings.** There is no template engine and no
  DOM library; match the surrounding code.
- Missing values render as `—` (em-dash), never `N/A` and never blank.
- pylint's DESIGN limits are raised rather than disabled, and file length is
  gated by the size-baseline workflow instead of pylint. If your patch trips
  a DESIGN limit, that is worth a look before you raise it further.

## Pull requests

Small and single-purpose beats large and comprehensive. The repository's PR
template is the form — fill it in rather than writing freehand. For anything
that changes the page, include the `diff_aa.py` output or a screenshot of the
before and after; a frontier that gains or loses a point is the kind of change
a reviewer cannot see in a diff of string literals.

If you are unsure whether something is a bug or intended, open an issue and
ask. A wrong premise caught early is cheaper than a correct fix to the wrong
problem.

## License

The repository and the page it builds are MIT-licensed — see
[LICENSE](LICENSE).
