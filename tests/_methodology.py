"""AA's methodology page in its live flight shape, for the composition tests."""
import decimal
import json

VERSION = "5.0.2"
CITED = f"Artificial Analysis Intelligence Index v{VERSION}"
# (table row key, weighting cell, evaluation name, catalog slug or None)
SUITE = (
    ("aa-briefcase", "15%", "AA-Briefcase v1.1", "aa-briefcase"),
    ("automation-bench-aa", "5%", "AutomationBench-AA", "automationbench-aa"),
    ("gdp-pdf", "5%", "GDP.pdf", "gdp-pdf"),
    ("frontiercode-2-0", "15%", "FrontierCode-AA 2.0", "frontiercode-2-0"),
    ("terminal-bench-v4-1", "10%", "Terminal-Bench 4.1", "terminalbench-4-1"),
    ("terminal-bench-science", "15%", "Terminal-Bench-Science 0.1", "terminal-bench-science"),
    ("critpt-v2-hard", "10%", "CritPt v2 (Hard Subset)", None),
    ("aa-omniscience", "15%", "AA-Omniscience v1.1", "omniscience"),
    ("hle-diamond", "10%", "HLE-Diamond", "hle-diamond"))
COMPOSITION = [(slug or key, decimal.Decimal(weight.rstrip("%")), name) for key, weight, name, slug in SUITE]
RECORDED = f"index version: {VERSION}\n" + "".join(
    f"index evaluation: {slug} {weight}% {name}\n" for slug, weight, name in COMPOSITION)
WEIGHTS = {slug: int(weight) / 100 for slug, weight, _ in COMPOSITION}


def catalog_entry(name, href, attributes=("intelligence-index",)):
    return {"name": f"{name} Benchmark", "shortName": name, "href": href, "logo": "/img/logo.svg", "deprecated": False,
            "attributes": list(attributes), "keywords": [], "change": "$undefined"}


def suite_row(key, weight, name):
    """A suite row's element, its cells in the live order around the two read."""
    return ["$", "tr", key, {"className": "even:bg-brand-blue-light/50", "children": [
        ["$", "td", cell, {"className": "px-3 py-2", "rowSpan": "$undefined", "colSpan": "$undefined", "children": text}]
        for cell, text in (("evaluation", name), ("questions", "66"), ("intelligence-index-weighting", weight),
                           ("tool-usage", ["$", "span", None, {"children": "✓"}]))]}]


def methodology_payload(suite=SUITE, catalog=None):
    """The flight payload as AA streams it: the third suite row's cells and every
    later row sit behind references, here written last row first; a text row
    runs into the next row; other tables and catalog entries sit beside."""
    if catalog is None:
        catalog = [catalog_entry(name, f"/evaluations/{slug}") for _, _, name, slug in suite if slug] + [
            catalog_entry("CritPt v2", "/evaluations/critpt-v2"), catalog_entry("GDPval-AA", "/evaluations/gdpval-aa", ())]
    rows = [suite_row(key, weight, name) for key, weight, name, _ in suite]
    outlined = {}
    for row in rows[2:3]:
        cells = row[3]["children"]
        outlined = {f"{0x58 + i:x}": cell for i, cell in enumerate(cells)}
        row[3]["children"] = [f"${'L' * (i != 2)}{0x58 + i:x}" for i in range(len(cells))]
    outlined.update({f"{0x5e + i:x}": row for i, row in enumerate(rows[3:])})
    header = ["$", "tr", None, {"children": [["$", "th", key, {"children": text}] for key, text in (
        ("evaluation", "Evaluation"), ("intelligence-index-weighting", ["Intelligence ", ["$", "br", "br0", {}], " Index"]))]}]
    table = ["$", "tbody", None, {"children": rows[:3] + [f"$L{0x5e + i:x}" for i in range(len(rows[3:]))]}]
    other = ["$", "tbody", None, {"children": [
        ["$", "tr", "gdpval", {"children": [None, ["·"], ["$", "td", "note", None], ["$", "td", "evaluation", {"children": "GDPval-AA"}]]}]]}]
    text = "Included at 10% weighting ✓\n1c:[]"
    return "".join([
        '1:"$Sreact.fragment"\n57:I[8154,["/_next/static/chunks/a.js"],"Tooltip"]\n:HL["/_next/static/a.css","style"]\n',
        f'0:{json.dumps({"f": [["$", "thead", None, {"children": [header]}], "$L1c", other]}, ensure_ascii=False)}\n1c:{json.dumps(table, ensure_ascii=False)}\n',
        f"7a:T{len(text.encode('utf-8')):x},{text}",
        *(f"{key}:{json.dumps(row, ensure_ascii=False)}\n" for key, row in reversed(outlined.items())),
        f'f3:{json.dumps(["$", "$Lf2", None, {"evaluations": [{"shortName": "MATH-500"}, *catalog], "attributes": {"intelligence-index": "Index"}}])}\n'])


def methodology_html(version: str | None = VERSION, suite=SUITE, catalog=None):
    """The whole page; None names no Intelligence Index version at all."""
    named = "" if version is None else f"Artificial Analysis Intelligence Index v{version} incorporates 9 evaluations"
    chunk = json.dumps(methodology_payload(suite, catalog))
    return f"<html><body><p>{named}</p><script>self.__next_f.push([1,{chunk}])</script></body></html>"
