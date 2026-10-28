"""Extract model and coding-agent records from AA flight payloads."""
from __future__ import annotations

import json
import re
import sys

CODING_ROW_FLOOR = 5


def balanced_array(text: str, start: int) -> str | None:
    """Return the JSON array literal beginning at text[start] == '['."""
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        c = text[j]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def richest_models_array(payload: str) -> list[dict]:
    """Take the richest records from models or initialModels (issue #266)."""
    best: list[dict] = []
    best_fields: set[str] = set()
    names: set[str] = set()
    for m in re.finditer(r'"(models|initialModels)"\s*:\s*\[', payload):
        names.add(m.group(1))
        raw = balanced_array(payload, m.end() - 1)
        if not raw:
            continue
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            continue
        richest = max((x for x in arr if isinstance(x, dict)), key=len, default={})
        if len(richest) > len(best_fields):
            best, best_fields = arr, set(richest)
    if len(best_fields) < 20:
        sys.exit(
            f"no full scored model records found in arrays: {', '.join(sorted(names)) or 'none'}; "
            f"richest record had {len(best_fields)} fields "
            f"({', '.join(sorted(best_fields)) or 'none'}); expected scored records "
            "with at least 20 fields, including intelligenceIndex, "
            "intelligenceIndexCostPerTask and contextWindowTokens")
    # RSC back-references are not model records.
    records = [m for m in best if isinstance(m, dict)]
    # AA may repeat rows.
    seen: set[str] = set()
    unique = []
    for m in records:
        slug = m.get("slug")
        if isinstance(slug, str):
            if slug in seen:
                continue
            seen.add(slug)
        unique.append(m)
    return unique


def balanced_object(text: str, start: int) -> str | None:
    """Return the JSON object literal beginning at text[start] == '{'."""
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        c = text[j]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def enclosing_object(payload: str, offset: int, window: int = 40000) -> dict | None:
    """Find the smallest object around offset."""
    i = offset
    floor = max(0, offset - window)
    while i > floor:
        i = payload.rfind("{", floor, i)
        if i < 0:
            return None
        raw = balanced_object(payload, i)
        if raw and i + len(raw) > offset:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                continue
    return None


def coding_agent_rows(payload: str) -> list[dict]:
    """Collect paired score/cost rows across AA's arrays and back-references."""
    seen: dict[str, dict] = {}
    for m in re.finditer(r'"indexScore"', payload):
        row = enclosing_object(payload, m.start())
        if not isinstance(row, dict):
            continue
        mean = row.get("mean")
        if not (isinstance(row.get("indexScore"), (int, float))
                and isinstance(mean, dict)
                and isinstance(mean.get("costUsd"), (int, float))):
            continue
        key = row.get("id") or row.get("displayLabel")
        if isinstance(key, str):
            seen.setdefault(key, row)
    priced = list(seen.values())
    if len(priced) < CODING_ROW_FLOOR:
        sys.exit(
            f"coding agent index: only {len(priced)} rows carry indexScore and "
            f"mean.costUsd -- schema changed"
        )
    return priced
