#!/usr/bin/env python3
"""Digest-verify and pre-seed Playwright's Chromium before it can execute.

The write-capable CI jobs (refresh.yml, tests.yml's coverage job) run the
browser suite, and the browser they execute is whatever ``python3 -m
playwright install`` fetched: playwright's downloader checks only that a
marker file exists, then downloads over TLS and extracts -- no digest is
published in browsers.json (verified against playwright 1.63.0, whose entries
carry only name/revision/browserVersion/installByDefault/title), and nothing
in the install path hashes a byte. A compromised CDN, a redirect target or
any middlebox can hand the job an arbitrary binary, and the job holds a
write token.

This script closes that hole without forking playwright's installer. It
resolves the pinned revision and archive URL from the INSTALLED playwright
package, checks the archive against a digest committed in this file, and
pre-seeds the browsers directory so the subsequent ``playwright install
--with-deps chromium`` finds every product present (marker file set) and
downloads nothing. Afterwards it asserts that nothing was re-downloaded
anyway -- a replaced browser directory or an unexpected new browser directory
fails the job.

Failure is loud and there is no fallback: a digest mismatch names expected
and actual and exits nonzero, and an unknown revision (a playwright bump
without its digest yet) fails with the exact update recipe. See DIGESTS for
the update procedure.

linux x64 only, deliberately: both consumers are ubuntu-latest runners, and
the layout below (directory names, zip roots, executable paths) was observed
on that platform against playwright 1.63.0 / chromium revision 1243. Other
platforms would need their own archives and executables verified; do not
extend it without observing them the same way.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

# cdn.playwright.dev is the registry's primary host. The CFT (Chrome for
# Testing) paths 307-redirect to Google's chrome-for-testing-public bucket;
# the digest pins the bytes, so the redirect target is verified like any
# other source. ffmpeg additionally lists the Microsoft prss host as its
# fallback mirror in playwright's own registry; mirrors are tried in order
# on transport failure, and EVERY mirror's bytes are digest-checked.
CDN = "https://cdn.playwright.dev"
PRSS = "https://playwright.download.prss.microsoft.com"

# Socket-level timeout for the download: 60 s without a successful block
# fails the attempt rather than hanging the job. Mirrors are still tried
# before the whole product fails.
DOWNLOAD_TIMEOUT = 60  # seconds

# One read wants to be small enough to hash incrementally but large enough
# to keep a 200 MiB transfer from spending its time in syscalls; progress
# prints are throttled to one line per PROGRESS_INTERVAL so a CI log stays
# readable.
CHUNK = 1024 * 1024
PROGRESS_INTERVAL = 25 * 1024 * 1024

# Playwright's completion marker, written by its installer and consulted
# (by filename only) before any download. Seeding writes it ourselves.
INSTALLATION_COMPLETE = "INSTALLATION_COMPLETE"

# Our provenance marker: written AFTER the digest check passed, naming the
# digest the directory's archive verified against. A directory that carries
# playwright's INSTALLATION_COMPLETE but no matching DIGEST_VERIFIED is an
# UNVERIFIED install -- it is replaced, never trusted.
PROVENANCE_FILE = "DIGEST_VERIFIED"

# The committed digest table: (browser name, playwright revision) -> sha256
# of the archive cdn.playwright.dev serves for that revision. Observed by
# downloading each archive (following the CDN's redirect) and hashing it
# with sha256sum, 2026-09-29, against playwright 1.63.0's browsers.json.
#
# Playwright publishes no digest anywhere (browsers.json has none and the
# installer never hashes), so this table IS the trust anchor, and it is
# updated BY HAND -- the repo's standard for checksummed binaries, same as
# actionlint.yml's ACTIONLINT_SHA256:
#
#   1. Dependabot (or you) bumps playwright in requirements-test.txt;
#   2. run this script -- it fails naming the new revision and the archive
#      URL to hash;
#   3. download that archive, `sha256sum` it, add the row here, and commit
#      the playwright bump and the digest in ONE commit. The revision moved
#      means the bytes moved; trusting the new bytes is a human decision
#      made at that sha256sum step, never a runtime decision. Until the row
#      lands, CI stays red: there is no bypass flag and no unverified
#      fallback.
DIGESTS = {
    ("chromium", "1243"):
        "8aac35011c18f6e2d10696154af89a5728ac2ddd6dc6fad24ffdf243c3fcfd5a",
    ("chromium-headless-shell", "1243"):
        "a9da028861a0cf789ff25c2fed45f5f1aaf969ed9247835b6a7821a4f7af9d1d",
    ("ffmpeg", "1011"):
        "ebc74fc5b94830176a3c2914ae96bd8bc7f6a91f4f33890230f84a172ee61ccc",
}

# The products `playwright install chromium` needs on linux x64, with the
# layout observed on disk after a real install (playwright 1.63.0):
#
#   <browsers>/chromium-<rev>/chrome-linux64/chrome
#   <browsers>/chromium_headless_shell-<rev>/chrome-headless-shell-linux64/
#       chrome-headless-shell
#   <browsers>/ffmpeg-<rev>/ffmpeg-linux
#
# plus a zero-byte INSTALLATION_COMPLETE marker per directory. The headless
# shell is not optional: since playwright 1.49 a headless launch resolves to
# it by default, so it is the binary the browser suite actually executes.
# ffmpeg rides along because the chromium product depends on it -- leaving
# it out would just send `playwright install` off to fetch it unverified.
#
# archive_path is the registry's own download template with the CDN host
# split off; hosts are tried in order and only on transport failure.


@dataclass(frozen=True)
class ProductSpec:
    """One browser product and its archive/executable layout."""

    name: str
    dir_prefix: str
    archive_path: str
    hosts: tuple
    executable: str


PRODUCTS = (
    ProductSpec(
        name="chromium",
        dir_prefix="chromium",
        archive_path="builds/cft/{browser_version}/linux64/chrome-linux64.zip",
        hosts=(CDN,),
        executable="chrome-linux64/chrome",
    ),
    ProductSpec(
        name="chromium-headless-shell",
        dir_prefix="chromium_headless_shell",
        archive_path=("builds/cft/{browser_version}/linux64/"
                      "chrome-headless-shell-linux64.zip"),
        hosts=(CDN,),
        executable="chrome-headless-shell-linux64/chrome-headless-shell",
    ),
    ProductSpec(
        name="ffmpeg",
        dir_prefix="ffmpeg",
        archive_path="builds/ffmpeg/{revision}/ffmpeg-linux.zip",
        hosts=(CDN, PRSS),
        executable="ffmpeg-linux",
    ),
)


class InstallError(Exception):
    """A condition that must fail the job loudly (printed, exit code 2)."""


@dataclass(frozen=True)
class Product:
    """A product resolved against the installed playwright's registry."""

    spec: ProductSpec
    revision: str
    browser_version: str | None
    digest: str


def find_playwright_spec():
    """The import spec of the installed playwright package (patchable)."""
    return importlib.util.find_spec("playwright")


def find_browsers_json() -> Path:
    """Locate browsers.json inside the installed playwright package.

    The package ships it at playwright/driver/package/browsers.json; the
    pinned requirements-test.txt version always pairs with the archive URLs
    and revisions the script derives from it.
    """
    spec = find_playwright_spec()
    if spec is None or not spec.submodule_search_locations:
        raise InstallError(
            "playwright is not importable; install the test toolchain first "
            "(pip install -r requirements-test.txt)")
    browsers_json = (
        Path(next(iter(spec.submodule_search_locations)))
        / "driver" / "package" / "browsers.json")
    if not browsers_json.is_file():
        raise InstallError(
            f"the installed playwright has no browsers.json at "
            f"{browsers_json}; its layout is not the one this script knows "
            "-- re-verify the install layout before extending it")
    return browsers_json


def load_registry(browsers_json: Path) -> dict:
    """Parse browsers.json into {name: entry}."""
    try:
        document = json.loads(browsers_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallError(
            f"cannot read playwright's browsers.json at {browsers_json}: "
            f"{error}") from error
    entries = document.get("browsers")
    if not isinstance(entries, list):
        raise InstallError(
            f"{browsers_json} has no 'browsers' list; playwright's registry "
            "format moved -- re-verify before extending this script")
    registry = {}
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str):
            raise InstallError(
                f"{browsers_json}: a browsers entry has no name; the "
                "registry format moved")
        registry[name] = entry
    return registry


def build_products(registry: dict, digests: dict | None = None) -> list:
    """Resolve every product's revision and expected digest.

    An unknown revision is the documented trust-on-first-use moment: the
    error names the revision and the URL to hash so the table row can be
    added in the same commit as the playwright bump.
    """
    if digests is None:
        digests = DIGESTS
    products = []
    for spec in PRODUCTS:
        entry = registry.get(spec.name)
        if entry is None:
            raise InstallError(
                f"playwright's browsers.json has no {spec.name!r} entry; "
                "the product set this script installs no longer matches "
                "the registry -- re-verify the install set")
        revision = entry.get("revision")
        if not isinstance(revision, str):
            raise InstallError(
                f"playwright's browsers.json entry {spec.name!r} has no "
                "revision; the registry format moved")
        browser_version = entry.get("browserVersion")
        if "{browser_version}" in spec.archive_path \
                and not isinstance(browser_version, str):
            raise InstallError(
                f"playwright's browsers.json entry {spec.name!r} has no "
                "browserVersion, which its archive URL template needs")
        digest = digests.get((spec.name, revision))
        if digest is None:
            url = f"{CDN}/{spec.archive_path.format(browser_version=browser_version, revision=revision)}"
            raise InstallError(
                f"no committed digest for {spec.name} revision {revision} "
                f"(playwright moved its pin). To trust it: download\n"
                f"  {url}\n"
                f"hash it with sha256sum, add the digest to DIGESTS in "
                f"scripts/ci/install_chromium.py keyed "
                f'("{spec.name}", "{revision}"), and commit that together '
                "with the playwright bump. Nothing is downloaded or executed "
                "until then.")
        products.append(Product(spec, revision, browser_version, digest))
    return products


def browsers_root() -> Path:
    """The browsers directory, exactly as playwright itself resolves it.

    PLAYWRIGHT_BROWSERS_PATH wins; otherwise the platform cache directory
    (XDG_CACHE_HOME or ~/.cache on Linux) plus ms-playwright. The value
    "0" is refused: playwright reserves it for the package-local
    .local-browsers directory (verified in 1.63.0's registry, where
    ``envDefined === "0"`` redirects the install), so honouring it as a
    literal path would seed and verify ./0 while playwright downloaded
    unverified browsers elsewhere -- exactly where the no-re-download
    assertion never looks.
    """
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        if override == "0":
            raise InstallError(
                'PLAYWRIGHT_BROWSERS_PATH="0" is a playwright-reserved '
                "value, not a path: it makes playwright install resolve "
                "the package-local .local-browsers directory, while this "
                "script would seed and verify ./0 -- the browsers would "
                "land unverified where the no-re-download assertion never "
                "looks. Unset the variable or name a real directory.")
        return Path(override)
    cache = os.environ.get("XDG_CACHE_HOME") \
        or Path.home() / ".cache"
    return Path(cache) / "ms-playwright"


def install_dir(root: Path, product: Product) -> Path:
    """The product's directory under the browsers root."""
    return root / f"{product.spec.dir_prefix}-{product.revision}"


def archive_urls(product: Product) -> list:
    """The archive URLs for a product, hosts in mirror order."""
    path = product.spec.archive_path.format(
        browser_version=product.browser_version,
        revision=product.revision)
    return [f"{host}/{path}" for host in product.spec.hosts]


def download_archive(urls: list, destination: Path, label: str,
                     timeout: int = DOWNLOAD_TIMEOUT) -> tuple:
    """Download the first mirror that answers, streaming to destination.

    Returns (sha256 hex digest, bytes downloaded). Mirrors are tried in
    order and only on transport failure (URLError/HTTPError, socket
    timeouts (OSError), malformed or unopenable URLs (ValueError)); the
    digest check downstream is what decides trust, so a mirror fallback is
    never a trust decision.
    """
    last_error = None
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response, \
                    open(destination, "wb") as out:
                digest = hashlib.sha256()
                downloaded = 0
                next_progress = PROGRESS_INTERVAL
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    digest.update(chunk)
                    out.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= next_progress:
                        print(f"{label}: {downloaded // (1024 * 1024)} MiB",
                              flush=True)
                        next_progress += PROGRESS_INTERVAL
                return digest.hexdigest(), downloaded
        except (urllib.error.URLError, OSError, ValueError) as error:
            last_error = error
            print(f"{label}: {url} failed ({error}); trying the next mirror"
                  if len(urls) > 1 else f"{label}: {url} failed ({error})",
                  file=sys.stderr, flush=True)
    raise InstallError(
        f"{label}: every download mirror failed; last error: {last_error}")


def extract_archive(archive_path: Path, destination: Path) -> None:
    """Extract a verified zip into destination, honoring its unix modes
    owner-only.

    The CFT zips store their mode bits (the chrome binaries are 0755), and
    restoring them is what makes the executables executable. Everything
    past the owner bits is masked off -- CodeQL py/overly-permissive-file
    flags group-readable files too, and the job runs as a single user (the
    browser is launched by the same uid that extracted it), so a 0755
    archive entry lands 0700. Symlink
    entries and path escapes are refused loudly: playwright's zips carry
    none, so one appearing is a format change to inspect, not to follow.
    """
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise InstallError(
                        f"{archive_path}: entry {info.filename!r} is a "
                        "symlink; playwright's archives carry none, so "
                        "refusing to extract until this is re-verified")
                parts = info.filename.split("/")
                if info.filename.startswith("/") \
                        or ".." in parts:
                    raise InstallError(
                        f"{archive_path}: entry {info.filename!r} escapes "
                        "the extraction directory (zip-slip); refusing")
                target = destination.joinpath(*parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, \
                        open(target, "wb") as out:
                    shutil.copyfileobj(source, out)
                # Owner-only (CodeQL py/overly-permissive-file flags group
                # bits too): functionally identical here because the job
                # runs as a single user — the browser is launched by the
                # same uid that extracted it; a 0755 entry lands 0700.
                os.chmod(target, (mode & 0o700) or 0o600)
    except (OSError, zipfile.BadZipFile) as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise InstallError(
            f"extracting {archive_path} into {destination} failed: "
            f"{error}") from error


def verify_executable(product_dir: Path, product: Product) -> None:
    """Assert the product's executable is present and executable."""
    executable = product_dir / product.spec.executable
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise InstallError(
            f"{product.spec.name}: the browser executable is missing or "
            f"not executable after extraction: {executable}")


def read_provenance(product_dir: Path) -> dict | None:
    """The directory's DIGEST_VERIFIED record, or None when absent/broken."""
    try:
        record = json.loads(
            (product_dir / PROVENANCE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, NotADirectoryError):
        return None
    if not isinstance(record, dict):
        return None
    return record


def seed_product(root: Path, product: Product,
                 timeout: int = DOWNLOAD_TIMEOUT) -> str:
    """Pre-seed one product's directory from its digest-verified archive.

    Skips the download entirely when a matching provenance marker proves
    the present directory is the verified bytes; replaces (never trusts) a
    directory that playwright installed without one. Returns the outcome,
    one of "already-verified", "replaced-unverified", "downloaded".
    """
    product_dir = install_dir(root, product)
    provenance = read_provenance(product_dir)
    if provenance is not None \
            and provenance.get("sha256") == product.digest:
        verify_executable(product_dir, product)
        print(f"{product.spec.name} revision {product.revision}: "
              f"digest-verified browser already present -- skipping the "
              f"download")
        return "already-verified"

    outcome = "downloaded"
    if product_dir.exists() and any(product_dir.iterdir()):
        print(f"{product.spec.name}: replacing an unverified install "
              f"(no matching {PROVENANCE_FILE} marker) with the "
              f"digest-checked archive", file=sys.stderr)
        outcome = "replaced-unverified"
    shutil.rmtree(product_dir, ignore_errors=True)

    urls = archive_urls(product)
    with tempfile.TemporaryDirectory(
            prefix=f"install-chromium-{product.spec.name}-") as scratch:
        archive = Path(scratch) / "archive.zip"
        actual, _size = download_archive(urls, archive, product.spec.name,
                                         timeout)
        if actual != product.digest:
            raise InstallError(
                f"{product.spec.name} revision {product.revision}: the "
                f"downloaded archive digest does not match the committed "
                f"digest -- refusing to seed or execute it\n"
                f"  expected: {product.digest}\n"
                f"  actual:   {actual}\n"
                f"  archive:  {urls[0]}\n"
                "If a playwright bump moved the revision, follow the update "
                "recipe in DIGESTS; otherwise treat the source as "
                "compromised and investigate.")
        try:
            extract_archive(archive, product_dir)
            (product_dir / INSTALLATION_COMPLETE).write_bytes(b"")
            (product_dir / PROVENANCE_FILE).write_text(
                json.dumps({"product": product.spec.name,
                            "revision": product.revision,
                            "sha256": product.digest,
                            "archive": urls[0]}, indent=2) + "\n",
                encoding="utf-8")
            verify_executable(product_dir, product)
        except BaseException:
            shutil.rmtree(product_dir, ignore_errors=True)
            raise
    print(f"{product.spec.name} revision {product.revision}: seeded from the "
          f"digest-verified archive ({_size} bytes)")
    return outcome


def run_playwright_install(root: Path) -> None:
    """Run playwright's own install against the pre-seeded directory.

    --with-deps still apt-installs the shared libraries headless Chromium
    links against; the browser archives themselves are already present, so
    the downloader has nothing left to fetch.
    """
    command = [sys.executable, "-m", "playwright", "install",
               "--with-deps", "chromium"]
    print(f"+ {' '.join(command)}", flush=True)
    result = subprocess.run(
        command,
        env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(root)},
        check=False)
    if result.returncode != 0:
        raise InstallError(
            f"playwright install exited {result.returncode}; its output is "
            "above. The browser archives were verified before this ran, so "
            "a failure here is playwright's apt/validation step, not a "
            "download.")


def assert_seeded_intact(root: Path, products: list,
                         inodes: dict) -> None:
    """Assert the post-install directory still holds the verified bytes.

    A playwright re-download removes and re-creates a product directory,
    which changes its inode; the completion/provenance markers and the
    executable are re-checked for good measure. A new browser-shaped
    directory (`*-<digits>`) that this script did not seed means playwright
    fetched something unverified -- both fail the job.
    """
    seeded = set()
    for product in products:
        product_dir = install_dir(root, product)
        seeded.add(product_dir.name)
        expected = inodes.get(product_dir.name)
        try:
            actual = product_dir.stat().st_ino
        except FileNotFoundError as error:
            raise InstallError(
                f"{product.spec.name}: the seeded directory vanished during "
                f"playwright install ({product_dir}) -- the digest-verified "
                "browser is gone and nothing replaced it") from error
        if actual != expected:
            raise InstallError(
                f"{product.spec.name}: the seeded directory was replaced "
                f"during playwright install (inode {expected} -> {actual}) "
                "-- playwright re-downloaded the browser after the digest "
                "check, so the executing binary would be unverified")
        provenance = read_provenance(product_dir)
        if provenance is None \
                or provenance.get("sha256") != product.digest:
            raise InstallError(
                f"{product.spec.name}: the {PROVENANCE_FILE} marker is "
                "missing or names a different digest after playwright "
                "install")
        verify_executable(product_dir, product)
    for entry in sorted(root.iterdir()):
        name = entry.name
        if name in seeded or not entry.is_dir() \
                or not re.fullmatch(r".+-\d+", name):
            continue
        raise InstallError(
            f"an unexpected browser directory {name!r} appeared during "
            "playwright install -- it was not digest-verified by this "
            "script; extend PRODUCTS/DIGESTS before trusting it")


def main(argv=None) -> int:
    """Resolve, verify, seed, then let playwright install its apt libs."""
    parser = argparse.ArgumentParser(
        description="Digest-verify Playwright's Chromium archives against "
                    "the committed table in this file, pre-seed the browsers "
                    "directory, then run playwright install --with-deps "
                    "chromium (which then downloads nothing).")
    parser.parse_args(argv)

    try:
        registry = load_registry(find_browsers_json())
        products = build_products(registry)
        root = browsers_root()
        for product in products:
            seed_product(root, product)
        inodes = {install_dir(root, product).name:
                  install_dir(root, product).stat().st_ino
                  for product in products}
        run_playwright_install(root)
        assert_seeded_intact(root, products, inodes)
    except InstallError as error:
        print(str(error), file=sys.stderr)
        return 2
    print("Chromium is digest-verified and playwright downloaded nothing "
          "beyond what this script verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
