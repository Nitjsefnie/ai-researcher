"""Tests for the command that writes install_chromium.py's digest rows.

Offline: playwright is a fixture browsers.json (find_playwright_spec) and the
network a fake urlopen serving fixture zips by URL; the rest runs for real.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import io
import json
import re
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

import install_chromium  # noqa: E402  # pylint: disable=wrong-import-position
import update_chromium_digests  # noqa: E402  # pylint: disable=wrong-import-position

CDN = "https://cdn.playwright.dev/builds"
URLS = {
    "chromium": f"{CDN}/cft/158.0.8127.18/linux64/chrome-linux64.zip",
    "chromium-headless-shell":
        f"{CDN}/cft/158.0.8127.18/linux64/chrome-headless-shell-linux64.zip",
    "ffmpeg": f"{CDN}/ffmpeg/1014/ffmpeg-linux.zip",
}
EXECUTABLES = {spec.name: spec.executable for spec in install_chromium.PRODUCTS}
# The headless shell's pinned row is held; ffmpeg has none.
TABLE = {"chromium": {"1248": "a" * 64},
         "chromium-headless-shell": {"1254": "c" * 64}}


def zip_bytes(entries) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, mode in entries:
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            archive.writestr(info, b"payload")
    return buffer.getvalue()


@pytest.fixture(name="table")
def fixture_table(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "chromium-digests.json"
    path.write_text(json.dumps(TABLE, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(install_chromium, "DIGESTS_FILE", path)
    return path


@pytest.fixture(name="registry", autouse=True)
def fixture_registry(tmp_path, monkeypatch):
    package = tmp_path / "playwright" / "driver" / "package"
    package.mkdir(parents=True)
    (package / "browsers.json").write_text(json.dumps({"browsers": [
        {"name": "chromium", "revision": "1254",
         "browserVersion": "158.0.8127.18"},
        {"name": "chromium-headless-shell", "revision": "1254",
         "browserVersion": "158.0.8127.18"},
        {"name": "ffmpeg", "revision": "1014"},
    ]}), encoding="utf-8")
    spec = importlib.machinery.ModuleSpec("playwright", None)  # type: ignore[arg-type]
    spec.submodule_search_locations = [str(tmp_path / "playwright")]
    monkeypatch.setattr(install_chromium, "find_playwright_spec", lambda: spec)


@pytest.fixture(name="fetched")
def fixture_fetched() -> list:
    return []


@pytest.fixture(name="served")
def fixture_served(monkeypatch, fetched) -> dict:
    """URL -> body; others (the ffmpeg mirror) answer 404."""
    served = {url: zip_bytes([(EXECUTABLES[name], 0o100755)])
              for name, url in URLS.items()}

    def urlopen(url, timeout):
        assert timeout == install_chromium.DOWNLOAD_TIMEOUT
        fetched.append(url)
        if url not in served:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]
        return io.BytesIO(served[url])

    monkeypatch.setattr(install_chromium.download.urllib.request, "urlopen",
                        urlopen)
    return served


def test_writes_only_missing_rows_and_a_rerun_writes_nothing(table, served,
                                                             fetched, capsys):
    before = table.read_text(encoding="utf-8").splitlines()
    assert update_chromium_digests.main([]) == 0
    sha = {name: hashlib.sha256(served[url]).hexdigest()
           for name, url in URLS.items()}
    assert json.loads(table.read_text(encoding="utf-8")) == {
        "chromium": {"1254": sha["chromium"], "1248": "a" * 64},
        "chromium-headless-shell": {"1254": "c" * 64},
        "ffmpeg": {"1014": sha["ffmpeg"]},
    }
    # archive_urls' first host for each missing row; nothing for the held one.
    assert fetched == [URLS["chromium"], URLS["ffmpeg"]]
    # Every row already held keeps its bytes, trailing comma included.
    rows = [line for line in before if re.search("[0-9a-f]{64}", line)]
    written = table.read_text(encoding="utf-8")
    assert [line for line in written.splitlines() if line in rows] == rows
    # install_chromium.py reads back exactly the rows written.
    registry = install_chromium.load_registry(
        install_chromium.find_browsers_json())
    assert [product.digest for product in install_chromium.build_products(
        registry, install_chromium.load_digests(table))] == [
        sha["chromium"], "c" * 64, sha["ffmpeg"]]
    fetched.clear()
    assert update_chromium_digests.main([]) == 0
    assert (table.read_text(encoding="utf-8"), fetched) == (written, [])
    assert "nothing written" in capsys.readouterr().out


@pytest.mark.parametrize("body, refusal", [
    (b"not a zip", "not a readable zip"),
    (zip_bytes([("ffmpeg-mac", 0o100755)]), "lists no ffmpeg-linux"),
    (zip_bytes([("ffmpeg-linux", 0o100755), ("../evil", 0o100644)]),
     "escapes"),
])
def test_a_refused_archive_writes_no_row(table, served, capsys, body,
                                         refusal):
    # ffmpeg is fetched last, so the good chromium row before it is dropped too.
    before = table.read_bytes()
    served[URLS["ffmpeg"]] = body
    assert update_chromium_digests.main([]) == 2
    assert table.read_bytes() == before
    err = capsys.readouterr().err
    assert refusal in err and "No digest row was written." in err
