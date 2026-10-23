"""Environment readers preserve compatibility and workflow hand-offs."""
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

import _workflowrun
import test_browser
import test_capture_gate
import test_check_committed_page
import test_diff_coverage

import build
from scripts.ci import aggregate_gate, classify_changes, perf_budgets

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = ["prefixed", "legacy", "both", "neither"]


def _environment(monkeypatch, name, case, current, legacy):
    """Isolate both spellings; an ambient setting cannot decide a case."""
    old = name.removeprefix("AI_RESEARCHER_")
    monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(old, raising=False)
    if case in ("prefixed", "both"):
        monkeypatch.setenv(name, current)
    if case in ("legacy", "both"):
        monkeypatch.setenv(old, legacy)


@pytest.mark.parametrize("case", CASES)
def test_source_commit_precedence(monkeypatch, case):
    _environment(monkeypatch, "AI_RESEARCHER_AA_SOURCE_COMMIT", case,
                 "a" * 40, "b" * 40)
    with tempfile.TemporaryDirectory(dir=build.ROOT) as tmp:
        output = pathlib.Path(tmp) / "page.html"
        monkeypatch.setattr(build, "OUT", output)
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()
        page = output.read_text(encoding="utf-8")
    if case == "neither":
        assert "Source commit <code>" not in page
    else:
        expected = "b" if case == "legacy" else "a"
        assert f"Source commit <code>{expected * 40}</code>" in page


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("helper", ["perf", "capture", "committed"])
@pytest.mark.parametrize("fails", [False, True])
def test_unstamped_build_restores_both_spellings(monkeypatch, case, helper, fails):
    _environment(monkeypatch, "AI_RESEARCHER_AA_SOURCE_COMMIT", case,
                 "a" * 40, "b" * 40)
    before = dict(os.environ)

    def refusing_build(**_kwargs):
        raise ValueError("fixture build refusal")

    if fails:
        monkeypatch.setattr(build, "main", refusing_build)
    with tempfile.TemporaryDirectory(dir=build.ROOT) as tmp:
        output = pathlib.Path(tmp)
        # white-box: each helper promises an unstamped build and restoration.
        # pylint: disable=protected-access

        def render():
            if helper == "perf":
                return perf_budgets._build_page(build, output / "page.html").decode("utf-8")
            if helper == "capture":
                return test_capture_gate.capture_gate._render_side(
                    output / "side", (test_capture_gate.FIXTURE_MODELS,
                                      test_capture_gate.FIXTURE_AGENTS), None, None)
            return test_check_committed_page.check_committed_page.rebuild_page()

        if fails:
            with pytest.raises(ValueError, match="fixture build refusal"):
                render()
        else:
            assert "Source commit <code>" not in render()
    assert dict(os.environ) == before


@pytest.mark.parametrize("case", CASES)
def test_chromium_precedence(monkeypatch, tmp_path, case):
    current, legacy = tmp_path / "current", tmp_path / "legacy"
    current.touch()
    legacy.touch()
    _environment(monkeypatch, "AI_RESEARCHER_CHROMIUM_PATH", case,
                 str(current), str(legacy))
    expected = legacy if case == "legacy" else current
    if case == "neither":
        expected = pathlib.Path("/usr/bin/chromium")
        expected = expected if expected.exists() else None
    assert perf_budgets._chromium_executable() == expected  # pylint: disable=protected-access


@pytest.mark.parametrize("case", CASES)
def test_aggregate_precedence(monkeypatch, tmp_path, case):
    good = {leg: {"result": "success"}
            for leg in aggregate_gate.EXPECTED_LEGS}
    bad = {**good, "tests": {"result": "failure"}}
    _environment(monkeypatch, "AI_RESEARCHER_NEEDS_JSON", case,
                 json.dumps(good), json.dumps(bad))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    assert aggregate_gate.main() == (1 if case in ("legacy", "neither") else 0)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("name,field", [
    ("AI_RESEARCHER_PR_NUMBER", "pull_request"),
    ("AI_RESEARCHER_BEFORE_SHA", "before"),
])
def test_classifier_precedence(monkeypatch, case, name, field):
    _environment(monkeypatch, name, case, "current", "legacy")
    event = classify_changes.event_from_environment()
    expected = {"prefixed": "current", "legacy": "legacy",
                "both": "current", "neither": None}
    assert event[field] == expected[case]


@pytest.mark.parametrize("case", CASES)
def test_browser_coverage_precedence(monkeypatch, tmp_path, case):
    current, legacy = tmp_path / "current.json", tmp_path / "legacy.json"
    _environment(monkeypatch, "AI_RESEARCHER_JS_COVERAGE_OUT", case,
                 str(current), str(legacy))
    test_browser.flush_page_coverage(SimpleNamespace(
        _open_pages=[], _coverage_entries=[{"url": "fixture"}]))
    assert current.exists() == (case in ("prefixed", "both"))
    assert legacy.exists() == (case == "legacy")
    if case != "neither":
        output = legacy if case == "legacy" else current
        assert json.loads(output.read_text(encoding="utf-8")) == [{"url": "fixture"}]


@pytest.mark.parametrize("case", CASES)
def test_child_coverage_precedence(monkeypatch, case):
    _environment(monkeypatch, "AI_RESEARCHER_COVERAGE_MEASURE_CHILDREN_RC",
                 case, "current.rc", "legacy.rc")
    seen = []

    def run(args, **_kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)
    test_diff_coverage._run_cli([sys.executable, "child.py"])  # pylint: disable=protected-access
    expected = [sys.executable, "child.py"]
    if case != "neither":
        rc = "legacy.rc" if case == "legacy" else "current.rc"
        expected = [sys.executable, "-m", "coverage", "run",
                    "--parallel-mode", "--rcfile", rc, "child.py"]
    assert seen == [expected]


def _step_environment(workflow, job, name):
    """Resolve a named producer's environment in the workflow document."""
    return _workflowrun.step_by_name(
        ROOT / ".github" / "workflows" / workflow, job, name)["env"]


def test_classifier_workflow_handoff(monkeypatch):
    expressions = _step_environment(
        "ci-gate.yml", "classify", "Classify the changed paths")
    assert expressions["AI_RESEARCHER_PR_NUMBER"] == "${{ github.event.pull_request.number }}"
    assert expressions["AI_RESEARCHER_BEFORE_SHA"] == "${{ github.event.before }}"
    env = {key: "7" if "pull_request" in value else "b" * 40
           for key, value in expressions.items()}
    env.update(GITHUB_EVENT_NAME="pull_request", GITHUB_REPOSITORY="o/r")
    monkeypatch.setattr(os, "environ", env)
    event = classify_changes.event_from_environment()
    assert event["pull_request"] == "7"
    assert event["before"] == "b" * 40


def test_aggregate_workflow_handoff(monkeypatch, tmp_path):
    expressions = _step_environment(
        "ci-gate.yml", "aggregate", "Fold the leg results into one verdict")
    assert expressions == {"AI_RESEARCHER_NEEDS_JSON": "${{ toJSON(needs) }}"}
    needs = {leg: {"result": "success"} for leg in aggregate_gate.EXPECTED_LEGS}
    env = {key: json.dumps(needs) for key in expressions}
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary")
    monkeypatch.setattr(os, "environ", env)
    assert aggregate_gate.main() == 0


@pytest.mark.parametrize("name", ["Rebuild the page", "Run the suite against the new capture"])
def test_refresh_stamp_handoff(monkeypatch, name):
    expressions = _step_environment("refresh.yml", "refresh", name)
    assert expressions == {"AI_RESEARCHER_AA_SOURCE_COMMIT": "${{ github.sha }}"}
    monkeypatch.setattr(os, "environ", {key: "a" * 40 for key in expressions})
    with tempfile.TemporaryDirectory(dir=build.ROOT) as tmp:
        output = pathlib.Path(tmp) / "page.html"
        monkeypatch.setattr(build, "OUT", output)
        with contextlib.redirect_stdout(io.StringIO()):
            build.main()
        assert f"Source commit <code>{'a' * 40}</code>" in output.read_text(encoding="utf-8")


def test_coverage_workflow_handoff(monkeypatch, tmp_path):
    expressions = _step_environment("tests.yml", "coverage", "Run tests")
    assert expressions == {
        "AI_RESEARCHER_JS_COVERAGE_OUT": "${{ runner.temp }}/js-coverage.json",
        "AI_RESEARCHER_COVERAGE_MEASURE_CHILDREN_RC": "${{ github.workspace }}/.github/coverage-children.rc",
    }
    env = {key: value.replace("${{ runner.temp }}", str(tmp_path))
           .replace("${{ github.workspace }}", str(ROOT))
           for key, value in expressions.items()}
    monkeypatch.setattr(os, "environ", env)
    test_browser.flush_page_coverage(SimpleNamespace(
        _open_pages=[], _coverage_entries=[{"url": "workflow"}]))
    assert json.loads((tmp_path / "js-coverage.json").read_text(encoding="utf-8")) == [{"url": "workflow"}]
    seen = []

    def run(args, **_kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)
    test_diff_coverage._run_cli([sys.executable, "child.py"])  # pylint: disable=protected-access
    assert seen == [[sys.executable, "-m", "coverage", "run", "--parallel-mode",
                     "--rcfile", str(ROOT / ".github" / "coverage-children.rc"), "child.py"]]
