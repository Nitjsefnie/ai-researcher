"""Read GDPval-AA's own-priced cost per task from its evaluation dataset."""
from __future__ import annotations

import gzip
import hashlib
import html as html_lib
import json
import math
import pathlib
import re
import sys
from typing import NamedTuple, NoReturn
import zlib

import aa_aes_gcm
import fetch_http

GDPVAL_URL = "https://artificialanalysis.ai/evaluations/gdpval-aa"
GDPVAL_VERSION = "2.1"
# AA's GDPval-AA taskCount from its evaluation-config chunk.
GDPVAL_TASK_COUNT = 220
COST_FIELD = "gdpvalCostPerTask"


class Evaluation(NamedTuple):
    """In-memory evaluation records, their eligible costs, and data path."""

    records: list[dict]
    costs: dict[str, float]
    path: str


def _fail(path: str, detail: str) -> NoReturn:
    sys.exit(f"{path}: {detail} -- schema changed")


def _number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _fallback_rates(fallbacks: dict, path: str) -> dict:
    rates = {}
    for ident, entry in fallbacks.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("rateByEval", {}), dict):
            _fail(path, "invalid fallback rates")
        by_eval = entry.get("rateByEval", {})
        if "gdpval-aa" not in by_eval:
            continue
        rate = by_eval["gdpval-aa"]
        if (not isinstance(rate, dict) or any(
                not _number(rate.get(key)) or not 0 <= rate[key] <= 1
                for key in ("input", "output", "reasoning"))):
            _fail(path, "invalid GDPval fallback rate")
        rates[ident] = any(rate[key] != 0 for key in ("input", "output", "reasoning"))
    return rates


def _counts(row: dict, path: str) -> dict | None:
    canonical = row.get("canonicalEvalTokenCounts")
    if canonical is None:
        return None
    if not isinstance(canonical, dict):
        _fail(path, "invalid canonical token counts")
    counts = canonical.get("gdpval")
    if counts is None:
        return None
    keys = {"input", "answer", "reasoning", "cacheableInput"}
    if not isinstance(counts, dict) or set(counts) != keys:
        _fail(path, "invalid GDPval token counts")
    for key, value in counts.items():
        if key == "cacheableInput" and value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            _fail(path, "invalid GDPval token count")
    if counts["cacheableInput"] is not None and counts["cacheableInput"] > counts["input"]:
        _fail(path, "cacheable input exceeds input")
    return counts


def _cost(row: dict, counts: dict) -> float | None:
    input_price = row.get("price1mInputTokens")
    output_price = row.get("price1mOutputTokens")
    hit_rate = row.get("cacheHitRate")
    cacheable = counts["cacheableInput"]
    if input_price is None or output_price is None or (cacheable is not None and hit_rate is None):
        return None
    hit_price = row.get("cacheHitPrice")
    write_price = row.get("cacheWritePrice")
    if cacheable is None:
        noncache, read, write = counts["input"], 0, 0
    else:
        read = cacheable * hit_rate
        noncache, write = 0, counts["input"] - read
    input_cost = (noncache / 1e6 * input_price
                  + read / 1e6 * (input_price if hit_price is None else hit_price)
                  + write / 1e6 * (input_price if write_price is None else write_price))
    output_cost = (counts["reasoning"] / 1e6 * output_price
                   + counts["answer"] / 1e6 * output_price)
    total = (input_cost + output_cost) / GDPVAL_TASK_COUNT
    return total if total > 0 else None


def costs(data, path: str) -> dict[str, float]:
    """Validate the decrypted shape and return positive own-priced costs by slug."""
    if (not isinstance(data, dict) or set(data) != {"models", "priceFallbackByModelId"}
            or not isinstance(data["models"], list)
            or not isinstance(data["priceFallbackByModelId"], dict)):
        _fail(path, "invalid GDPval data")
    rates = _fallback_rates(data["priceFallbackByModelId"], path)
    out = {}
    seen = set()
    for row in data["models"]:
        if not isinstance(row, dict) or not isinstance(row.get("slug"), str) or not row["slug"]:
            _fail(path, "invalid model slug")
        slug = row["slug"]
        if slug in seen:
            _fail(path, "duplicate model slug")
        seen.add(slug)
        ident = row.get("id")
        if ident is not None and not isinstance(ident, str):
            _fail(path, "invalid model id")
        counts = _counts(row, path)
        for key in ("gdpval", "cacheHitRate", "price1mInputTokens", "price1mOutputTokens",
                    "cacheHitPrice", "cacheWritePrice"):
            if row.get(key) is not None and not _number(row[key]):
                _fail(path, f"invalid {key}")
        if row.get("gdpval") is None or counts is None or (ident is not None and rates.get(ident, False)):
            continue
        value = _cost(row, counts)
        if value is not None:
            out[slug] = value
    return out


def join(records: list[dict], values: dict[str, float]) -> list[dict]:
    """Add the evaluation cost to matching model records by slug."""
    result = []
    for source in records:
        record = dict(source)
        record.pop(COST_FIELD, None)
        slug = record.get("slug")
        value = values.get(slug) if isinstance(slug, str) else None
        if value is not None:
            record[COST_FIELD] = value
        result.append(record)
    return result


def _manifest(page: str, flight_payload) -> dict:
    title = re.search(r"<title\b[^>]*>(.*?)</title\s*>", page, re.IGNORECASE | re.DOTALL)
    version = rf"GDPval-AA v{re.escape(GDPVAL_VERSION)}(?![.\d])"
    if not title or not re.search(version, html_lib.unescape(title.group(1))):
        sys.exit(f"{GDPVAL_URL}: page title does not name GDPval-AA v{GDPVAL_VERSION}")
    try:
        payload = flight_payload(page)
        matches = list(re.finditer(r'"manifest"\s*:\s*', payload))
        if len(matches) != 1:
            raise ValueError("expected one manifest")
        manifest, _ = json.JSONDecoder().raw_decode(payload[matches[0].end():])
        if not isinstance(manifest, dict):
            raise ValueError("invalid manifest")
        path, key = manifest.get("path"), manifest.get("key")
        if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
                or not isinstance(key, str) or len(bytes.fromhex(key)) != 32):
            raise ValueError("invalid manifest path or key")
        return manifest
    except (SystemExit, ValueError, TypeError) as exc:
        sys.exit(f"{GDPVAL_URL}: missing or invalid flight manifest ({exc})")


def fetch(cached_page, cached_data, fetch_html, flight_payload, user_agent, timeout, sleep):
    """Read and authenticate the evaluation records and their per-slug costs."""
    try:
        page = fetch_html(cached_page, GDPVAL_URL)
    except OSError as exc:
        sys.exit(f"{GDPVAL_URL}: page read failed: {exc}")
    manifest = _manifest(page, flight_payload)
    path = manifest["path"]
    try:
        body = (pathlib.Path(cached_data).read_bytes() if cached_data else
                fetch_http.fetch_bytes("https://artificialanalysis.ai" + path,
                                       {"User-Agent": user_agent}, timeout, sleep=sleep))
    except OSError as exc:
        sys.exit(f"{path}: data read failed: {exc}")
    key = bytes.fromhex(manifest["key"])
    nonce = hashlib.sha256(key).digest()[:12]
    try:
        compressed = aa_aes_gcm.decrypt(key, nonce, body)
    except ValueError as exc:
        sys.exit(f"{path}: data authentication or decryption failed: {exc}")
    try:
        decoded = gzip.decompress(compressed)
    except (OSError, EOFError, zlib.error) as exc:
        sys.exit(f"{path}: gzip decompression failed: {exc}")
    try:
        data = json.loads(decoded)
    except (UnicodeDecodeError, ValueError) as exc:
        sys.exit(f"{path}: JSON decoding failed: {exc}")
    values = costs(data, path)
    return Evaluation(data["models"], values, path)
