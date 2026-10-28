"""Fetch HTTP response bodies with bounded retries for transport failures."""
from __future__ import annotations

import http.client
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

ATTEMPTS = 3
BACKOFF_SECONDS = 5


def retryable_transport_error(exc: BaseException) -> bool:
    """Distinguish transient HTTP answers and transport errors from other 4xx."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (OSError, http.client.HTTPException))


def fetch_bytes(url: str, headers: dict[str, str], timeout: int,
                *, sleep: Callable[[float], None] | None = None) -> bytes:
    """Read the entire response inside each bounded attempt."""
    if sleep is None:
        sleep = time.sleep
    for attempt in range(1, ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            if not retryable_transport_error(exc) or attempt == ATTEMPTS:
                exhausted = f" after {attempt} attempts" if attempt > 1 else ""
                sys.exit(f"{url}: fetch failed{exhausted}: {exc} -- nothing "
                         "was captured; check connectivity or the site, "
                         "then re-run")
            delay = attempt * BACKOFF_SECONDS
            print(f"{url}: attempt {attempt} of {ATTEMPTS} failed "
                  f"({exc}); retrying in {delay}s", file=sys.stderr)
            sleep(delay)
    raise AssertionError("fetch_bytes ran out of attempts without a verdict")
