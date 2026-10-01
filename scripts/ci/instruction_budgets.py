#!/usr/bin/env python3
"""Gate the Python pipeline's CPU work on instruction-count budgets (issue #110).

CI bounds the page's reader-side work (perf budgets, issue #109) and the
suite's line coverage, but nothing bounded the pipeline's own CPU work: a
patch could make build.py, diff_aa.py or capture_gate.py do an unbounded
amount of extra work and every gate would stay green. This gate measures
each pipeline target under valgrind callgrind on a COMMITTED FIXTURE
capture -- tests/fixtures/pipeline/, a fixed miniature capture -- and
holds each target's instruction count against the integer maxima in
.github/instruction-budgets.json.

Why a fixture: the budgets must be invariant to capture size (standing
rule -- anything the refresh suite runs may not couple to AA's data
volume), so the gate never touches data/. The mini capture is copied from
the fixture into a throwaway mini-tree together with the targets' code
from the current tree, so every measured run exercises exactly the code
under test and nothing of the live data directory. capture_gate.py reads
its HEAD side with ``git show HEAD:data/<capture>``, so the mini-tree is
git-inited and its captures committed before the runs start.

Measured quantity: retired instructions (Ir) from callgrind, per target,
minus the same measurement of ``python3 -c pass`` -- the interpreter
startup every target pays regardless. Every budget value is that
startup-subtracted delta. Budgets are integer MAXIMA: a target may use
fewer instructions, never more, and a measured value equal to its budget
passes.

Determinism pins, and why they are load-bearing (measured on the
authoring box, Python 3.13.14, valgrind 3.24.0): without
PYTHONDONTWRITEBYTECODE the first run compiles and writes .pyc files and
the second loads them -- a 1.6% run-to-run swing on a bare pair of runs;
PYTHONHASHSEED=0 removes dict-order jitter; PYTHONNOUSERSITE=1 keeps
user-site .pth execution out of every count. Under the pins the observed
run-to-run spread was under 0.002% (the exact spreads this branch
measured are recorded in CONTRIBUTING.md); the 3% margin covers CI's
different CPython and valgrind builds, and the budgets themselves are
calibrated by CI's own first runs -- the check mode always prints its
measured counts.

Every run executes under ``nice -n 19 timeout <seconds>``: nice, so the
measurement yields to everything else on the box, timeout, so a hung
target is a failed gate rather than a hung CI job (callgrind runs 20-50x
slower than the instrumented program alone; 180s per run bounds four runs
at worst 12 of the coverage job's 30 minutes).

The gate writes ONLY under one tempfile directory: the mini-tree, the
callgrind output files and every target's own scratch (build's out/,
capture_gate's temp sides) live inside it, because each target resolves
its ROOT from its own __file__. Nothing lands in the repository tree.

Exit codes (mirrors scripts/ci/perf_budgets.py's contract):
  0  every budget met (a measured value equal to its budget passes);
  1  at least one budget exceeded -- one stderr line per offender, measured
     vs budget, after the per-target table on stdout;
  2  the budgets document is missing or invalid;
  3  the measure path failed (valgrind missing, the fixture missing or
     corrupt, a target crashed or timed out, a callgrind output file
     missing or unparseable) -- a broken harness must never read as a
     budget breach.

Default mode is the check. ``--measure`` prints the counts and exits 0
without comparing; that is how the budgets were bootstrapped and how a
later tighten-only PR re-measures.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUDGETS = ROOT / ".github" / "instruction-budgets.json"
FIXTURE = ROOT / "tests" / "fixtures" / "pipeline"
SCHEMA_VERSION = 1
BASELINE_ARGV = ("-c", "pass")
# Per-run wall bound; see the module docstring's sizing note.
TIMEOUT_SECONDS = 180

# The pipeline targets, in budget-document order: name -> the argv the
# mini-tree runs (after the interpreter). diff_aa gets the two identical
# fixture captures as file arguments, so its report is empty and its exit
# is 0; capture_gate gets no arguments and compares HEAD's committed
# captures against the working data/ files.
TARGETS = (
    ("build", ("build.py",)),
    ("capture_gate", ("scripts/capture_gate.py",)),
    ("diff_aa", ("scripts/diff_aa.py", "data/aa-raw-models.json",
                 "data/aa-raw-models.json")),
)
SCRIPT_NAMES = tuple(name for name, _argv in TARGETS)

# The fixture files seeded into the mini-tree's data/ directory.
FIXTURE_FILES = ("aa-raw-models.json", "aa-raw-coding-agents.json",
                 "captured-at.txt")

# The measurement environment. These pins are load-bearing: see the module
# docstring's determinism note.
RUN_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
}

_TOP_LEVEL_FIELDS = ("schema_version", "scripts")


def _reject_constant(value):
    raise ValueError(f"non-finite JSON number: {value}")


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode(raw):
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(text, parse_constant=_reject_constant,
                          object_pairs_hook=_object_pairs)
    except UnicodeDecodeError as error:
        raise ValueError(f"invalid budgets JSON: {error}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid budgets JSON: {error}") from None


def _integer(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, float):
        raise ValueError(f"{name} must be an integer")
    if not isinstance(value, int):
        raise ValueError(f"{name} must be a JSON number")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _required_fields(value, expected, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    for field in expected:
        if field not in value:
            raise ValueError(f"missing field: {name}.{field}")
    for field in value:
        if field not in expected:
            raise ValueError(f"unknown field: {field}")


def validate_budgets(data):
    """Validate a decoded budgets document; return it normalised.

    Exactly the two top-level fields and exactly the three script maxima:
    unknown or missing fields are refused (an unknown key can never become
    a budget a later gate silently ignores).
    """
    _required_fields(data, _TOP_LEVEL_FIELDS, "budgets")
    if _integer(data["schema_version"], "schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version: {data['schema_version']}")
    scripts = data["scripts"]
    _required_fields(scripts, SCRIPT_NAMES, "scripts")
    return {
        "schema_version": SCHEMA_VERSION,
        "scripts": {name: _integer(scripts[name], f"scripts.{name}")
                    for name in SCRIPT_NAMES},
    }


def load_budgets(path=BUDGETS):
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read budgets: {error}") from None
    return validate_budgets(_decode(raw))


def gate(budgets, measured):
    """Findings for a measurement against budgets; [] when all are met.

    A measured value EQUAL to its budget passes -- budgets are maxima. A
    measurement missing a target is a loud error, never a pass.
    """
    if not isinstance(measured, dict):
        raise ValueError("measurement must be an object")
    findings = []
    for name in SCRIPT_NAMES:
        if name not in measured:
            raise ValueError(f"measurement is missing script: {name}")
        value = measured[name]
        budget = budgets["scripts"][name]
        if value > budget:
            findings.append(
                f"scripts.{name}: head {value} exceeds base {budget}")
    return findings


def summary_total(path):
    """The instruction total in one callgrind output file.

    The documented callgrind format puts a ``summary: <count>`` line at
    the end of each collected part. The runs this gate makes are
    single-part (one thread, no --separate-* options), so the file's one
    summary line is the run's total; a file that somehow carries several
    parts parses to the LAST summary line, and one with no parseable
    summary line is a broken measure, not a zero.
    """
    try:
        text = Path(path).read_text(encoding="utf-8",
                                    errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"cannot read callgrind output {path}: {error}") from None
    found = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("summary:"):
            found = stripped[len("summary:"):].strip()
    if found is None:
        raise ValueError(f"no summary line in callgrind output {path}")
    try:
        return int(found)
    except ValueError:
        raise ValueError(
            f"unparseable summary line in callgrind output {path}: {found}"
        ) from None


class MeasureError(Exception):
    """The measure path failed -- exit 3, never a budget breach."""


def _require_valgrind():
    if shutil.which("valgrind") is None:
        raise MeasureError(
            "valgrind is not installed -- the instruction budgets gate "
            "measures instruction counts with callgrind (apt-get install "
            "valgrind)")


def _callgrind(out_file, cwd, argv, quiet=False):
    """One valgrind callgrind run over ``python3 <argv>``; the result.

    nice -n 19 so the measurement yields to everything else on the box;
    timeout so a hung target fails the gate instead of hanging the job.
    RUN_ENV's pins are load-bearing -- see the module docstring. check=False
    is deliberate: the returncode is inspected below.
    """
    env = dict(os.environ)
    env.update(RUN_ENV)
    return subprocess.run(  # pylint: disable=subprocess-run-check
        ["nice", "-n", "19", "timeout", str(TIMEOUT_SECONDS), "valgrind",
         "--tool=callgrind", f"--callgrind-out-file={out_file}",
         sys.executable, *argv],
        cwd=str(cwd), env=env, check=False, text=True,
        # build.py's page summary is loud and useless here -- /dev/null.
        # Every other run's stdout is captured (capture_gate's must say
        # "false") and every run's stderr is kept for the failure message.
        stdout=subprocess.DEVNULL if quiet else subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _tail(text, limit=200):
    """The last non-empty stderr line, trimmed to the message limit."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return "no stderr"
    return lines[-1][:limit]


def _stage_tree(mini):
    """The mini-tree: the code under test plus the fixture capture.

    build.py and page_format.py sit at the mini-tree root; the two scripts
    keep their scripts/ layout because both resolve their ROOT as their
    own parent's parent. Raises MeasureError when the fixture is missing
    or corrupt -- a broken input is exit 3, never a zero measurement.
    """
    for name in ("build.py", "page_format.py"):
        shutil.copy2(ROOT / name, mini / name)
    (mini / "scripts").mkdir()
    for name in ("capture_gate.py", "diff_aa.py"):
        shutil.copy2(ROOT / "scripts" / name, mini / "scripts" / name)
    data = mini / "data"
    data.mkdir()
    for name in FIXTURE_FILES:
        source = FIXTURE / name
        if not source.is_file():
            raise MeasureError(f"fixture file missing: {source}")
        if name.endswith(".json"):
            try:
                json.loads(source.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise MeasureError(
                    f"fixture file corrupt: {source}: {error}") from None
        shutil.copy2(source, data / name)


def _commit_captures(mini):
    """git-init the mini-tree and commit the two captures at HEAD.

    capture_gate.py reads its HEAD side with ``git show HEAD:data/<capture>``
    at cwd=ROOT, so the mini-tree must be a repository whose HEAD carries
    the fixture captures. The identity is a throwaway; commit signing is
    disabled explicitly in case the environment signs commits.
    """

    def git(*args):
        result = subprocess.run(  # pylint: disable=subprocess-run-check
            ["git", "-C", str(mini), *args],
            capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise MeasureError(
                f"git {' '.join(args)} failed in the mini-tree: "
                f"{result.stderr.strip()}")
        return result

    git("init", "-q", "-b", "main")
    git("add", "data/aa-raw-models.json", "data/aa-raw-coding-agents.json")
    git("-c", "user.name=t", "-c", "user.email=t@t",
        "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")


def measure():
    """Each target's startup-subtracted instruction count, measured.

    Four callgrind runs inside one tempfile tree: the three targets over
    the mini fixture and one ``python3 -c pass`` baseline. Every budget
    value is (target total) minus (baseline total) -- the interpreter
    startup every target pays regardless of what its code does.
    """
    _require_valgrind()
    with tempfile.TemporaryDirectory(
            prefix=".instruction-budgets-") as tmp:
        tmp = Path(tmp)
        mini = tmp / "mini"
        mini.mkdir()
        _stage_tree(mini)
        _commit_captures(mini)
        totals = {}
        for name, argv in (*TARGETS, ("baseline", BASELINE_ARGV)):
            out_file = tmp / f"cg-{name}.out"
            # build.py's page summary is devnulled; see _callgrind.
            quiet = name == "build"
            result = _callgrind(out_file, mini, argv, quiet=quiet)
            if result.returncode != 0:
                detail = _tail(result.stderr)
                if result.returncode == 124:
                    detail = (f"timed out after {TIMEOUT_SECONDS}s "
                              f"({detail})")
                raise MeasureError(
                    f"{name} failed under callgrind (exit "
                    f"{result.returncode}): {detail}")
            if name == "capture_gate" and result.stdout.strip() != "false":
                raise MeasureError(
                    f"capture_gate printed {result.stdout.strip()!r}, not "
                    "'false' -- the mini fixture is not self-consistent")
            totals[name] = summary_total(out_file)
    baseline = totals.pop("baseline")
    return {name: total - baseline for name, total in totals.items()}


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", action="store_true",
                        help="print each target's measured instruction count "
                             "and exit 0 -- no comparison (bootstraps and "
                             "re-measures the budgets)")
    parser.add_argument("--budgets", type=Path, default=BUDGETS,
                        help="budgets document (default: %(default)s)")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.measure:
        try:
            measured = measure()
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Deliberately broad: whatever escapes the measure path is a
            # broken HARNESS, and its exit code must not collide with
            # "exceeded" (perf_budgets' contract).
            print(f"measurement failed: {error}", file=sys.stderr)
            return 3
        for name in SCRIPT_NAMES:
            print(f"{name}: {measured[name]} instructions "
                  "(startup-subtracted)")
        return 0
    try:
        budgets = load_budgets(args.budgets)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    try:
        measured = measure()
    except Exception as error:  # pylint: disable=broad-exception-caught
        # Deliberately broad: same contract as the --measure arm.
        print(f"measurement failed: {error}", file=sys.stderr)
        return 3
    for name in SCRIPT_NAMES:
        value = measured[name]
        budget = budgets["scripts"][name]
        verdict = "ok" if value <= budget else "exceeded"
        print(f"scripts.{name}: measured {value}  budget {budget}  {verdict}")
    findings = gate(budgets, measured)
    if findings:
        for line in findings:
            print(line, file=sys.stderr)
        return 1
    print("instruction budgets met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
