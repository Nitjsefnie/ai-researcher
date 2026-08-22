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

Six workflows run. Five of them you can run locally:

```sh
python3 -m pytest -q                                             # tests
python3 -m coverage run --source=. --omit='tests/*,scripts/*' \
  -m pytest -q && python3 -m coverage report                     # coverage
git ls-files '*.py' | xargs python3 -m pylint                    # lint
git ls-files '*.py' | xargs python3 -m pycodestyle               # lint
python3 -m pyright                                               # types
pip-audit -r requirements-dev.txt -r requirements-test.txt       # audit
actionlint .github/workflows/*.yml && zizmor .github/workflows/  # actionlint
```

`python3 -m pip install -r requirements-dev.txt -r requirements-test.txt` gets
the pinned toolchain. Coverage is gated at **95%** — a ratchet set under the
current number, not a target. Raise it as coverage climbs; never lower it to
turn a build green. Note what that number can and cannot speak to: `build.py`
is ~1400 lines but only ~100 statements, because most of it is HTML, CSS and
JavaScript in string literals. The browser tests are what cover those.

The sixth, `codeql`, needs GitHub: it is gated on repository visibility,
because code scanning is free on public repositories and needs Code Security on
private ones.

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
