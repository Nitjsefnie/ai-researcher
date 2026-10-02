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

- **Every number comes from artificialanalysis.ai, and nowhere else.** Not lab
  blogs, model cards, technical reports, pricing pages, LMSYS, Vellum,
  swebench.com, livecodebench.com or journalism — not even to cross-check or to
  fill one gap. A model AA has not measured is **absent**, not interpolated. A
  patch that adds a second source will be declined no matter how good the
  source is: two sources with different harnesses produce numbers that cannot
  be compared on one axis, which is the only thing this page does.

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
  nearest-point hover, and one filter row above everything it scopes. **The
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
footer stamp is rendered only when `AA_SOURCE_COMMIT` is set at build time,
and nothing but the refresh workflow sets it for you. Build with

```sh
AA_SOURCE_COMMIT="$(git rev-parse HEAD)" python3 build.py
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
chromium`); `CHROMIUM_PATH` overrides both. Half the page's behaviour — the
frontier line, the tooltip, the filter chips, the sortable table — is only
reachable through those tests, so a change to the emitted JavaScript needs one.

## CI

Eight workflows run. Five of them you can run locally:

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
raise is the only writer on main. There are two floors: Python statement
coverage from the pytest run,
and JavaScript physical code-line coverage of the page's inline script,
measured through the browser suite (`tests/test_browser.py` records V8
coverage when `JS_COVERAGE_OUT` is set, and `scripts/ci/js_coverage.py` folds
the dump). A push to `main` whose coverage climbs more than 1.5 points past
the recorded measurement raises the floor automatically; nothing can relax
the file — a guard step compares it against the merge base and refuses any
change that lowers a value, on a pull request and on a direct push to
`main` alike, and `thresholds.py --check` refuses a working-tree copy below
the committed one.
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

naming the exact values the diff carries. The guard accepts a declared raise
only on a main **push** (the workflow passes `--allow-declared-raises` on the
push branch and never on a pull request), so a raise riding a PR refuses even
a perfectly declared one; a declaration whose values do not match the diff
exactly refuses too. Seeding
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
commit on main, one `Budget-Raise: <document> <key> <from> -> <to>` line
per raised leaf with the exact values the diff carries; pull requests
cannot carry a raise. Budgets are pinned to the CI cell that runs the gate —
the coverage job's ubuntu-latest runner, CPython 3.13.15 / valgrind
3.22.0 — and were seeded from that cell's own first measured counts
(build 171,504,264, capture_gate 267,669,619, diff_aa 222,551,193
startup-subtracted Ir), each plus 3% rounded up to the next million.
Authoring-box counts (CPython 3.13.14 / valgrind 3.24.0) sit about 10%
lower; the budgets follow the CI cell because it is the only place the
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

Three run only on GitHub. `codeql` is gated on repository visibility, because
code scanning is free on public repositories and needs Code Security on private
ones. `claim` watches issue comments: `/claim` assigns the commenter to an
unassigned open issue, and `/unclaim` and `/release` remove the commenter's own
assignment — self-service issue claiming for contributors without write access.

`refresh` is the capture → commit → publish of the page, and it fires two
ways, which are not equivalent. The workflow's own `schedule` trigger asks
for hourly (`11 * * * *`), but GitHub delivers scheduled runs best-effort:
measured over the 37 days ending 2026-09-28, it averaged five runs a day.
The hourly cadence is actually carried by an out-of-repository scheduler on
the maintainer's side, which calls the workflow's `workflow_dispatch` API
once an hour (24 runs a day since it started on 2026-09-25; dispatching
needs write access, so a contributor cannot reproduce this trigger — you
can only read its runs). **If that external dispatcher stops, nothing in
this repository changes and nothing alerts: the cadence silently degrades
to the schedule trigger's few runs a day.** `workflow_dispatch` is also
the only path a build-only change has to the live page: run the workflow
with `force: true` to rebuild and republish even when the fresh capture
would render the identical page — the page the code produces has moved
while the data has not, and only a forced run publishes that (the workflow
header explains the rendered no-change gate — the page is built from both
captures with provenance normalized out — and the stale-page case in
full).

One hourly-flow case reads differently since #118: when AA's two routes
disagree, `refresh` no longer skips the hour — `fetch_aa.py` writes a
disagreement snapshot and the run publishes a **disputed page** (a banner,
both routes' values in the disputed cells, disputed models off the
frontiers) until the routes converge and the page reverts on its own. A
disputed commit's subject says so: "Publish disputed capture: AA routes
disagree (issue #118)". There is no time bound on a disputed window; the
banner is the alarm.

**Actions are hash-pinned**, with the version in a trailing comment. Do not
"tidy" one back to `@v4`: a tag is a moving pointer, and these jobs hold a
repository token. Dependabot keeps the hashes current.

**`.gitignore` is deny-by-default**: `*` first, then each shipped path named
back, with every kept directory re-opened and its contents denied again. A new
file of an unlisted type is invisible to git and will NOT appear in `git
status` as untracked — it simply never appears. `git check-ignore -v <path>`
names the rule hiding it.

## House style

- **Python** — stdlib only in the runtime, type hints where they help, no
  framework. Third-party packages belong in the toolchain files, not in
  `build.py` or the scripts.
- **The page is emitted as plain strings.** There is no template engine and no
  DOM library; match the surrounding code.
- Missing values render as `—` (em-dash), never `N/A` and never blank.
- pylint's DESIGN limits are raised rather than disabled. If your patch trips
  one, that is worth a look before you raise it further.

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
