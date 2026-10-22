"""Own browser temp files (issue #310)."""
import contextlib
import os
from pathlib import Path
import shutil
import tempfile

try:
    import fcntl
except ImportError:  # Windows skips reclaim.
    fcntl = None

# Chromium's Unix socket path has a length limit.
PREFIX = "aa-cr-"


@contextlib.contextmanager
def _directory_lock(path, nonblocking=False):
    """Exclude reclaim until the pending file is locked."""
    if fcntl is None:
        yield
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield
    finally:
        os.close(descriptor)


def _reclaim(parent):
    if fcntl is None:
        return
    for candidate in parent.glob(PREFIX + "*"):
        if candidate.is_symlink():
            continue
        with contextlib.ExitStack() as stack:
            try:
                stack.enter_context(_directory_lock(candidate, nonblocking=True))
                published, pending = candidate / "owner.lock", candidate / "owner.pending"
                if published.is_symlink() or pending.is_symlink():
                    continue
                try:
                    lock = published.open("r+", encoding="utf-8")
                except FileNotFoundError:
                    lock = pending.open("r+", encoding="utf-8")
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
    """The owner flock survives rename and covers the browser lifetime."""
    with contextlib.ExitStack() as lifetime:
        own = lifetime.enter_context(tempfile.TemporaryDirectory(prefix=PREFIX))
        path = Path(own)
        with _directory_lock(path):
            pending = path / ("owner.pending" if fcntl is not None else "owner.lock")
            lock = lifetime.enter_context(pending.open("x", encoding="utf-8"))
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_EX)
                pending.rename(path / "owner.lock")
        _reclaim(path.parent)
        yield own


@contextlib.contextmanager
def chromium_browser(playwright_factory, **launch_options):
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
