#!/usr/bin/env python3
"""Download a URL retrying transient failures, or re-run a command inside one
backoff window (issue #395): on any nonzero exit by default, narrowed by each
of --retry-on (statuses) and --retry-stderr (multiline regex) given, and
always after a --timeout kill (issue #426); --gh: for gh, last stdout only.

    python3 scripts/ci/download.py URL DESTINATION
    python3 scripts/ci/download.py --run [--gh] [--retry-on STATUS,...] [--retry-stderr REGEX]
        [--timeout SECONDS] [--window SECONDS] COMMAND...

With AI_RESEARCHER_DOWNLOAD_TOKEN set, a github.com release download goes
through the authenticated release-asset API instead.
"""
from __future__ import annotations

import hashlib
import http.client
import importlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
fetch_http = importlib.import_module("fetch_http")

BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 60
WINDOW_SECONDS = 300
CLI_TIMEOUT = 30
TIMED_OUT = 124
CHUNK = 1024 * 1024
PROGRESS_INTERVAL = 25 * 1024 * 1024
API = "https://api.github.com"
RELEASE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/([^/]+)")
# gh exits 1 on all: 429/5xx, transport, DNS, dropped body, HTML page.
GH_TRANSIENT = (r'HTTP (?:429|5\d\d)\)?$|^[A-Z][a-z]+ "[^"]*": |^error connecting to '
                r"|^unexpected EOF$|^invalid character '<' looking for beginning of value$")


T = TypeVar("T")


class DownloadError(Exception):
    pass


class RetriesExhausted(Exception):
    """Raised from the last error once the window allows no attempt."""


def _another_attempt(attempt: int, start: float, label: str, reason: object,
                     sleep: Callable[[float], None] | None,
                     clock: Callable[[], float] | None, window: float | None) -> bool:
    """The window decides only whether another attempt may start."""
    delay = min(BACKOFF_SECONDS * 2 ** (attempt - 1), MAX_BACKOFF_SECONDS)
    if (clock or time.monotonic)() - start + delay > (WINDOW_SECONDS if window is None else window):
        return False
    print(f"{label}: attempt {attempt} failed ({reason}); retrying in "
          f"{delay}s", file=sys.stderr, flush=True)
    (sleep or time.sleep)(delay)
    return True


def retrying(attempt: Callable[[], T], label: str, *,
             sleep: Callable[[float], None] | None = None,
             clock: Callable[[], float] | None = None, window: float | None = None) -> T:
    """Re-run attempt() on a transient transport error (issue #402)."""
    start = (clock or time.monotonic)()
    count = 0
    while True:
        count += 1
        try:
            return attempt()
        except (OSError, http.client.HTTPException) as exc:
            if not fetch_http.retryable_transport_error(exc):
                raise
            if not _another_attempt(count, start, label, exc, sleep, clock, window):
                spent = (clock or time.monotonic)() - start
                raise RetriesExhausted(
                    f"after {count} attempts in {spent:.0f}s") from exc


def download_to(url: str, destination: Path, timeout: float, *,
                label: str | None = None, token: str | None = None,
                sleep: Callable[[float], None] | None = None,
                clock: Callable[[], float] | None = None) -> tuple[str, int]:
    def attempt() -> tuple[str, int]:
        try:
            return _attempt(url, destination, timeout, label, token)
        except (DownloadError, OSError, http.client.HTTPException, ValueError) as exc:
            # No partial body survives to prefix a retry or to be verified.
            destination.unlink(missing_ok=True)
            # GitHub: an exhausted rate limit is not to be retried before its reset.
            if isinstance(exc, urllib.error.HTTPError) \
                    and (getattr(exc, "headers", None) or {}).get("x-ratelimit-remaining") == "0":
                raise DownloadError(f"{url}: download failed: {exc}") from exc
            raise

    try:
        return retrying(attempt, url, sleep=sleep, clock=clock)
    except RetriesExhausted as exc:
        raise DownloadError(
            f"{url}: download failed {exc}: {exc.__cause__}") from exc.__cause__
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise DownloadError(f"{url}: download failed: {exc}") from exc


def _attempt(url: str, destination: Path, timeout: float, label: str | None,
             token: str | None) -> tuple[str, int]:
    out = _local(url, open, destination, "wb")
    with out, urllib.request.urlopen(_source(url, timeout, token),
                                     timeout=timeout) as response:
        digest = hashlib.sha256()
        size = 0
        next_progress = PROGRESS_INTERVAL
        while chunk := response.read(CHUNK):
            digest.update(chunk)
            _local(url, out.write, chunk)
            size += len(chunk)
            if label and size >= next_progress:
                print(f"{label}: {size // (1024 * 1024)} MiB", flush=True)
                next_progress += PROGRESS_INTERVAL
        # http.client's read(amt) ends a dropped body with b"", never an error.
        if missing := getattr(response, "length", None):
            raise http.client.IncompleteRead(b"", missing)
        return digest.hexdigest(), size


def _source(url: str, timeout: float, token: str | None):
    if not token or not (match := RELEASE.fullmatch(url)):
        return url
    owner, repo, tag, name = match.groups()
    with urllib.request.urlopen(_api(f"{API}/repos/{owner}/{repo}/releases/tags/{tag}",
                                     "application/vnd.github+json", token),
                                timeout=timeout) as response:
        assets = json.load(response).get("assets", [])
    ids = [a["id"] for a in assets if a.get("name") == urllib.parse.unquote(name)]
    if not ids:
        raise DownloadError(f"{url}: download failed: release {tag} has no asset {name}")
    return _api(f"{API}/repos/{owner}/{repo}/releases/assets/{ids[0]}",
                "application/octet-stream", token)


def _api(url: str, accept: str, token: str) -> urllib.request.Request:
    request = urllib.request.Request(url, headers={"Accept": accept})
    # Unredirected: the 302 to the signed asset host carries no token.
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    return request


def _local(url: str, operation: Callable, *args):
    """A destination error is not the network's, so it fails at once."""
    try:
        return operation(*args)
    except OSError as exc:
        raise DownloadError(f"{url}: download failed: {exc}") from exc


def run_retrying(command: list[str] | Callable[[], list[str]], *,
                 retry_on: frozenset[int] | None = None,
                 retry_stderr: re.Pattern[str] | None = None,
                 timeout: float | None = None, last_stdout: bool = False,
                 window: float | None = None, sleep: Callable[[float], None] | None = None,
                 clock: Callable[[], float] | None = None) -> int:
    start = (clock or time.monotonic)()
    attempt = 0
    while True:
        attempt += 1
        argv = command() if callable(command) else command
        label = " ".join(argv)
        timed_out = False
        try:
            # Kills only the direct child: enough for one binary, not a tree.
            done = subprocess.run(argv, check=False, timeout=timeout, stderr=(
                subprocess.PIPE if retry_stderr else None), stdout=(
                    subprocess.PIPE if last_stdout else None))
            status, stdout, stderr = done.returncode, done.stdout, done.stderr or b""
        except subprocess.TimeoutExpired as expired:
            status, stdout, stderr, timed_out = TIMED_OUT, expired.stdout, expired.stderr or b"", True
        if retry_stderr:
            sys.stderr.flush()
            sys.stderr.buffer.write(stderr)
            sys.stderr.buffer.flush()
        matched = retry_stderr is None or bool(retry_stderr.search(
            re.sub(r"\r\n?", "\n", stderr.decode("utf-8", "replace"))))
        reason = f"timed out after {timeout:g}s" if timed_out else f"exit {status}"
        retryable = timed_out or (
            status != 0 and (retry_on is None or status in retry_on) and matched)
        if not retryable or not _another_attempt(attempt, start, label, reason,
                                                 sleep, clock, window):
            if timed_out:
                print(f"{label}: attempt {attempt} {reason}; no attempt left in "
                      "the window", file=sys.stderr, flush=True)
            if last_stdout:
                sys.stdout.buffer.write(stdout or b"")
                sys.stdout.buffer.flush()
            return status


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--run"]:
        args, options = args[1:], {}
        while args[:1] in (["--gh"], ["--retry-on"], ["--retry-stderr"], ["--timeout"], ["--window"]):
            if args[0] == "--gh":
                options.update({"--gh": "", "--retry-on": "1", "--retry-stderr": GH_TRANSIENT})
                args = args[1:]
            else:
                options[args[0]], args = args[1], args[2:]
        statuses, seconds = options.get("--retry-on"), options.get("--timeout")
        pattern, window = options.get("--retry-stderr"), options.get("--window")
        return run_retrying(
            args, timeout=None if seconds is None else float(seconds), last_stdout="--gh" in options,
            window=None if window is None else float(window),
            retry_stderr=None if pattern is None else re.compile(pattern, re.MULTILINE),
            retry_on=None if statuses is None
            else frozenset(int(status) for status in statuses.split(",")))
    url, destination = args
    try:
        download_to(url, Path(destination), CLI_TIMEOUT,
                    token=os.environ.get("AI_RESEARCHER_DOWNLOAD_TOKEN"))
    except DownloadError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
