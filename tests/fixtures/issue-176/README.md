# tests/fixtures/issue-176/ — the 909ca49 disagreement window, trimmed

Committed fixture for the stale-route staleness rule (issue #176, Overseer
ruling (delegated by the maintainer), 2026-10-04). Derived mechanically from
the git history; never hand-edited.

## Derivation

    git show 909ca49:data/aa-disagreement-snapshot.json
    git show a0ff4ad:data/aa-raw-models.json

`disagreement-snapshot.json` is the 909ca49 refusal's snapshot with
`leaderboard` and `detail` trimmed to a representative subset of models (full
records byte-verbatim; the subset's order follows the derivation's selection
list, not the upstream arrays; header fields verbatim):
`deepseek-v4-pro-non-reasoning` (the cost.total move — the absence case),
`a-x-k2` (score-only move), `claude-fable-5` (name + score), and the
undisputed control `apertus-70b-instruct`. `disagreements` keeps every entry
belonging to those slugs: 9 of the original 251 across 198 models.

`last-capture.json` is the same slugs of a0ff4ad's merged capture
(`data/aa-raw-models.json` at HEAD when the window was captured) — the last
AGREEING capture the stale detail route still serves.

Asserted at derivation time and re-asserted by the suite: for every kept
entry, the detail-route value equals the a0ff4ad baseline and the
leaderboard-route value does not (251/251 vs 0/251 over the full window; 9/9
vs 0/9 here).

## What the tests may derive from it, and how

- **Detail-stale direction** (the real window): baseline = `last-capture.json`
  verbatim.
- **Leaderboard-stale direction** (synthetic window, same payloads): the
  baseline re-pairs the shape-split total with the leaderboard's copy (an
  agreeing capture always pairs agreeing values) and otherwise merges the
  two payloads (`merge_captures`, leaderboard's copy of every shared value,
  detail-only fields from the detail payload). This models a window where the
  leaderboard's generation was already published and the detail route has
  since moved. The #117 window (2026-10-02) ran this direction for real.
  The helper is `leaderboard_stale_baseline()` in tests/test_fetch_aa.py.

The new-slug fallback case (a disputed slug with no row in the last capture)
is a synthetic extension added in the tests (a slug outside the fixture's
models), not a fixture file.
