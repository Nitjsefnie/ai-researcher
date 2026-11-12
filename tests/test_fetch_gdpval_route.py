"""Exercise GDPval page and encrypted-data reads through cached routes."""
import email.message
import gzip
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import aa_aes_gcm  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_gdpval  # noqa: E402  # pylint: disable=wrong-import-position
from test_fetch_gdpval import payload  # noqa: E402  # pylint: disable=wrong-import-position


def _multiply(left, right):
    product = 0
    for bit in range(128):
        if left & (1 << (127 - bit)):
            product ^= right
        right = (right >> 1) ^ (0xe1000000000000000000000000000000 if right & 1 else 0)
    return product


def _seal(key, plaintext):
    """Fixture encryptor uses the standard's bitwise GHASH, independently of the decoder."""
    cipher = aa_aes_gcm.AES256(key)
    nonce = hashlib.sha256(key).digest()[:12]
    encrypted = bytearray()
    for offset in range(0, len(plaintext), 16):
        counter = nonce + (2 + offset // 16).to_bytes(4, "big")
        stream = cipher.encrypt(counter)
        encrypted.extend(a ^ b for a, b in zip(plaintext[offset:offset + 16], stream))
    subkey = int.from_bytes(cipher.encrypt(bytes(16)), "big")
    hashed = 0
    for offset in range(0, len(encrypted), 16):
        block = encrypted[offset:offset + 16].ljust(16, b"\0")
        hashed = _multiply(hashed ^ int.from_bytes(block, "big"), subkey)
    hashed = _multiply(hashed ^ (len(encrypted) * 8), subkey)
    tag = hashed ^ int.from_bytes(cipher.encrypt(nonce + bytes(3) + b"\1"), "big")
    return bytes(encrypted) + tag.to_bytes(16, "big")


def _page(manifest, title="GDPval-AA v2.1 Leaderboard"):
    flight = json.dumps({"manifest": manifest})
    return (f"<title>{title}</title><script>self.__next_f.push([1,"
            f"{json.dumps(flight)}])</script>")


def fixture_files(tmp_path, *, content=None, title="GDPval-AA v2.1 Leaderboard"):
    key = os.urandom(32)
    page = tmp_path / "evaluation.html"
    data = tmp_path / "data.bin"
    page.write_text(_page({"path": "/data/example.txt", "key": key.hex()}, title),
                    encoding="utf-8")
    if content is None:
        content = gzip.compress(json.dumps(payload()).encode("utf-8"))
    data.write_bytes(_seal(key, content))
    return page, data


def fetch(page, data):
    return fetch_gdpval.fetch(str(page), str(data), fetch_aa.fetch_html,
                              fetch_aa.flight_payload, fetch_aa.UA,
                              fetch_aa.FETCH_TIMEOUT_SECONDS, lambda _: None)


def test_runtime_key_round_trip_uses_title_manifest_and_cached_binary(tmp_path):
    page, data = fixture_files(tmp_path)
    result = fetch(page, data)
    assert result.costs == {"test-model": 4.5 / 220}
    assert result.records == payload()["models"]
    assert result.path == "/data/example.txt"


@pytest.mark.parametrize("title", ["GDPval-AA v2.2", "GDPval-AA v2.10", "Other title"])
def test_wrong_version_in_page_title_refuses(tmp_path, title):
    page, data = fixture_files(tmp_path, title=title)
    with pytest.raises(SystemExit, match="evaluations/gdpval-aa"):
        fetch(page, data)


@pytest.mark.parametrize("page_text", [
    "<title>GDPval-AA v2.1</title>",
    _page(None),
    _page({"path": "/data/example.txt"}),
    _page({"path": "/data/example.txt", "key": "wrong"}),
    _page({"path": "other-site", "key": "00" * 32}),
])
def test_missing_flight_or_invalid_manifest_refuses_with_page_url(tmp_path, page_text):
    page, data = fixture_files(tmp_path)
    page.write_text(page_text, encoding="utf-8")
    with pytest.raises(SystemExit, match="evaluations/gdpval-aa"):
        fetch(page, data)


def test_missing_cached_page_refuses_with_page_url(tmp_path):
    _, data = fixture_files(tmp_path)
    with pytest.raises(SystemExit, match="evaluations/gdpval-aa"):
        fetch(tmp_path / "missing.html", data)


def test_missing_data_file_refuses_with_data_path(tmp_path):
    page, _ = fixture_files(tmp_path)
    with pytest.raises(SystemExit, match="/data/example.txt"):
        fetch(page, tmp_path / "missing.bin")


def test_tag_mismatch_refuses_with_data_path(tmp_path):
    page, data = fixture_files(tmp_path)
    body = bytearray(data.read_bytes())
    body[-1] ^= 1
    data.write_bytes(body)
    with pytest.raises(SystemExit, match="/data/example.txt"):
        fetch(page, data)


@pytest.mark.parametrize("content", [b"not gzip", gzip.compress(b"not JSON"),
                                     gzip.compress(b'{"models":[]}')])
def test_bad_gzip_json_and_schema_refuse_with_data_path(tmp_path, content):
    page, data = fixture_files(tmp_path, content=content)
    with pytest.raises(SystemExit, match="/data/example.txt"):
        fetch(page, data)


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


@pytest.mark.parametrize("transient_url", [
    fetch_gdpval.GDPVAL_URL, "https://artificialanalysis.ai/data/example.txt"])
def test_live_transport_retries_transient_failures_with_the_existing_ua(
        tmp_path, monkeypatch, transient_url):
    page, data = fixture_files(tmp_path)
    responses = {fetch_gdpval.GDPVAL_URL: page.read_bytes(),
                 "https://artificialanalysis.ai/data/example.txt": data.read_bytes()}
    calls = []

    def urlopen(request, timeout):
        assert request.get_header("User-agent") == fetch_aa.UA
        assert timeout == fetch_aa.FETCH_TIMEOUT_SECONDS
        url = request.full_url
        calls.append(url)
        if url == transient_url and calls.count(url) == 1:
            raise urllib.error.HTTPError(url, 503, "unavailable", email.message.Message(), None)
        assert url in responses
        return _Response(responses[url])

    waits = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(fetch_aa, "_sleep", waits.append)
    result = fetch_gdpval.fetch(None, None, fetch_aa.fetch_html, fetch_aa.flight_payload,
                                fetch_aa.UA, fetch_aa.FETCH_TIMEOUT_SECONDS, waits.append)
    assert result.costs == {"test-model": 4.5 / 220}
    assert calls.count(transient_url) == 2
    assert waits == [fetch_aa.PAGE_BACKOFF_SECONDS]


@pytest.mark.parametrize("failed_url", [
    fetch_gdpval.GDPVAL_URL, "https://artificialanalysis.ai/data/example.txt"])
def test_forbidden_page_or_data_fetch_refuses_with_the_failed_url(tmp_path, monkeypatch, failed_url):
    page, data = fixture_files(tmp_path)
    responses = {fetch_gdpval.GDPVAL_URL: page.read_bytes(),
                 "https://artificialanalysis.ai/data/example.txt": data.read_bytes()}

    def urlopen(request, timeout):
        assert timeout == fetch_aa.FETCH_TIMEOUT_SECONDS
        url = request.full_url
        if url == failed_url:
            raise urllib.error.HTTPError(url, 403, "challenge", email.message.Message(), None)
        assert url in responses
        return _Response(responses[url])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(SystemExit) as caught:
        fetch_gdpval.fetch(None, None, fetch_aa.fetch_html, fetch_aa.flight_payload,
                           fetch_aa.UA, fetch_aa.FETCH_TIMEOUT_SECONDS, lambda _: None)
    assert failed_url in str(caught.value)


DATA_HOST = "https://artificialanalysis.ai"


def _pair(number, page_key, seal_key, content=None):
    """One attempt's page naming `page_key` and its data file sealed under `seal_key`."""
    path = f"/data/attempt{number}.txt"
    page = _page({"path": path, "key": page_key.hex()}).encode("utf-8")
    content = gzip.compress(json.dumps(payload()).encode("utf-8")) if content is None else content
    return path, page, _seal(seal_key, content)


def _serve(monkeypatch, responses):
    """Answer each URL's requests from its own sequence, one entry per request."""
    queues = {url: list(items) for url, items in responses.items()}
    calls = []

    def urlopen(request, timeout):
        assert timeout == fetch_aa.FETCH_TIMEOUT_SECONDS
        calls.append(request.full_url)
        item = queues[request.full_url].pop(0)
        if isinstance(item, Exception):
            raise item
        return _Response(item)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls


def _live_fetch(waits):
    return fetch_gdpval.fetch(None, None, fetch_aa.fetch_html, fetch_aa.flight_payload,
                              fetch_aa.UA, fetch_aa.FETCH_TIMEOUT_SECONDS, waits.append)


def _attempts(failures):
    """`failures` attempts whose page key fits no data seal, then one that authenticates."""
    pairs = [_pair(number, os.urandom(32), os.urandom(32)) for number in range(1, failures + 1)]
    good = os.urandom(32)
    return pairs + [_pair(failures + 1, good, good)]


def _responses(pairs):
    responses = {fetch_gdpval.GDPVAL_URL: [page for _, page, _ in pairs]}
    responses.update({DATA_HOST + path: [body] for path, _, body in pairs})
    return responses


def test_failed_authentication_re_reads_page_and_data_together(monkeypatch, capsys):
    # Three keys: re-reading only the data pairs K1 with K2's file, only the page
    # pairs K2 with K0's, and attempt 1's key fits neither second file.
    seal_first, key_first, key_second = os.urandom(32), os.urandom(32), os.urandom(32)
    pairs = [_pair(1, key_first, seal_first), _pair(2, key_second, key_second)]
    calls = _serve(monkeypatch, _responses(pairs))
    waits = []
    result = _live_fetch(waits)
    assert result.costs == {"test-model": 4.5 / 220}
    assert result.path == "/data/attempt2.txt"
    assert calls == [fetch_gdpval.GDPVAL_URL, DATA_HOST + "/data/attempt1.txt",
                     fetch_gdpval.GDPVAL_URL, DATA_HOST + "/data/attempt2.txt"]
    assert waits == [fetch_gdpval.AUTH_REREAD_SECONDS]
    assert (f"/data/attempt1.txt: authentication attempt 1 of {fetch_gdpval.AUTH_ATTEMPTS} failed "
            "(GCM tag mismatch); re-reading page and data in "
            f"{fetch_gdpval.AUTH_REREAD_SECONDS}s") in capsys.readouterr().err


def test_authentication_clearing_on_the_last_attempt_succeeds(monkeypatch):
    pairs = _attempts(fetch_gdpval.AUTH_ATTEMPTS - 1)
    calls = _serve(monkeypatch, _responses(pairs))
    waits = []
    result = _live_fetch(waits)
    assert result.costs == {"test-model": 4.5 / 220}
    assert calls.count(fetch_gdpval.GDPVAL_URL) == fetch_gdpval.AUTH_ATTEMPTS
    assert waits == [fetch_gdpval.AUTH_REREAD_SECONDS] * (fetch_gdpval.AUTH_ATTEMPTS - 1)


def test_authentication_failing_past_the_bound_refuses_naming_the_last_file(monkeypatch):
    pairs = _attempts(fetch_gdpval.AUTH_ATTEMPTS)[:-1]
    calls = _serve(monkeypatch, _responses(pairs))
    waits = []
    with pytest.raises(SystemExit) as caught:
        _live_fetch(waits)
    assert str(caught.value) == (f"{pairs[-1][0]}: data authentication or decryption failed: "
                                 "GCM tag mismatch")
    assert calls.count(fetch_gdpval.GDPVAL_URL) == fetch_gdpval.AUTH_ATTEMPTS
    assert [url for url in calls if url != fetch_gdpval.GDPVAL_URL] == [
        DATA_HOST + path for path, _, _ in pairs]
    assert waits == [fetch_gdpval.AUTH_REREAD_SECONDS] * (fetch_gdpval.AUTH_ATTEMPTS - 1)


@pytest.mark.parametrize("cached_page, cached_data", [(True, False), (False, True), (True, True)])
def test_failed_authentication_with_a_cached_input_refuses_without_a_re_read(
        tmp_path, monkeypatch, cached_page, cached_data):
    page, data = fixture_files(tmp_path)
    body = bytearray(data.read_bytes())
    body[-1] ^= 1
    data.write_bytes(body)
    responses = {}
    if not cached_page:
        responses[fetch_gdpval.GDPVAL_URL] = [page.read_bytes()]
    if not cached_data:
        responses[DATA_HOST + "/data/example.txt"] = [bytes(body)]
    calls = _serve(monkeypatch, responses)
    waits = []
    with pytest.raises(SystemExit, match="/data/example.txt: data authentication"):
        fetch_gdpval.fetch(str(page) if cached_page else None, str(data) if cached_data else None,
                           fetch_aa.fetch_html, fetch_aa.flight_payload, fetch_aa.UA,
                           fetch_aa.FETCH_TIMEOUT_SECONDS, waits.append)
    assert not waits
    assert len(calls) == (not cached_page) + (not cached_data)


@pytest.mark.parametrize("failure", ["gzip", "title", "forbidden"])
def test_non_authentication_failures_refuse_at_once_without_a_re_read(monkeypatch, failure):
    key = os.urandom(32)
    path, page, body = _pair(1, key, key, content=b"not gzip")
    if failure == "title":
        page = _page({"path": path, "key": key.hex()}, title="GDPval-AA v2.2").encode("utf-8")
    if failure == "forbidden":
        body = urllib.error.HTTPError(DATA_HOST + path, 403, "challenge",
                                      email.message.Message(), None)
    calls = _serve(monkeypatch, {fetch_gdpval.GDPVAL_URL: [page] * 2, DATA_HOST + path: [body] * 2})
    waits = []
    with pytest.raises(SystemExit):
        _live_fetch(waits)
    assert not waits
    assert calls.count(fetch_gdpval.GDPVAL_URL) == 1
    assert calls.count(DATA_HOST + path) == (0 if failure == "title" else 1)
