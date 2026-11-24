"""Extract AA's model, coding-agent and index composition records from flight payloads."""
from __future__ import annotations

import decimal
import json
import re
import sys
import typing

CODING_ROW_FLOOR = 5
# AA's prose cites older generations without the full brand prefix.
VERSION_RE = re.compile(r"Artificial Analysis Intelligence Index v(\d+(?:\.\d+)*)")
FLIGHT_ROW_RE = re.compile(rb"([0-9a-f]*):(?:T([0-9a-f]+),)?")
REFERENCE_RE = re.compile(r"\$L?([0-9a-f]+)")
SUITE_WEIGHT = "intelligence-index-weighting"
INDEX_ATTRIBUTE = "intelligence-index"


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
        # The leaderboard moved slug to release.slug (issue #417).
        release = m.get("release")
        if (not isinstance(m.get("slug"), str) and isinstance(release, dict)
                and isinstance(release.get("slug"), str)):
            m["slug"] = release["slug"]
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


def named_version(page_text: str) -> str | None:
    """The version-sorted maximum of the page's citations."""
    versions = [tuple(int(p) for p in found.split(".")) for found in VERSION_RE.findall(page_text)]
    return ".".join(str(p) for p in max(versions)) if versions else None


def flight_rows(payload: str) -> dict[str, typing.Any]:
    """The payload's JSON rows by id; a row that does not parse is skipped."""
    data, rows, at = payload.encode("utf-8", "surrogatepass"), {}, 0
    while at < len(data):
        head = FLIGHT_ROW_RE.match(data, at)
        if head and head[2]:  # A text row ends by its byte length.
            at = head.end() + int(head[2], 16)
            continue
        line = data[at:].partition(b"\n")[0]
        at += len(line) + 1
        if head:
            try:
                rows[head[1].decode("ascii")] = json.loads(line[len(head[0]):])
            except ValueError:
                continue
    return rows


def flight_nodes(rows: dict[str, typing.Any]) -> typing.Iterator[typing.Any]:
    pending = list(rows.values())
    while pending:
        node = pending.pop()
        if isinstance(node, (list, dict)):
            yield node
            pending.extend(node if isinstance(node, list) else node.values())


def flight_children(element: typing.Any, rows: dict[str, typing.Any]) -> list:
    """The elements a flight element lists as its children, references read."""
    def read(value: typing.Any) -> typing.Any:
        reference = REFERENCE_RE.fullmatch(value) if isinstance(value, str) else None
        return rows.get(reference[1]) if reference else value

    props = element[3] if isinstance(element, list) and len(element) == 4 else None
    children = props.get("children") if isinstance(props, dict) else None
    return [child for child in map(read, children if isinstance(children, list) else [])
            if isinstance(child, list) and len(child) == 4 and isinstance(child[3], dict)]


def index_composition(payload: str, url: str) -> list[tuple[str, decimal.Decimal, str]]:
    """The methodology page's index suite as [(slug, weight percent, name)].

    The slug is the index-flagged catalog entry's for the row's name; only a
    name no entry has takes the row's own key. A page without a catalog or a
    suite, or whose suite does not read or sum to 100%, is refused, naming it."""
    def refuse(problem: str) -> typing.NoReturn:
        sys.exit(f"{url}: the Intelligence Index composition cannot be read: {problem} -- re-read the page by hand")

    rows = flight_rows(payload)
    catalog: dict[str, set[str]] = {}
    suite: list[tuple[typing.Any, dict[str, typing.Any]]] = []
    for node in flight_nodes(rows):
        if isinstance(node, list):
            for row in flight_children(node, rows):
                cells = {str(cell[2]): cell[3].get("children") for cell in flight_children(row, rows)
                         if cell[1] == "td"}
                if SUITE_WEIGHT in cells:
                    suite.append((row[2], cells))
        elif isinstance(node.get("shortName"), str) and isinstance(node.get("attributes"), list):
            hrefs = catalog.setdefault(node["shortName"], set())
            if INDEX_ATTRIBUTE in node["attributes"]:
                hrefs.add(str(node.get("href")))
    if not any(catalog.values()):
        refuse("the catalog carries no index evaluation")
    composition = []
    for key, cells in suite:
        name, weight = cells.get("evaluation"), cells[SUITE_WEIGHT]
        # A line end would break the recorded text, a lone surrogate its encoding.
        if not isinstance(name, str) or not name.strip() or re.search("^\\$|[\r\n\ud800-\udfff]", name):
            refuse(f"row {key!r} has no single name ({name!r})")
        if (not isinstance(weight, str) or not re.fullmatch(r"[0-9]+(\.[0-9]+)?%", weight)
                or not decimal.Decimal(weight[:-1])):
            refuse(f"{name}: the weighting {weight!r} is not a positive percentage")
        hrefs = catalog.get(name, {f"/evaluations/{key or ''}"})
        slugs = [re.fullmatch(r"/evaluations/([A-Za-z0-9._-]+)", href) for href in hrefs]
        if len(slugs) != 1 or slugs[0] is None:
            refuse(f"{name}: no readable slug, or several ({', '.join(sorted(hrefs))})")
        composition.append((slugs[0][1], decimal.Decimal(weight[:-1]), name))
    if not composition:
        refuse("no suite row carries a weighting")
    for column in (0, 2):
        values = [entry[column] for entry in composition]
        if len(set(values)) != len(values):
            refuse(f"duplicate slugs or names among {values}")
    total = sum(weight for _, weight, _ in composition)
    if total != 100:
        refuse(f"the weightings sum to {total}%")
    return composition
