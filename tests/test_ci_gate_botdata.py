"""The ci-gate bot-data class: classifier and fold pins.

The bot-data classification (any non-empty subset of the refresh bot's
push signature -> the cheap class) and the aggregate fold's data-only
branch are the narrowing additions to the ci-gate classifier and
aggregate fold, so their pins live in their own module rather than
growing test_ci_gate_modules.py past the test size ceiling. Loader shape
matches that file: scripts/ci is not a package and deliberately has no
__init__.py — it holds standalone CI entry points, so both modules load
by path here too.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    """Import scripts/ci/<name>.py by path."""
    path = REPO_ROOT / "scripts" / "ci" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


classify = _load("classify_changes")
aggregate = _load("aggregate_gate")


DOCS = ["README.md", "docs/guide.md", "LICENSE", ".gitignore"]
CODE = [
    "build.py", "scripts/fetch_aa.py", ".github/workflows/tests.yml",
    ".github/ci-thresholds.json", "scripts/ci/classify_changes.py",
    "scripts/capture_gate.py",
]


# ---------------------------------------------------------------------------
# classify_changes: the bot-data class
# ---------------------------------------------------------------------------


def test_bot_signature_is_exactly_the_refresh_bots_four_files():
    # The hourly refresh's fixed `git add` list in refresh.yml stages
    # the two captures, their capture stamp and the built page as ONE
    # commit, though an hour's diff stages only the subset whose bytes
    # moved. The refresh job runs the full suite against the fresh
    # capture BEFORE pushing, so the signature's paths are exactly the
    # ones that pre-test covers.
    assert classify.BOT_SIGNATURE == frozenset({
        "data/aa-raw-models.json",
        "data/aa-raw-coding-agents.json",
        "data/captured-at.txt",
        "out/frontier-models.html",
    })


def test_bot_signature_names_every_file_the_refresh_workflow_adds():
    # Lockstep with refresh.yml: its fixed `git add` list is the
    # signature's source of truth, and since issue #200 it is the ONLY
    # `git add` the workflow runs — the conditional window-file adds are
    # gone with the disagreement state, so the signature covers every path
    # an hour's commit stages. A future fifth `git add` must move the
    # signature with it, so the pin compares the sets, not one spelling.
    raw = (REPO_ROOT / ".github" / "workflows" / "refresh.yml").read_text(
        encoding="utf-8")
    fixed = "git add data/aa-raw-models.json data/aa-raw-coding-agents.json \\\n" \
            "                  data/captured-at.txt out/frontier-models.html"
    assert fixed in raw
    adds = re.findall(r"^\s*git add(?:[^\n\\]|\\\n)*", raw, re.MULTILINE)
    assert len(adds) == 1, adds
    # The one `git add` spans a backslash continuation, so flatten it
    # before reading the paths off it.
    staged = {path for path in adds[0].replace("\\\n", " ").split()
              if path.startswith(("data/", "out/"))}
    assert staged == set(classify.BOT_SIGNATURE)


def test_data_only_accepts_the_signature_and_only_its_subsets():
    # The empty set opens the refusals the name's "only" covers: nothing
    # changed is not a bot push, and not data-only either.
    assert not classify.data_only([])
    assert classify.data_only([
        "data/aa-raw-models.json", "data/aa-raw-coding-agents.json",
        "data/captured-at.txt", "out/frontier-models.html"])
    # Listing order and duplicates are set noise, not a fifth path.
    assert classify.data_only([
        "out/frontier-models.html", "data/captured-at.txt",
        "data/aa-raw-models.json", "data/aa-raw-coding-agents.json",
        "data/aa-raw-models.json"])
    # An hour's commit carries only the subset of the four whose bytes
    # moved (git omits byte-identical files from the diff) — the real
    # refresh push that ran the full matrix by mistake (issue #212,
    # run 37490807791) touched exactly these two.
    assert classify.data_only([
        "data/aa-raw-models.json", "out/frontier-models.html"])
    assert classify.data_only(["data/captured-at.txt"])


def test_data_only_refuses_a_fifth_path():
    for intruder in (DOCS + CODE + ["data/captured-at-old.txt"]):
        assert not classify.data_only([
            "data/aa-raw-models.json", "data/aa-raw-coding-agents.json",
            "data/captured-at.txt", "out/frontier-models.html",
            intruder]), intruder


def test_data_only_accepts_any_proper_subset():
    # Any non-empty subset of the four is a shape the bot's push takes:
    # an hour's commit carries only the files whose bytes moved, so a
    # dropped file is an hour with one byte-identical artifact, not a
    # hand-staged change to run the full matrix over.
    full = ["data/aa-raw-models.json", "data/aa-raw-coding-agents.json",
            "data/captured-at.txt", "out/frontier-models.html"]
    for dropped in full:
        assert classify.data_only(
            [path for path in full if path != dropped]), dropped


def test_classify_the_bots_signature_gets_the_cheap_class():
    docs_only, data_only, reason = classify.classify(
        {"name": "pull_request", "repository": "o/r", "pull_request": "17"},
        lambda argv: "data/aa-raw-models.json\n"
                     "data/aa-raw-coding-agents.json\n"
                     "data/captured-at.txt\n"
                     "out/frontier-models.html\n",
    )
    assert (docs_only, data_only) == (False, True)
    assert "data-only" in reason


def test_classify_mixed_capture_and_code_runs_everything():
    # The class is the SET of changed paths, never individual files: one
    # code file beside the data files is a full run.
    docs_only, data_only, reason = classify.classify(
        {"name": "pull_request", "repository": "o/r", "pull_request": "17"},
        lambda argv: "data/aa-raw-models.json\nbuild.py\n",
    )
    assert (docs_only, data_only) == (False, False)
    assert "outside documentation" in reason


def test_classify_capture_beside_docs_runs_everything():
    docs_only, data_only, reason = classify.classify(
        {"name": "pull_request", "repository": "o/r", "pull_request": "17"},
        lambda argv: "data/aa-raw-models.json\nREADME.md\n",
    )
    assert (docs_only, data_only) == (False, False)
    assert "outside documentation" in reason


def test_write_outputs_records_the_data_only_narrowing(tmp_path):
    out = tmp_path / "output.txt"
    classify.write_outputs(str(out), False, True,
                           "bot-data-only change: 4 paths")
    assert out.read_text(encoding="utf-8") == (
        "docs_only=false\n"
        "data_only=true\n"
        "reason=bot-data-only change: 4 paths\n"
    )


# ---------------------------------------------------------------------------
# aggregate_gate: the data-only fold
# ---------------------------------------------------------------------------

# Lockstep with the fold's own leg tuple, not a copy of the modules
# file's: the pins here judge exactly the document aggregate_gate
# expects, and a leg added there moves this document with it.
LEGS = aggregate.EXPECTED_LEGS


def _needs(cheap="success", expensive="skipped", data_only="true",
           docs_only="false"):
    """A needs document shaped for the data-only fold pins.

    Cheap legs sit at ``cheap``, every other leg at ``expensive``, so
    the helper states the class split once instead of each test looping
    over legs by hand.
    """
    doc = {"classify": {"result": "success",
                        "outputs": {"docs_only": docs_only,
                                    "data_only": data_only}}}
    for leg in LEGS[1:]:
        doc[leg] = {"result": cheap if leg in aggregate.CHEAP_LEGS
                    else expensive}
    return doc


def test_aggregate_data_only_skips_pass_and_names_the_cheap_legs():
    verdict, message = aggregate.decide(_needs())
    assert verdict == aggregate.PASSED
    assert "data-only" in message
    for cheap in sorted(aggregate.CHEAP_LEGS):
        assert cheap in message


def test_aggregate_data_only_cannot_skip_the_cheap_legs():
    # Fail closed: a data-only run that skipped lint or actionlint
    # anyway is a fold/workflow disagreement, and the aggregate must go
    # red — the two cheap legs are why the class exists.
    verdict, message = aggregate.decide(_needs(cheap="skipped"))
    assert verdict == aggregate.FAILED
    assert "lint=skipped" in message
    assert "actionlint=skipped" in message


def test_aggregate_data_only_output_missing_reads_as_not_data_only():
    # Fail closed: a classify entry without the data_only output cannot
    # turn a skipped leg into a pass.
    doc = _needs()
    doc["classify"]["outputs"] = {"docs_only": "false"}
    doc["tests"] = {"result": "skipped"}
    verdict, message = aggregate.decide(doc)
    assert verdict == aggregate.FAILED
    assert "tests=skipped" in message


def test_aggregate_non_data_only_skip_fails():
    # A skip beside a data_only=false output is still a disagreement,
    # the way a non-docs skip has always been.
    doc = _needs(data_only="false", expensive="success")
    doc["codeql"] = {"result": "skipped"}
    verdict, message = aggregate.decide(doc)
    assert verdict == aggregate.FAILED
    assert "codeql=skipped" in message


def test_aggregate_summary_names_the_data_only_narrowing(tmp_path):
    doc = _needs()
    doc["classify"]["outputs"]["reason"] = "bot-data-only change: 4 paths"
    summary = tmp_path / "summary.md"
    assert aggregate.main_with(doc, summary_path=str(summary)) == 0
    text = summary.read_text(encoding="utf-8")
    assert "data-only narrowing: true" in text
    assert "classification: bot-data-only change: 4 paths" in text
    assert "data-only" in text
