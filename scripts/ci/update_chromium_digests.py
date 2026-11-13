#!/usr/bin/env python3
"""Add install_chromium.py's missing digest rows for the installed playwright.

A row's digest is computed from what Playwright's download hosts served over
TLS at bump time (the registry's hosts in mirror order, the CDN's redirect
target included): it records those bytes and is not an independent
attestation of them. The reviewed commit adding the rows with the bump is the
trust decision.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

if __package__:
    from . import install_chromium
else:
    install_chromium = importlib.import_module("install_chromium")


def verify_archive(archive: Path, product, url: str) -> None:
    try:
        with zipfile.ZipFile(archive) as opened:
            entries = opened.infolist()
    except (OSError, zipfile.BadZipFile) as error:
        raise install_chromium.InstallError(
            f"{url}: not a readable zip archive ({error}); refusing to "
            "record its digest") from error
    for info in entries:
        install_chromium.refuse_unsafe_entry(url, info)
    if product.spec.executable not in {info.filename for info in entries}:
        raise install_chromium.InstallError(
            f"{url}: the archive lists no {product.spec.executable}; its "
            "layout is not the one install_chromium.py extracts -- refusing "
            "to record its digest")


def fetch_digest(product) -> str:
    urls = install_chromium.archive_urls(product)
    with tempfile.TemporaryDirectory(
            prefix=f"update-chromium-digests-{product.spec.name}-") as scratch:
        archive = Path(scratch) / "archive.zip"
        digest, _size = install_chromium.download_archive(
            urls, archive, product.spec.name)
        verify_archive(archive, product, urls[0])
    return digest


def main(argv=None) -> int:
    argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0]).parse_args(argv)
    table_path = install_chromium.DIGESTS_FILE
    try:
        registry = install_chromium.load_registry(
            install_chromium.find_browsers_json())
        table = json.loads(table_path.read_text(encoding="utf-8"))
        missing = [product for product in (
            install_chromium.resolve_product(registry, spec)
            for spec in install_chromium.PRODUCTS)
            if product.revision not in table.get(product.spec.name, {})]
        rows = [(product, fetch_digest(product)) for product in missing]
    except install_chromium.InstallError as error:
        print(f"{error}\nNo digest row was written.", file=sys.stderr)
        return 2
    if not rows:
        print(f"{table_path.name} already holds a row for every revision "
              "this playwright pins; nothing written.")
        return 0
    for product, digest in rows:
        table[product.spec.name] = {product.revision: digest,
                                    **table.get(product.spec.name, {})}
        print(f'added ("{product.spec.name}", "{product.revision}"): '
              f"{digest}\n  archive {install_chromium.archive_urls(product)[0]}")
    staged = table_path.with_name(table_path.name + ".tmp")
    staged.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8",
                      newline="\n")
    os.replace(staged, table_path)
    print(f"Review and commit {table_path.name} with the playwright bump.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
