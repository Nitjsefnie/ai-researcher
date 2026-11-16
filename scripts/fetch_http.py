"""Fetch HTTP bodies inside download.py's retry window."""
from __future__ import annotations

import http.client
import importlib
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ci"))


def retryable_transport_error(exc: BaseException) -> bool:
    """Transient: an HTTP 429 or 5xx, or a transport error."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (OSError, http.client.HTTPException))


def fetch_bytes(url: str, headers: dict[str, str], timeout: int, *,
                window: float | None = None,
                sleep: Callable[[float], None] | None = None) -> bytes:
    """Read the whole response in each attempt."""
    download = importlib.import_module("download")  # deferred: download imports fetch_http
    attempts, slept = 0, 0.0

    def attempt() -> bytes:
        nonlocal attempts
        attempts += 1
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def pause(seconds: float) -> None:
        # The window counts a wait as requested, even a recorded one.
        nonlocal slept
        began = time.monotonic()
        (sleep or time.sleep)(seconds)
        slept += seconds - (time.monotonic() - began)

    try:
        return download.retrying(attempt, url, sleep=pause, window=window,
                                 clock=lambda: time.monotonic() + slept)
    except download.RetriesExhausted as exhausted:
        error = exhausted.__cause__
    except (OSError, http.client.HTTPException) as exc:
        error = exc
    counted = f" after {attempts} attempts" if attempts > 1 else ""
    sys.exit(f"{url}: fetch failed{counted}: {error} -- nothing "
             "was captured; check connectivity or the site, then re-run")
