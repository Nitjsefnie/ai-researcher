"""Temp ownership and cleanup for browser launches (issue #310)."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import browser_temp


@pytest.mark.parametrize("previous", [None, "ambient-temp"])
@pytest.mark.parametrize("failure", [None, "start", "launch", "body", "close", "stop"])
def test_browser_lifetime_cleans_temp_and_restores_env(
        tmp_path, monkeypatch, previous, failure):
    """Lost env wiring or any missing finally strands a real temp file."""
    monkeypatch.setattr(browser_temp.tempfile, "tempdir", str(tmp_path))
    if previous is None:
        monkeypatch.delenv("TMPDIR", raising=False)
    else:
        monkeypatch.setenv("TMPDIR", previous)
    seen = {}
    events = []

    def fail_at(stage):
        if failure == stage:
            raise RuntimeError(stage)

    def close():
        assert seen["own"].exists()
        events.append("close")
        fail_at("close")

    browser = SimpleNamespace(close=close)

    def launch(**options):
        assert os.environ.get("TMPDIR") == previous
        own = seen["own"]
        assert options["env"] == {**os.environ, "TMPDIR": str(own)}
        assert options["headless"] is True
        (own / "chromium-residue").mkdir()
        fail_at("launch")
        return browser

    def stop():
        assert seen["own"].exists()
        events.append("stop")
        fail_at("stop")

    def start():
        own = Path(os.environ["TMPDIR"])
        assert own.parent == tmp_path
        assert own != tmp_path
        seen["own"] = own
        (own / "playwright-artifacts-test").mkdir()
        fail_at("start")
        return SimpleNamespace(
            chromium=SimpleNamespace(launch=launch), stop=stop)

    def factory():
        return SimpleNamespace(start=start)

    def run():
        with browser_temp.chromium_browser(factory, headless=True) as opened:
            assert opened is browser
            assert seen["own"].exists()
            assert os.environ.get("TMPDIR") == previous
            fail_at("body")

    if failure:
        with pytest.raises(RuntimeError, match=failure):
            run()
    else:
        run()
    assert os.environ.get("TMPDIR") == previous
    assert not list(tmp_path.iterdir())
    assert events == ({"start": [], "launch": ["stop"]}.get(
        failure, ["close", "stop"]))


def test_fcntl_absent_import_still_cleans_own_directory(tmp_path):
    """The Windows import path skips reclaim but keeps normal cleanup."""
    script = """
import sys
sys.modules['fcntl'] = None
from pathlib import Path
from scripts.browser_temp import chromium_temp
root = Path(sys.argv[1])
stale = root / 'aa-cr-stale'
stale.mkdir()
(stale / 'owner.lock').touch()
import tempfile
tempfile.tempdir = str(root)
with chromium_temp() as own:
    assert Path(own).exists()
assert not Path(own).exists()
assert stale.exists()
"""
    done = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX-only")
def test_live_owner_lock_is_held_and_parallel_launch_keeps_it(
        tmp_path, monkeypatch):
    import fcntl  # pylint: disable=import-outside-toplevel
    monkeypatch.setattr(browser_temp.tempfile, "tempdir", str(tmp_path))
    with browser_temp.chromium_temp() as live:
        marker = Path(live) / "browser-file"
        marker.touch()
        with (Path(live) / "owner.lock").open("r+", encoding="utf-8") as lock:
            with pytest.raises(OSError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with browser_temp.chromium_temp() as other:
            assert other != live
            assert marker.exists()
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(sys.platform == "win32", reason="flock is POSIX-only")
def test_dead_owner_is_reclaimed_on_next_launch(tmp_path, monkeypatch):
    script = """
import os
import tempfile
from pathlib import Path
from scripts.browser_temp import chromium_temp
tempfile.tempdir = os.environ['TMPDIR']
with chromium_temp() as own:
    (Path(own) / 'playwright-artifacts-killed').mkdir()
    os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script], check=True,
                   cwd=Path(__file__).resolve().parents[1],
                   env={**os.environ, "TMPDIR": str(tmp_path)})
    stale, = tmp_path.iterdir()
    assert (stale / "playwright-artifacts-killed").is_dir()
    monkeypatch.setattr(browser_temp.tempfile, "tempdir", str(tmp_path))
    with browser_temp.chromium_temp():
        assert not stale.exists()
    assert not list(tmp_path.iterdir())


def test_prefix_only_and_foreign_directories_are_untouched(tmp_path, monkeypatch):
    prefix_only = tmp_path / "aa-cr-foreign"
    prefix_only.mkdir()
    (prefix_only / "precious").touch()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "owner.lock").touch()
    monkeypatch.setattr(browser_temp.tempfile, "tempdir", str(tmp_path))
    with browser_temp.chromium_temp():
        assert (prefix_only / "precious").exists()
        assert (foreign / "owner.lock").exists()
    assert set(tmp_path.iterdir()) == {prefix_only, foreign}


@pytest.mark.parametrize("class_name", [
    "BrowserInteractionTests", "PerfBudgetTests", "ZeroScoreBrowserTests",
    "DisputeBrowserTests", "PresenceDisputeBrowserTests"])
@pytest.mark.parametrize("failure", ["start", "launch"])
def test_browser_class_setup_failure_cleans_driver_and_temp(
        tmp_path, monkeypatch, class_name, failure):
    pytest.importorskip("playwright.sync_api")
    import test_browser  # pylint: disable=import-outside-toplevel
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr(browser_temp.tempfile, "tempdir", str(tmp_path))
    saved = (test_browser.build.RAW, test_browser.build.AGENTS_RAW,
             test_browser.build.OUT)
    stopped = []

    def launch(**options):
        assert os.environ["TMPDIR"] == str(tmp_path)
        assert Path(options["env"]["TMPDIR"]).parent == tmp_path
        raise RuntimeError("launch failed")

    def start():
        own = Path(os.environ["TMPDIR"])
        assert own.parent == tmp_path
        (own / "driver-residue").mkdir()
        if failure == "start":
            raise RuntimeError("start failed")
        return SimpleNamespace(chromium=SimpleNamespace(launch=launch),
                               stop=lambda: stopped.append(True))

    monkeypatch.setattr(test_browser, "sync_playwright",
                        lambda: SimpleNamespace(start=start))
    cls = getattr(test_browser, class_name)
    try:
        with pytest.raises(RuntimeError, match=failure + " failed"):
            cls.setUpClass()
    finally:
        cls.doClassCleanups()
    assert (test_browser.build.RAW, test_browser.build.AGENTS_RAW,
            test_browser.build.OUT) == saved
    assert os.environ["TMPDIR"] == str(tmp_path)
    assert not list(tmp_path.iterdir())
    assert stopped == ([] if failure == "start" else [True])
