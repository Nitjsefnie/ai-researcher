"""Own Chromium and driver temp files for one browser lifetime (issue #310)."""
import contextlib
import os
from pathlib import Path
import shutil
import tempfile

try:
    import fcntl
except ImportError:  # Windows keeps per-launch cleanup, without reclaim.
    fcntl = None

# Keep room for Chromium's SingletonSocket under Unix socket path limits.
PREFIX = "aa-cr-"


def _reclaim(parent):
    """Delete only a recognized directory with an acquirable owner lock."""
    if fcntl is None:
        return
    for candidate in parent.glob(PREFIX + "*"):
        lock_path = candidate / "owner.lock"
        if candidate.is_symlink() or lock_path.is_symlink():
            continue
        try:
            lock = lock_path.open("r+", encoding="utf-8")
        except OSError:
            continue
        with lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                continue
            with contextlib.suppress(FileNotFoundError):
                shutil.rmtree(candidate)


@contextlib.contextmanager
def chromium_temp():
    """Remove a launch's temp files even when starting or closing fails."""
    with tempfile.TemporaryDirectory(prefix=PREFIX) as own:
        path = Path(own)
        pending = path / ("owner.pending" if fcntl is not None else "owner.lock")
        with pending.open("x", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_EX)
                # Publish only a held lock, so a parallel sweep cannot
                # reclaim a directory whose owner is still starting.
                pending.rename(path / "owner.lock")
            _reclaim(path.parent)
            yield own


@contextlib.contextmanager
def chromium_browser(playwright_factory, **launch_options):
    """Start the driver and Chromium in one owned temp directory."""
    with chromium_temp() as own:
        saved = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = own
        try:
            playwright = playwright_factory().start()
        finally:
            if saved is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = saved
        try:
            browser = playwright.chromium.launch(
                env={**os.environ, "TMPDIR": own}, **launch_options)
            try:
                yield browser
            finally:
                browser.close()
        finally:
            playwright.stop()
