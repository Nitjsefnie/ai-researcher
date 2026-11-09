"""The retry path for CI's tool and browser downloads (issue #395).

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
import sys
import threading
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
    """The defaults, time.sleep and time.monotonic, on one fake clock."""
    clock = FakeClock()
    monkeypatch.setattr(download.time, "sleep", clock.sleep)
    monkeypatch.setattr(download.time, "monotonic", clock)
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


def test_429_is_retried_with_backoff(serve, sleeps, tmp_path):
    server = serve(429)
    out = tmp_path / "out"
    digest, size = download.download_to(server.url, out, 5)
    assert out.read_bytes() == BODY
    assert (digest, size) == (hashlib.sha256(BODY).hexdigest(), len(BODY))
    assert server.hits == 2
    assert sleeps == [5]


def test_every_5xx_is_retried_on_a_doubling_schedule(serve, sleeps, tmp_path):
    server = serve(500, 502, 503, 504)
    download.download_to(server.url, tmp_path / "out", 5)
    assert server.hits == 5
    assert sleeps == [5, 10, 20, 40]


@pytest.mark.parametrize("fault", ["midstall", "midreset"])
def test_a_body_cut_by_a_timeout_or_reset_is_retried(serve, sleeps, tmp_path,
                                                     fault):
    server = serve(fault)
    download.download_to(server.url, tmp_path / "out", 0.2)
    assert (server.hits, sleeps) == (2, [5])
    assert (tmp_path / "out").read_bytes() == BODY


def test_a_dropped_body_is_retried_and_never_kept(serve, sleeps, tmp_path):
    server = serve("drop")
    out = tmp_path / "out"
    download.download_to(server.url, out, 5)
    assert server.hits == 2
    assert out.read_bytes() == BODY
    assert sleeps == [5]


def test_a_timeout_is_retried(serve, sleeps, tmp_path):
    server = serve("stall")
    download.download_to(server.url, tmp_path / "out", 0.2)
    assert server.hits == 2
    assert sleeps == [5]


def test_a_404_fails_at_once_naming_the_url(serve, sleeps, tmp_path):
    server = serve(404)
    with pytest.raises(download.DownloadError) as caught:
        download.download_to(server.url, tmp_path / "out", 5)
    assert server.hits == 1
    assert sleeps == []
    assert str(caught.value).startswith(f"{server.url}: download failed: ")
    assert not (tmp_path / "out").exists()


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
@pytest.mark.parametrize("cost, attempts, schedule", [
    (30, 6, [5, 10, 20, 40, 60]), (17.5, 7, [5, 10, 20, 40, 60, 60])])
def test_hung_attempts_spend_the_window(monkeypatch, tmp_path, cost, attempts,
                                        schedule):
    clock = FakeClock()

    def hung(url, timeout):
        clock.now += cost
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", hung)
    with pytest.raises(download.DownloadError,
                       match=f"after {attempts} attempts"):
        download.download_to("https://example.test/a", tmp_path / "out", 30,
                             sleep=clock.sleep, clock=clock)
    assert clock.sleeps == schedule


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


# Exits argv[2] for its first argv[3] runs, then 0, counting runs in argv[1].
FLAKY = ("import pathlib, sys; p = pathlib.Path(sys.argv[1]); "
         "n = int(p.read_text(encoding='utf-8')) if p.exists() else 0; "
         "p.write_text(str(n + 1), encoding='utf-8'); "
         "sys.exit(int(sys.argv[2]) if n < int(sys.argv[3]) else 0)")


@pytest.mark.parametrize("failures, status, attempts, schedule", [
    (0, 0, 1, []), (2, 0, 3, [5, 10]),
    (99, 3, 8, [5, 10, 20, 40, 60, 60, 60])])
def test_a_failing_command_is_rerun_and_its_last_status_returned(
        sleeps, tmp_path, failures, status, attempts, schedule):
    counter = tmp_path / "runs"
    assert download.main(["--run", sys.executable, "-c", FLAKY, str(counter),
                          "3", str(failures)]) == status
    assert int(counter.read_text(encoding="utf-8")) == attempts
    assert sleeps == schedule


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


@pytest.mark.parametrize("where, hits", [("missing directory", 0),
                                         ("full disk", 1)])
def test_a_destination_error_fails_at_once(serve, sleeps, tmp_path,
                                           monkeypatch, where, hits):
    server = serve()
    out = tmp_path / "missing" / "out"
    if where == "full disk":
        out = tmp_path / "out"
        monkeypatch.setattr(download, "open", lambda *args: FullDisk(),
                            raising=False)
    with pytest.raises(download.DownloadError) as caught:
        download.download_to(server.url, out, 5)
    assert str(caught.value).startswith(f"{server.url}: download failed: ")
    assert (server.hits, sleeps) == (hits, [])
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
