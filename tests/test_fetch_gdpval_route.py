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
