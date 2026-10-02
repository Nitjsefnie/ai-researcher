"""Tests for folding a Playwright V8 dump into the page's line coverage.

The scorer attributes a record only when its ``source`` is the text of the
built page's single inline ``<script>`` block; everything else the browser
compiled is an unattributed record that is never scored. The cases below
pin the extraction (both tags at line start, the UTF-16 length guard), the
V8 range merging on synthetic records, attribution refusal when nothing
matches, and the CLI's two formats and its floor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

from js_coverage import (  # pylint: disable=wrong-import-position  # noqa: E402
    collect_coverage,
    main,
    merge_records,
    page_script,
    render_markdown,
)
from js_lines import code_lines  # noqa: E402  # pylint: disable=wrong-import-position

BODY = (
    "const a = 1;\n"
    "// comment line\n"
    "const b = 2;\n"
)
# The script text as the browser compiled it: the newline that closes
# <script> is part of it, and the last body line carries its own newline.
SCRIPT = "\n" + BODY


def _page(tmp_path, body=BODY):
    (tmp_path / "out").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "frontier-models.html").write_text(
        "<!doctype html>\n<script>\n" + body + "</script>\n",
        encoding="utf-8")


def _record(source=SCRIPT, ranges=None, url="file:///tmp/page.html"):
    return {
        "url": url,
        "source": source,
        "functions": [{
            "functionName": "",
            "isBlockCoverage": True,
            "ranges": ranges if ranges is not None
            else [{"startOffset": 0, "endOffset": len(SCRIPT), "count": 1}],
        }],
    }


def _write_dump(tmp_path, records):
    dump = tmp_path / "js-coverage.json"
    dump.write_text(json.dumps(records), encoding="utf-8")
    return dump


# --- the extractor ---------------------------------------------------------


def test_page_script_extracts_between_line_start_tags(tmp_path):
    _page(tmp_path)
    assert page_script(tmp_path) == SCRIPT


def test_page_script_refuses_a_page_without_a_script_block(tmp_path):
    _page(tmp_path)
    (tmp_path / "out" / "frontier-models.html").write_text(
        "<!doctype html>\n<p>no script</p>\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no inline <script> block"):
        page_script(tmp_path)


def test_page_script_refuses_an_unterminated_block(tmp_path):
    _page(tmp_path)
    (tmp_path / "out" / "frontier-models.html").write_text(
        "<!doctype html>\n<script>\nconst a = 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unterminated"):
        page_script(tmp_path)


def test_page_script_refuses_astral_characters(tmp_path):
    # V8 offsets count UTF-16 code units; one astral character before an
    # uncovered line would map every later offset to the wrong line.
    _page(tmp_path, body='const a = "\U0001F600";\n')
    with pytest.raises(ValueError, match="UTF-16"):
        page_script(tmp_path)


# --- the V8 range merge ------------------------------------------------------


def _merge_record(ranges):
    return {"functions": [{"ranges": ranges}]}


def test_inner_zero_range_overrides_outer_nonzero_range():
    record = _merge_record([
        {"startOffset": 0, "endOffset": 6, "count": 1},
        {"startOffset": 2, "endOffset": 4, "count": 0},
    ])
    assert merge_records([record], 6) == [1, 1, 0, 0, 1, 1]


def test_inner_nonzero_range_overrides_outer_zero_range():
    record = _merge_record([
        {"startOffset": 0, "endOffset": 6, "count": 0},
        {"startOffset": 2, "endOffset": 4, "count": 1},
    ])
    assert merge_records([record], 6) == [0, 0, 1, 1, 0, 0]


def test_ranges_arriving_inner_first_still_resolve_nesting():
    record = _merge_record([
        {"startOffset": 2, "endOffset": 4, "count": 1},
        {"startOffset": 0, "endOffset": 6, "count": 0},
    ])
    assert merge_records([record], 6) == [0, 0, 1, 1, 0, 0]


def test_separate_script_records_add_their_counts():
    first = _merge_record([{"startOffset": 0, "endOffset": 3, "count": 2}])
    second = _merge_record([{"startOffset": 0, "endOffset": 3, "count": 3}])
    assert merge_records([first, second], 3) == [5, 5, 5]


def test_coverage_range_past_source_length_is_an_error():
    record = _merge_record([{"startOffset": 0, "endOffset": 4, "count": 1}])
    with pytest.raises(ValueError,
                       match="outside source length 3"):
        merge_records([record], 3)


# --- attribution ------------------------------------------------------------


def test_collect_scores_the_matching_record_only(tmp_path):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [
        _record(),
        _record(source="something else", url="node:fs"),
        _record(source="", url="[eval]"),
    ])
    report = collect_coverage(dump, tmp_path)
    page = report.files["out/frontier-models.html"]
    assert page.executable_lines == {2, 4}
    assert page.covered_lines == {2, 4}
    assert report.records_seen == 3
    assert report.ignored_other == 2
    assert report.unattributed_records == 2


def test_collect_partial_coverage(tmp_path):
    _page(tmp_path)
    # cover line 2 only: offsets 0..14 end where the comment line begins
    dump = _write_dump(tmp_path, [
        _record(ranges=[
            {"startOffset": 0, "endOffset": 14, "count": 1},
            {"startOffset": 14, "endOffset": len(SCRIPT), "count": 0},
        ]),
    ])
    report = collect_coverage(dump, tmp_path)
    page = report.files["out/frontier-models.html"]
    assert page.covered_lines == {2}


def test_collect_uncovered_page_reports_zero(tmp_path):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [
        _record(ranges=[{"startOffset": 0, "endOffset": len(SCRIPT),
                         "count": 0}]),
    ])
    report = collect_coverage(dump, tmp_path)
    assert report.files["out/frontier-models.html"].covered_lines == set()


def test_collect_merges_several_matching_records_by_summing(tmp_path):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [
        _record(ranges=[{"startOffset": 0, "endOffset": 14, "count": 1}]),
        _record(ranges=[{"startOffset": 0, "endOffset": len(SCRIPT),
                         "count": 7}]),
    ])
    report = collect_coverage(dump, tmp_path)
    assert report.files["out/frontier-models.html"].covered_lines == {2, 4}


def test_collect_refuses_when_no_record_attributed(tmp_path):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [_record(source="unrelated")])
    with pytest.raises(ValueError, match="no coverage record attributed"):
        collect_coverage(dump, tmp_path)


def test_collect_refuses_a_dump_that_is_not_an_array(tmp_path):
    _page(tmp_path)
    dump = _write_dump(tmp_path, {"result": []})
    with pytest.raises(ValueError, match="must be the JSON array"):
        collect_coverage(dump, tmp_path)


# --- the CLI -----------------------------------------------------------------


def test_cli_total_format_is_machine_readable(tmp_path, capsys):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [_record()])
    assert main([str(dump), "--root", str(tmp_path), "--format=total"]) == 0
    assert capsys.readouterr().out == "100.0\n"


def test_cli_renders_the_page_row_and_attribution(tmp_path, capsys):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [
        _record(ranges=[{"startOffset": 0, "endOffset": 14, "count": 1}]),
        _record(source="unrelated", url="node:child_process"),
    ])
    assert main([str(dump), "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        "| Name | Covered | Total | Cover |\n"
        "| :--- | ---: | ---: | ---: |\n"
        "| out/frontier-models.html | 1 | 2 | 50.0% |\n"
        "| **TOTAL** | **1** | **2** | **50.0%** |\n"
        "\n"
        "Unattributed script records: 1 record of 2 seen; only records "
        "whose source equals the page script are scored.\n")


def test_cli_fail_under_above_measured_fails(tmp_path, capsys):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [
        _record(ranges=[{"startOffset": 0, "endOffset": 14, "count": 1}]),
    ])
    code = main([str(dump), "--root", str(tmp_path), "--format=total",
                 "--fail-under", "50.1"])
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == "50.0\n"
    assert "Coverage failure" in captured.err


def test_cli_fail_under_at_or_below_measured_passes(tmp_path, capsys):
    _page(tmp_path)
    dump = _write_dump(tmp_path, [_record()])
    code = main([str(dump), "--root", str(tmp_path), "--format=total",
                 "--fail-under", "100.0"])
    assert code == 0
    assert capsys.readouterr().out == "100.0\n"


def test_render_markdown_is_the_row_and_the_attribution_note():
    _page_view = {
        "out/frontier-models.html": type(
            "File", (), {"executable_lines": {1, 2}, "covered_lines": {1}})(),
    }
    report = type(
        "Report", (),
        {"files": _page_view, "records_seen": 5, "ignored_other": 4})()
    assert render_markdown(report) == (
        "| Name | Covered | Total | Cover |\n"
        "| :--- | ---: | ---: | ---: |\n"
        "| out/frontier-models.html | 1 | 2 | 50.0% |\n"
        "| **TOTAL** | **1** | **2** | **50.0%** |\n"
        "\n"
        "Unattributed script records: 4 records of 5 seen; only records "
        "whose source equals the page script are scored.\n")


# --- the physical-line scanner ----------------------------------------------


def test_comments_never_mark_a_line_executable():
    assert code_lines('a(); // trailing\n/* multi\nline */\nb();\n') == {1, 4}


def test_strings_and_division_on_one_line():
    assert code_lines('const s = "a\\"b"; const d = x / y / z;\n') == {1}


def test_regex_literal_is_not_division():
    assert code_lines('const re = /a[/]b/g; const hit = re.test(s);\n') == {1}


def test_regex_allowed_where_a_statement_paren_closes():
    assert code_lines('if (x) /re/.test(s);\n') == {1}


def test_multiline_template_marks_every_body_line():
    assert code_lines('const t = `one\ntwo ${ x } four\nfive`;\n') == {1, 2, 3}


def test_optional_chaining_and_numbers():
    assert code_lines('const n = a?.b[0]?.c;\nconst e = 1.5e+3;\n') == {1, 2}


def test_crlf_and_unicode_line_ends():
    assert code_lines('a();\r\nb(); c(); d();\n') == {1, 2, 3, 4}


def test_multiline_function_body_marks_its_statement_lines():
    source = 'function f(a) {\n  return a + 1;\n}\nconst v = f(2);\n'
    assert code_lines(source) == {1, 2, 3, 4}


@pytest.mark.parametrize("source", [
    'const s = "unterminated\n',       # string
    'const t = `unterminated\n',       # template
    'const re = /unterminated\n',      # regex
    '/* unterminated\n',               # block comment
    'const \\x = 1;\n',                # escaped identifier
    'const q = { a: 1 } / 2;\n',       # slash after }
])
def test_unterminatable_source_raises(source):
    with pytest.raises(ValueError):
        code_lines(source)


# --- the disputed build's second shape (issue #118) -------------------------------

def _page_root(tmp_path, payload: str):
    """A root carrying a built page whose DATA line is `payload`.

    page_script() extracts from the newline closing <script>, so the
    script text begins with the blank line the fixture writes there --
    the same leading shape the real page has.
    """
    root = tmp_path / "root"
    root.mkdir()
    script = "\n" + payload + "\n" + "let x = 1;\nlet y = 2;\n"
    (root / "out").mkdir()
    (root / "out" / "frontier-models.html").write_text(
        "<script>\n" + script + "</script>\n", encoding="utf-8")
    return root


def _one_range_record(source: str, start: int, end: int, count: int = 1):
    return {"url": "x", "source": source, "functions": [
        {"functionName": "f", "isBlockCoverage": True, "ranges": [
            {"startOffset": start, "endOffset": end, "count": count}]}]}


def test_a_different_one_line_payload_attributes_and_scores(tmp_path):
    # The disputed build (issue #118): a different-length DATA line over the
    # byte-identical code. Its records must attribute and score -- the
    # disputed JS paths run on no other page -- landing on the shared line
    # numbers from line 2 on.
    payload_a = "const DATA = {\"a\": 1};"
    payload_b = "const DATA = {\"a\": 1, \"much\": \"longer payload here\"};"
    root = _page_root(tmp_path, payload_a)
    code = "\nlet x = 1;\nlet y = 2;\n"
    body_a = "\n" + payload_a + code
    body_b = "\n" + payload_b + code
    # offsets of "let y" in each shape
    start_a = 1 + len(payload_a) + len("\nlet x = 1;\n")
    start_b = 1 + len(payload_b) + len("\nlet x = 1;\n")
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps([
        _one_range_record("\n" + body_a, start_a - 1, start_a + 11),
        _one_range_record("\n" + body_b, start_b - 1, start_b + 11),
    ]), encoding="utf-8")
    report = collect_coverage(str(dump), str(root))

    fc = report.files["out/frontier-models.html"]
    assert fc.covered_lines == {4, 5}
    assert report.unattributed_records == 0


def test_a_genuinely_different_script_stays_unattributed(tmp_path):
    # A record whose CODE text differs is not a second shape; attributing it
    # would score lines the page never shipped.
    root = _page_root(tmp_path, "const DATA = {\"a\": 1};")
    other = "const DATA = {\"a\": 1};\nlet x = 1;\nlet DIFFERENT = 2;\n"
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps([_one_range_record(other, 0, len(other))]),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="no coverage record attributed"):
        collect_coverage(str(dump), str(root))
