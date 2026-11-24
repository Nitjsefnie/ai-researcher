"""The retry path for CI's tool and browser downloads.

Faults are injected at the network boundary only: a local HTTP server that
answers a scripted status, drops the connection mid-body or stalls, or a
urlopen double driving a fake clock for the window arithmetic. Every case
counts the attempts the fault consumed, and no backoff sleep is real.
"""
from __future__ import annotations

import errno
import hashlib
import http.server
import io
import json
import socket
import struct
import subprocess
import sys
import threading
import types
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

import download  # noqa: E402  # pylint: disable=wrong-import-position

BODY = b"verified archive bytes " * 4096


class FakeClock:
    """A clock that only the double and the injected sleep advance."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture(name="sleeps")
def fixture_sleeps(monkeypatch):
    """download.py's time.sleep and time.monotonic (not subprocess's) on one fake clock."""
    clock = FakeClock()
    monkeypatch.setattr(download, "time", types.SimpleNamespace(sleep=clock.sleep, monotonic=clock))
    return clock.sleeps


class Server(http.server.ThreadingHTTPServer):
    """Answers each request with the next scripted fault, then BODY."""

    daemon_threads = True

    def __init__(self, faults):
        super().__init__(("127.0.0.1", 0), Handler)
        self.faults = list(faults)
        self.hits = 0
        self.auth = []
        self.release = threading.Event()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/tool.tar.gz"


class Handler(http.server.BaseHTTPRequestHandler):
    server: Server

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass

    def do_GET(self):  # pylint: disable=invalid-name
        self.server.hits += 1
        self.server.auth.append(self.headers.get("Authorization"))
        fault = self.server.faults.pop(0) if self.server.faults else 200
        if fault == "stall":
            self.server.release.wait(10)
            return
        if isinstance(fault, int) and fault != 200:
            self.send_error(fault)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY[:1000] if fault != 200 else BODY)
        if fault == "midstall":
            self.server.release.wait(10)
        elif fault == "midreset":
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                       struct.pack("ii", 1, 0))
            self.connection.close()


@pytest.fixture(name="serve")
def fixture_serve():
    servers = []

    def start(*faults):
        server = Server(faults)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.release.set()
        server.shutdown()
        server.server_close()


# A 429, every 5xx, a dropped body or a timeout (before or mid-body) is retried.
@pytest.mark.parametrize("faults, timeout, schedule", [
    ([429], 5, [5]), ([500, 502, 503, 504], 5, [5, 10, 20, 40]), (["drop"], 5, [5]),
    (["stall"], 0.2, [5]), (["midstall"], 0.2, [5]), (["midreset"], 0.2, [5])])
def test_a_transient_fault_is_retried_with_backoff(serve, sleeps, tmp_path,
                                                   faults, timeout, schedule):
    server = serve(*faults)
    out = tmp_path / "out"
    digest, size = download.download_to(server.url, out, timeout)
    assert (server.hits, sleeps) == (len(faults) + 1, schedule)
    assert out.read_bytes() == BODY
    assert (digest, size) == (hashlib.sha256(BODY).hexdigest(), len(BODY))


def test_exhaustion_names_the_url_and_leaves_no_partial_file(serve, sleeps,
                                                             tmp_path):
    server = serve(*["drop"] * 9)
    out = tmp_path / "out"
    with pytest.raises(download.DownloadError) as caught:
        download.download_to(server.url, out, 5)
    assert server.hits == 8
    assert sleeps == [5, 10, 20, 40, 60, 60, 60]
    assert str(caught.value).startswith(
        f"{server.url}: download failed after 8 attempts in 255s: ")
    assert not out.exists()


# 17.5 s attempts put the seventh start exactly on the window's edge: 6 * 17.5
# + 5 + 10 + 20 + 40 + 60 + 60 = 300, which still starts; 30 s ones stop at six.
# A --run attempt --timeout kills spends it alike; at zizmor's 60 s bound, four fit.
@pytest.mark.parametrize("cost, attempts, schedule", [
    (30, 6, [5, 10, 20, 40, 60]), (17.5, 7, [5, 10, 20, 40, 60, 60]), (60, 4, [5, 10, 20])])
def test_hung_attempts_spend_the_window(monkeypatch, tmp_path, capsys, cost, attempts, schedule):
    clock = FakeClock()

    def hung(*args, **kwargs):
        clock.now += cost
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", hung)
    monkeypatch.setattr(download.subprocess, "run", hung)
    error = TimeoutError("timed out")
    with pytest.raises(download.DownloadError,
                       match=f"after {attempts} attempts"):
        download.download_to("https://example.test/a", tmp_path / "out", 30,
                             sleep=clock.sleep, clock=clock)
    downloaded, clock.sleeps = clock.sleeps, []
    error = subprocess.TimeoutExpired("zizmor", cost)
    assert download.run_retrying(["zizmor"], retry_on=frozenset({1}), timeout=cost,
                                 sleep=clock.sleep, clock=clock) == 124
    assert (downloaded, clock.sleeps) == (schedule, schedule)
    assert capsys.readouterr().err.endswith(
        f"zizmor: attempt {attempts} timed out after {cost:g}s; no attempt left in the window\n")


class TrickleResponse(io.BytesIO):
    """One chunk per read, each costing `step` seconds; `owed` bytes never come."""

    def __init__(self, clock, step, chunks, owed):
        super().__init__()
        self.clock, self.step, self.chunks = clock, step, list(chunks)
        self.length = owed

    def read(self, size=-1, /):
        self.clock.now += self.step if self.chunks else 0
        return self.chunks.pop(0) if self.chunks else b""


# Three chunks: a 110 s step ends past the 300 s window, a 90 s step inside it.
@pytest.mark.parametrize("step, owed, attempts, schedule", [
    (110, 0, 1, []),   # still receiving past the window: never cut
    (110, 7, 1, []),   # dropped past the window: no new attempt starts
    (90, 7, 2, [5]),   # dropped inside it: one more attempt starts
])
def test_the_window_gates_only_the_next_attempt(monkeypatch, tmp_path, step,
                                                owed, attempts, schedule):
    clock = FakeClock()
    calls = []

    def trickle(url, timeout):
        calls.append(url)
        return TrickleResponse(clock, step, [b"a", b"b", b"c"], owed)

    monkeypatch.setattr(urllib.request, "urlopen", trickle)
    out = tmp_path / "out"
    out.write_bytes(b"a stale file is replaced, never appended to")
    if not owed:
        download.download_to("https://example.test/a", out, 30,
                             sleep=clock.sleep, clock=clock)
        assert out.read_bytes() == b"abc"
    else:
        with pytest.raises(download.DownloadError,
                           match=f"after {attempts} attempts"):
            download.download_to("https://example.test/a", out, 30,
                                 sleep=clock.sleep, clock=clock)
        assert not out.exists()
    assert len(calls) == attempts
    assert clock.sleeps == schedule


def test_progress_prints_one_line_per_interval(serve, sleeps, tmp_path,
                                               monkeypatch, capsys):
    monkeypatch.setattr(download, "CHUNK", 10000)
    monkeypatch.setattr(download, "PROGRESS_INTERVAL", 40000)
    download.download_to(serve().url, tmp_path / "out", 5, label="chromium")
    assert capsys.readouterr().out == "chromium: 0 MiB\n" * 2


# For its first argv[3] runs, writes "flaky argv[2]" (CRLF-ended), "lone argv[2]" (lone CR) and a
# non-UTF-8 line to stderr and exits argv[2] (hangs, for "hang"); then exits 0. Runs are counted in argv[1].
FLAKY = ("import pathlib, sys, time; p = pathlib.Path(sys.argv[1]); "
         "n = int(p.read_text(encoding='utf-8')) if p.exists() else 0; "
         "p.write_text(str(n + 1), encoding='utf-8'); fail = n < int(sys.argv[3]); "
         "fail and sys.stderr.buffer.write(b'flaky %b\\r\\nlone %b\\r\\xff\\r\\n' % ((sys.argv[2].encode(),) * 2)); sys.stderr.flush(); "
         "fail and sys.argv[2] == 'hang' and time.sleep(60); "
         "sys.exit(int(sys.argv[2]) if fail else 0)")


# Any nonzero status reruns, or only those --retry-on names and, with --retry-stderr, whose
# stderr matches (logged once per failed run either way); a --timeout kill always reruns.
@pytest.mark.parametrize("retry_on, code, failures, status, attempts, schedule", [
    ([], 3, 0, 0, 1, []), ([], 3, 2, 0, 3, [5, 10]), ([], 3, 99, 3, 8, [5, 10, 20, 40, 60, 60, 60]),
    (["--retry-on", "1"], 1, 2, 0, 3, [5, 10]), (["--retry-on", "1"], 13, 99, 13, 1, []),
    (["--retry-on", "13,1"], 1, 99, 1, 8, [5, 10, 20, 40, 60, 60, 60]), (["--retry-stderr", "^lone 1$"], 1, 2, 0, 3, [5, 10]),
    (["--retry-stderr", "^flaky 1$"], 1, 2, 0, 3, [5, 10]), (["--retry-stderr", "^flaky 2$"], 1, 9, 1, 1, []),
    (["--retry-stderr", "aky 1"], 1, 2, 0, 3, [5, 10]), (["--retry-on", "2", "--retry-stderr", "flaky"], 1, 9, 1, 1, []),
    (["--timeout", "2", "--retry-on", "13", "--retry-stderr", "x"], "hang", 1, 0, 2, [5]), (["--window", "30"], 3, 99, 3, 3, [5, 10])])
def test_a_failing_command_is_rerun_and_its_last_status_returned(
        sleeps, tmp_path, capfdbinary, retry_on, code, failures, status, attempts, schedule):
    counter = tmp_path / "runs"
    assert download.main(["--run", *retry_on, sys.executable, "-c", FLAKY, str(counter), str(code), str(failures)]) == status
    assert int(counter.read_text(encoding="utf-8")) == attempts
    assert sleeps == schedule
    err = capfdbinary.readouterr().err  # each failed run's bytes, unaltered; the give-up line only after a timeout
    assert (err.count(b"flaky %s\r\nlone %s\r\xff\r\n" % ((str(code).encode(),) * 2)), b"no attempt left" in err) == (min(failures, attempts), False)


@pytest.mark.parametrize("attempt, delay", [(1, 5), (4, 40), (5, 60)])
def test_a_pause_waits_one_backoff_step(sleeps, capsys, attempt, delay):
    assert download.main(["--pause", str(attempt), "artifact x"]) == 0
    assert (sleeps, capsys.readouterr().err) == ([delay], f"artifact x: attempt {attempt} failed (its error is above); retrying in {delay}s\n")


# Its first run prints "body 0" and argv[3] on stderr and exits argv[2]; later runs print "body N", exit 0.
GH = ("import pathlib, sys; p = pathlib.Path(sys.argv[1]); n = len(p.read_bytes()) if p.exists() else 0; "
      "p.write_bytes(b'x' * (n + 1)); sys.stdout.buffer.write(b'body %d\\n' % n); "
      "n or sys.stderr.write(sys.argv[3] + '\\n'); sys.exit(0 if n else int(sys.argv[2]))")


# --gh reruns gh's exit 1 when a stderr line is an HTTP 429 or 5xx, Go's transport error, a DNS failure, a
# dropped body or an HTML error page (gh 2.98.0, measured), and keeps only the last attempt's stdout.
@pytest.mark.parametrize("code, line, rerun", [
    (1, "gh: Server Error (HTTP 502)", True), (1, "gh: HTTP 503", True), (1, "gh: rate limit (HTTP 429)", True),
    (1, 'Get "https://api.github.com/x": dial tcp 127.0.0.1:9: connect: connection refused', True),
    (1, "error connecting to api.github.com", True), (1, "unexpected EOF", True),
    (1, "invalid character '<' looking for beginning of value", True), (1, "gh: Not Found (HTTP 404)", False),
    (1, "gh: Bad credentials (HTTP 401)", False), (1, "gh: Forbidden (HTTP 403)", False),
    (1, "gh: Validation Failed (HTTP 422)", False), (1, "gh: see (HTTP 502) above", False), (4, "gh: HTTP 502", False)])
def test_gh_reruns_only_a_transient_failure_and_keeps_the_last_stdout(sleeps, tmp_path, capfdbinary, code, line, rerun):
    counter = tmp_path / "runs"
    status = download.main(["--run", "--gh", sys.executable, "-c", GH, str(counter), str(code), line])
    assert (status, counter.read_bytes(), capfdbinary.readouterr().out, sleeps) == (
        (0, b"xx", b"body 1\n", [5]) if rerun else (code, b"x", b"body 0\n", []))


def test_the_cli_retries_and_exits_nonzero_on_exhaustion(serve, sleeps,
                                                         tmp_path, capsys):
    good = serve(503)
    assert download.main([good.url, str(tmp_path / "good")]) == 0
    assert (tmp_path / "good").read_bytes() == BODY
    bad = serve(*[504] * 9)
    assert download.main([bad.url, str(tmp_path / "bad")]) == 1
    assert (good.hits, bad.hits) == (2, 8)
    assert f"{bad.url}: download failed after 8 attempts" in capsys.readouterr().err


TOKEN = "token-value-for-tests"
RELEASE_URL = "https://github.com/o/r/releases/download/v1/tool.tar.gz"


# No token, an empty one, or a URL that is no github.com release download:
# the plain URL, exactly as given, at the CLI's 30 s socket timeout.
@pytest.mark.parametrize("token, url", [
    (None, RELEASE_URL), ("", RELEASE_URL), (TOKEN, "https://cdn.test/a.zip")])
def test_the_cli_fetches_the_plain_url_at_30_seconds(monkeypatch, tmp_path,
                                                     token, url):
    monkeypatch.delenv("AI_RESEARCHER_DOWNLOAD_TOKEN", raising=False)
    if token is not None:
        monkeypatch.setenv("AI_RESEARCHER_DOWNLOAD_TOKEN", token)
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout:
                        calls.append((url, timeout)) or io.BytesIO(b"tool"))
    assert download.main([url, str(tmp_path / "out")]) == 0
    assert calls == [(url, 30)]


class FullDisk(io.BytesIO):
    def write(self, data, /):
        raise OSError(errno.ENOSPC, "No space left on device")


@pytest.mark.parametrize("where, hits", [("404", 1), ("missing directory", 0),
                                         ("full disk", 1)])
def test_a_404_or_a_destination_error_fails_at_once(serve, sleeps, tmp_path,
                                                    monkeypatch, where, hits):
    server = serve(404) if where == "404" else serve()
    out = tmp_path / ("out" if where == "404" else "missing/out")
    if where == "full disk":
        out = tmp_path / "out"
        monkeypatch.setattr(download, "open", lambda *args: FullDisk(),
                            raising=False)
    with pytest.raises(download.DownloadError) as caught:
        download.download_to(server.url, out, 5)
    assert str(caught.value).startswith(f"{server.url}: download failed: ")
    assert (server.hits, sleeps) == (hits, [])
    assert not out.exists()


class FailsAfterFirstWrite:
    """The real destination file, whose second write raises; `sizes` records how
    many bytes sat on disk when it did."""

    def __init__(self, path, sizes):
        self.path, self.sizes, self.writes = path, sizes, 0
        self.file = open(path, "wb")  # pylint: disable=consider-using-with

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.file.close()

    def write(self, data, /):
        self.writes += 1
        if self.writes > 1:
            self.file.flush()
            self.sizes.append(self.path.stat().st_size)
            raise OSError(errno.ENOSPC, "No space left on device")
        return self.file.write(data)


def test_a_write_error_after_the_first_chunk_deletes_the_partial_file(
        serve, sleeps, tmp_path, monkeypatch):
    server = serve()
    out = tmp_path / "out"
    sizes = []
    monkeypatch.setattr(download, "CHUNK", 1000)
    monkeypatch.setattr(download, "open",
                        lambda path, mode: FailsAfterFirstWrite(path, sizes),
                        raising=False)
    with pytest.raises(download.DownloadError) as caught:
        download.download_to(server.url, out, 5)
    assert sizes == [1000]
    assert str(caught.value).startswith(f"{server.url}: download failed: ")
    assert (server.hits, sleeps) == (1, [])
    assert not out.exists()


class Api(http.server.ThreadingHTTPServer):
    """api.github.com: each path answers its scripted (status, headers, body)
    list in order, repeating the last; an unknown path is a 404."""

    daemon_threads = True

    def __init__(self, routes):
        super().__init__(("127.0.0.1", 0), ApiHandler)
        self.routes, self.seen = routes, []


class ApiHandler(http.server.BaseHTTPRequestHandler):
    server: Api

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass

    def do_GET(self):  # pylint: disable=invalid-name
        self.server.seen.append((self.path, self.headers.get("Authorization"),
                                 self.headers.get("Accept")))
        answers = self.server.routes.get(self.path, [(404, {}, b"")])
        status, headers, body = answers.pop(0) if len(answers) > 1 else answers[0]
        self.send_response(status)
        for name, value in {**headers, "Content-Length": str(len(body))}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(name="api")
def fixture_api(monkeypatch):
    servers = []

    def start(routes):
        server = Api(routes)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        monkeypatch.setattr(download, "API",
                            f"http://127.0.0.1:{server.server_address[1]}")
        return server

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


TAGS, ASSET = "/repos/o/r/releases/tags/v1", "/repos/o/r/releases/assets/7"
RELEASE = json.dumps({"assets": [{"name": "other", "id": 6},
                                 {"name": "tool.tar.gz", "id": 7}]}).encode()
JSON, OCTETS = "application/vnd.github+json", "application/octet-stream"


def test_the_token_path_retries_both_requests_and_keeps_the_token_on_the_api(
        api, serve, sleeps, tmp_path, capsys):
    signed = serve()
    server = api({TAGS: [(503, {}, b""), (200, {}, RELEASE)],
                  ASSET: [(504, {}, b""), (302, {"Location": signed.url}, b"")]})
    out = tmp_path / "out"
    download.download_to(RELEASE_URL, out, 5, token=TOKEN)
    assert out.read_bytes() == BODY
    bearer = f"Bearer {TOKEN}"
    assert server.seen == [(TAGS, bearer, JSON), (TAGS, bearer, JSON),
                           (ASSET, bearer, OCTETS), (TAGS, bearer, JSON),
                           (ASSET, bearer, OCTETS)]
    assert (signed.hits, signed.auth, sleeps) == (1, [None], [5, 10])
    assert TOKEN not in "".join(capsys.readouterr())


@pytest.mark.parametrize("routes, reason", [
    ({}, "HTTP Error 404"),
    ({TAGS: [(200, {}, b'{"assets": [{"name": "other", "id": 6}]}')]},
     "release v1 has no asset tool.tar.gz"),
    ({TAGS: [(403, {"X-RateLimit-Remaining": "0"}, b"")]}, "HTTP Error 403"),
    ({TAGS: [(429, {"X-RateLimit-Remaining": "0"}, b"")]}, "HTTP Error 429"),
])
def test_a_missing_release_or_an_exhausted_rate_limit_fails_at_once(
        api, sleeps, tmp_path, capsys, routes, reason):
    server = api(routes)
    with pytest.raises(download.DownloadError) as caught:
        download.download_to(RELEASE_URL, tmp_path / "out", 5, token=TOKEN)
    assert str(caught.value).startswith(f"{RELEASE_URL}: download failed: {reason}")
    assert (len(server.seen), sleeps) == (1, [])
    assert TOKEN not in str(caught.value) + "".join(capsys.readouterr())
