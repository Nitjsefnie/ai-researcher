# ai-researcher

Tracks frontier AI models and publishes one comparison artifact: **intelligence
against cost per task**, live at
[`docs.nitjsefni.eu/d/ai-researcher/frontier-models`](https://docs.nitjsefni.eu/d/ai-researcher/frontier-models).

Every number comes from [artificialanalysis.ai](https://artificialanalysis.ai/)
and nowhere else. A model AA has not measured is absent from the page, not
estimated from a lab blog or a pricing page. That is a standing decision, and
`AGENTS.md` carries the reasoning; read it before changing what the page shows.

## What the page plots

- **y** — Artificial Analysis Intelligence Index (v4.1), AA's composite of
  GDPval-AA v2, τ³-Banking, Terminal-Bench v2.1, SciCode, Humanity's Last Exam,
  GPQA Diamond, CritPt, AA-Omniscience and AA-LCR.
- **x** — cost per task in USD, log scale. AA's *measured* spend to run the
  model through the index, not a quoted per-token price. A verbose reasoning
  model therefore costs more than its sticker price implies, which is the whole
  reason for using the measured figure.

The **efficient frontier** — models nothing cheaper matches or beats — is the
analytical payload. Everything off it is strictly dominated.

## Pipeline

AA ships the leaderboard as a Next.js RSC flight payload; there is no public
JSON API, so the extractor reassembles it.

```sh
python3 scripts/fetch_aa.py     # → data/aa-raw-models.json  (captured artifact)
python3 scripts/diff_aa.py      # what moved since the last capture
python3 build.py                # → out/frontier-models.html

python3 ~/.agent-bundle/scripts/docs_hub.py publish ./out/frontier-models.html \
  --slug ai-researcher/frontier-models \
  --title "Frontier models — intelligence vs cost per task" \
  --from ai-researcher --tags benchmarks,comparison,interactive,ai \
  --project ai-researcher
```

`fetch_aa.py` exits nonzero when the flight payload or the model schema changes
shape. That is the signal to re-read the page, not to hand-fix JSON — never
hand-edit `data/aa-raw-models.json`.

Re-publishing the same slug adds a version and never destroys history.

## Working on it

The runtime is pure stdlib. Everything third-party is a tool, pinned in
`requirements-dev.txt` (lint, types) and `requirements-test.txt` (test, coverage,
browser).

```sh
python3 -m pip install -r requirements-dev.txt -r requirements-test.txt
python3 -m playwright install chromium   # only if you have no system Chromium

python3 -m pytest -q                     # NOT the bare `pytest` binary — see below
git ls-files '*.py' | xargs python3 -m pylint
git ls-files '*.py' | xargs python3 -m pycodestyle
python3 -m pyright
```

Each of those four is a CI gate under `.github/workflows/`, so a green local run
is a green push.

**The runner must be `python3 -m pytest`, from the repo root.** `tests/` has no
`__init__.py` and the tests `import build` from the root, so the root has to be
on `sys.path` — only the `-m` form puts the cwd there. The bare `pytest` binary
collects the same files and every test errors on the import.

`tests/test_browser.py` drives the built page in a real headless Chromium. It
prefers a system browser at `/usr/bin/chromium` and falls back to playwright's
own download; `CHROMIUM_PATH` overrides both.

`.gitignore` is deny-by-default: `*` hides everything and each shipped file is
named back. A new file does not show up in `git status` as untracked — it simply
never appears. Add its rule, and `git check-ignore -v <path>` will name the rule
hiding it if it still doesn't.

## What this repo is not

Not a benchmark harness — AA runs the evals, we read their numbers. Not a
live-scraping dashboard — refreshes are deliberate and diffed. Not a model
directory — if AA has not measured cost per task for it, it is not on the chart.
