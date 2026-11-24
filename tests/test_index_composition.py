"""The Intelligence Index composition: read, confirmed, recorded and rendered."""
import contextlib
import decimal
import io
import pathlib
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import capture_gate  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
import fetch_aa_parse  # noqa: E402  # pylint: disable=wrong-import-position
from _methodology import (  # noqa: E402  # pylint: disable=wrong-import-position
    CITED, COMPOSITION, RECORDED, SUITE, VERSION, catalog_entry, methodology_html, methodology_payload)
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
import test_capture_gate  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order
from test_fetch_aa import cached_pages, capture_into, legacy_main  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

EVIDENCE = test_build.route_evidence(1)


def given(**arguments):
    return arguments


def read(suite=SUITE, catalog=None, payload=None):
    return fetch_aa_parse.index_composition(
        methodology_payload(suite, catalog) if payload is None else payload, fetch_aa.METHODOLOGY_URL)


def edited(**changes):
    """The suite with the named fields of one row (by key, `-` as `_`) replaced."""
    return tuple({**dict(zip("kwns", row)), **changes.get(row[0].replace("-", "_"), {})}.values() for row in SUITE)


def test_the_live_shape_reads_in_table_order_with_catalog_slugs_and_the_row_key_fallback():
    assert read() == COMPOSITION
    assert [slug for slug, _, _ in read()][4:8] == [
        "terminalbench-4-1", "terminal-bench-science", "critpt-v2-hard", "omniscience"]


def test_fractional_weights_sum_exactly():
    got = read(edited(aa_briefcase={"w": "14.9%"}, gdp_pdf={"w": "5.1%"}))
    assert [weight for _, weight, _ in got][:3] == [decimal.Decimal("14.9"), 5, decimal.Decimal("5.1")]


def test_a_catalog_entry_outside_the_index_or_repeated_decides_nothing():
    catalog = [catalog_entry(name, f"/evaluations/{slug}") for _, _, name, slug in SUITE if slug]
    outside = catalog_entry("HLE-Diamond", "/evaluations/hle-multichoice", ["private-dataset"])
    assert read(catalog=[outside] + catalog * 2) == COMPOSITION


HALVES = SUITE[:-1] + (("hle-diamond", "5%", "HLE-Diamond", "hle-diamond"),)
FULL = [catalog_entry(name, f"/evaluations/{slug}") for _, _, name, slug in SUITE if slug]
REFUSALS = {
    "no-suite-row": (given(suite=()), "no suite row"),
    "no-catalog": (given(catalog=[]), "no index evaluation"),
    "none-flagged": (given(catalog=[catalog_entry("GDPval-AA", "/evaluations/gdpval-aa", ())]), "no index evaluation"),
    "broken-suite-row": (given(payload=methodology_payload().replace("HLE-Diamond\"}]", "HLE-Diamond\"}", 1)), "sum to 90%"),
    "name-in-parts": (given(suite=edited(critpt_v2_hard={"n": ["CritPt ", "v2"]})), "no single name"),
    "name-a-reference": (given(suite=edited(critpt_v2_hard={"n": "$L99"})), "no single name"),
    "name-blank": (given(suite=edited(critpt_v2_hard={"n": " "})), "no single name"),
    "name-newline": (given(suite=edited(critpt_v2_hard={"n": "CritPt\nv2"})), "no single name"),
    "name-return": (given(suite=edited(critpt_v2_hard={"n": "CritPt\rv2"})), "no single name"),
    "name-surrogate": (given(payload=methodology_payload().replace("(Hard Subset)", "\\ud800")), "no single name"),
    "weight-no-percent": (given(suite=edited(gdp_pdf={"w": "5"})), "weighting"),
    "weight-spaced": (given(suite=edited(gdp_pdf={"w": "5 %"})), "weighting"),
    "weight-in-parts": (given(suite=edited(gdp_pdf={"w": ["5", "%"]})), "weighting"),
    "weight-trailing": (given(suite=edited(gdp_pdf={"w": "5%*"})), "weighting"),
    "weight-negative": (given(suite=edited(gdp_pdf={"w": "-5%"}, aa_briefcase={"w": "25%"})), "weighting"),
    "weight-zero": (given(suite=SUITE + (("extra", "0%", "Extra", None),)), "weighting"),
    "weights-short": (given(suite=edited(gdp_pdf={"w": "4%"})), "sum to 99%"),
    "weights-over": (given(suite=edited(gdp_pdf={"w": "6%"})), "sum to 101%"),
    "duplicate-slug": (given(suite=HALVES + (("other", "5%", "Other", "hle-diamond"),)), "duplicate"),
    "duplicate-name": (given(suite=HALVES[:-1] + (("x-1", "5%", "X", None), ("x-2", "5%", "X", None))), "duplicate"),
    "two-slugs-one-name": (given(catalog=FULL + [catalog_entry("GDP.pdf", "/evaluations/gdp-pdf-2")]), "GDP.pdf"),
    "unflagged-name": (given(catalog=FULL[:-1] + [catalog_entry("HLE-Diamond", "/evaluations/hle-diamond", ())]), "no readable slug"),
    "foreign-href": (given(catalog=FULL + [catalog_entry("CritPt v2 (Hard Subset)", "/models/critpt")]), "no readable slug"),
    "no-row-key": (given(suite=edited(critpt_v2_hard={"k": None})), "no readable slug"),
    "spaced-row-key": (given(suite=edited(critpt_v2_hard={"k": "critpt v2"})), "no readable slug"),
}


@pytest.mark.parametrize("arguments,reason", REFUSALS.values(), ids=REFUSALS)
def test_a_page_whose_every_part_cannot_be_read_is_refused_naming_it(arguments, reason):
    with pytest.raises(SystemExit) as caught:
        read(**arguments)
    assert fetch_aa.METHODOLOGY_URL in str(caught.value) and reason in str(caught.value)


def test_a_stretch_the_parser_cannot_read_is_skipped_to_the_next_row():
    payload = methodology_payload()
    for junk in ("zz:[]\n", "f9:[1\n", "f9:x\n", "f9:o4,\x01\x02\n:N1\n", "f9:\ud800\n"):
        assert read(payload=junk + payload) == read(payload=payload + junk) == COMPOSITION
    assert read(payload=payload + "f9:T9999,cut") == COMPOSITION


def test_a_suite_row_without_an_evaluation_cell_is_refused():
    payload = methodology_payload().replace('"evaluation"', '"renamed"')
    with pytest.raises(SystemExit, match="no single name"):
        read(payload=payload)


def recomposed(**weights):
    """The composition with the named slugs (`-` as `_`) reweighed, or dropped at None; a new slug is added."""
    merged = {slug: (weight, name) for slug, weight, name in COMPOSITION}
    for slug, weight in weights.items():
        merged[slug.replace("_", "-")] = (weight, slug)
    return [(slug, decimal.Decimal(weight), name) for slug, (weight, name) in merged.items() if weight is not None]


SWAP = given(terminalbench_4_1=None, terminalbench_4_0=10)  # the recorded side of the live one-for-one replacement
REBALANCE = given(aa_briefcase=10, gdp_pdf=10)


def confirm(*, recorded=(), slugs: tuple | list | None = tuple(slug for slug, _, _ in COMPOSITION), versions=(None,) * 4, before=VERSION, suite=SUITE, catalog=None, first=None):
    """Confirm the suite's composition over fetched breakdowns of `first` and `slugs`
    (None: a window hour's bare total) against the one recorded under `before`."""
    costs = [1.0 if part is None else {"cost": {"total": 1.0}, "evaluations": [
        {"weightedCostPerTask": 0.1} if slug is None else {"slug": slug, "weightedCostPerTask": 0.1} for slug in part]}
             for part in (first, slugs)]
    fetch_aa.confirm_composition(fetch_aa.Capture(
        [], "host", versions[0], 1, False, fetched=tuple({"slug": "priced", "intelligenceIndexCostPerTask": c} for c in costs),
        composition=tuple(read(suite, catalog)), cited=versions[1:]), (before, list(recorded)) if recorded else None)


SLUGS = [slug for slug, _, _ in COMPOSITION]


@pytest.mark.parametrize("slugs,missing,unexpected", [
    (SLUGS[:-1], "['hle-diamond']", "[]"), (SLUGS + ["scicode"], "[]", "['scicode']"),
    (SLUGS[:-1] + ["critpt"], "['hle-diamond']", "['critpt']"), (SLUGS + [None], "[]", "[None]"),
    ([], str(sorted(SLUGS)), "[]")], ids=["dropped", "added", "renamed", "no-slug", "empty"])
def test_a_fetched_breakdown_off_the_composition_exits_even_when_it_is_the_recorded_one(slugs, missing, unexpected):
    with pytest.raises(SystemExit) as caught:
        confirm(recorded=COMPOSITION, slugs=slugs, versions=(VERSION,) * 4)
    for pair in (given(first=SLUGS, slugs=slugs), given(first=slugs, slugs=SLUGS)):
        with pytest.raises(SystemExit, match="priced: cost breakdown slugs left"):
            confirm(recorded=COMPOSITION, **pair)
    for part in ("priced: cost breakdown slugs left", f"missing {missing}", f"unexpected {unexpected}",
                 fetch_aa.METHODOLOGY_URL):
        assert part in str(caught.value)


@pytest.mark.parametrize("arguments", [
    given(recorded=COMPOSITION), given(recorded=COMPOSITION, slugs=None), given(recorded=COMPOSITION[::-1], slugs=None),
    given(recorded=recomposed(**SWAP)), given(recorded=recomposed(**SWAP), versions=("5.0.1", "5.0", None, "5.0.2")),
    given(recorded=recomposed(**SWAP), before=None), given(recorded=[(f"old-{slug}", *rest) for slug, *rest in COMPOSITION]),
    given(recorded=recomposed(hle_diamond=None, gdp_pdf=None, a=10, b=5)),
    given(recorded=recomposed(**REBALANCE), versions=(VERSION,) * 4, before="5.0"),
    given(recorded=recomposed(**REBALANCE), versions=(VERSION,) * 4),
    given(recorded=recomposed(scicode=5, aa_briefcase=10), versions=(VERSION,) * 4),
    given(recorded=recomposed(gdp_pdf=None, aa_briefcase=20), versions=(VERSION,) * 4),
    given(versions=(VERSION,) * 4)],
    ids=["unchanged", "unchanged-no-breakdown", "reordered", "swap-unnamed", "swap-versions-differ",
         "swap-unnamed-record", "every-slug-swapped", "two-swaps",
         "rebalance", "rebalance-same-version", "dropped", "added", "none-recorded"])
def test_a_confirmed_composition_passes(arguments):
    confirm(**arguments)


@pytest.mark.parametrize("versions", [(None,) * 4, (VERSION,) * 4])
def test_a_replacement_whose_row_key_is_the_old_slug_needs_a_fetched_breakdown_of_its_own(versions):
    # AA's catalog gives the row a new slug; the row key and a lagging detail corpus keep the old one.
    replaced = FULL[:-1] + [catalog_entry("HLE-Diamond", "/evaluations/hle-diamond-2")]
    with pytest.raises(SystemExit, match="slugs left.*missing .'hle-diamond-2'.*unexpected .'hle-diamond'"):
        confirm(recorded=COMPOSITION, catalog=replaced, versions=versions)
    with pytest.raises(SystemExit, match="no fetched cost breakdown"):
        confirm(recorded=COMPOSITION, catalog=replaced, slugs=None, versions=versions)
    confirm(recorded=COMPOSITION, catalog=replaced, slugs=SLUGS[:-1] + ["hle-diamond-2"])


@pytest.mark.parametrize("recorded", [
    recomposed(**REBALANCE), recomposed(aa_briefcase=5, gdp_pdf=15), recomposed(scicode=5, aa_briefcase=10),
    recomposed(gdp_pdf=None, aa_briefcase=20), recomposed(hle_diamond=None, a=5, gdp_pdf=10),
    recomposed(hle_diamond=None, a=10, aa_briefcase=5, gdp_pdf=15),
    recomposed(hle_diamond=None, a=10, b=5, aa_briefcase=10), recomposed(hle_diamond=None, a=5, b=5),
    recomposed(hle_diamond=None, gdp_pdf=None, a=8, b=7),
    recomposed(hle_diamond=None, critpt_v2_hard=None, gdp_pdf=None, a=10, b=5, c=5, d=5), ()],
    ids=["rebalance", "permuted", "dropped", "added", "swap-at-another-weight", "swap-and-permuted",
         "swap-and-dropped", "two-for-one", "two-at-other-weights", "four-for-three", "none-recorded"])
def test_any_other_change_needs_every_page_to_name_one_version(recorded):
    for at, page in enumerate(("methodology page", "first leaderboard look", "model detail page", "second leaderboard look")):
        for other, said in ((None, "no version"), ("5.0", "v5.0"), ("5.0.10", "v5.0.10")):
            versions: list[str | None] = [VERSION] * 4
            versions[at] = other
            with pytest.raises(SystemExit) as caught:
                confirm(recorded=recorded, versions=tuple(versions))
            assert f"{page} {said}" in str(caught.value) and fetch_aa.METHODOLOGY_URL in str(caught.value)
    with pytest.raises(SystemExit):
        confirm(recorded=recorded)


@pytest.mark.parametrize("recorded", [recomposed(**SWAP), recomposed(**REBALANCE), ()],
                         ids=["swap", "rebalance", "none-recorded"])
def test_a_changed_composition_no_breakdown_confirms_exits(recorded):
    with pytest.raises(SystemExit, match="no fetched cost breakdown"):
        confirm(recorded=recorded, slugs=None, versions=(VERSION,) * 4)


def cite(page, version):
    """The cached page with its one version citation replaced, or removed at None."""
    text = page.read_text(encoding="utf-8")
    assert text.count(CITED) == 1
    page.write_text(text.replace(CITED, CITED.replace(VERSION, version) if version else ""), encoding="utf-8")


def run_hour(root, *, recorded=None, html: str | None = VERSION, detail: str | None = VERSION, args=(), **methodology):
    """main() over the cached pages, the evidence of `recorded` beside OUT -> stdout."""
    flags = cached_pages(root, methodology_html(**methodology))
    cite(root / "html", html)
    cite(root / "detail-html", detail)
    if recorded is not None:
        (root / build.ROUTE_EVIDENCE_NAME).write_text(EVIDENCE + recorded, encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out), capture_into(root, *flags, *args):
        legacy_main()
    return out.getvalue()


OLD_SWAP = RECORDED.replace("terminalbench-4-1", "terminalbench-4-0").replace("Terminal-Bench 4.1", "Terminal-Bench 4.0")
OLD_WEIGHTS = RECORDED.replace("gdp-pdf 5%", "gdp-pdf 10%").replace("aa-briefcase 15%", "aa-briefcase 10%")


@pytest.mark.parametrize("html,detail", [(None, None), ("5.0.1", "5.0.1")])
@pytest.mark.parametrize("args", [(), ("--cross-run-lookback",)])
def test_a_one_for_one_replacement_is_captured_and_recorded(tmp_path, html, detail, args):
    assert "v5.0.2 cost breakdown" in run_hour(tmp_path, recorded=OLD_SWAP, html=html, detail=detail, args=args)
    assert (tmp_path / build.ROUTE_EVIDENCE_NAME).read_text(encoding="utf-8") == EVIDENCE + RECORDED


def test_a_rebalance_is_captured_only_when_every_page_names_its_version(tmp_path):
    for html, detail in (("5.0", VERSION), (VERSION, None)):
        with pytest.raises(SystemExit, match="re-read"):
            run_hour(tmp_path, recorded=OLD_WEIGHTS, html=html, detail=detail)
        assert not (tmp_path / "aa-raw-models.json").exists()
        assert (tmp_path / build.ROUTE_EVIDENCE_NAME).read_text(encoding="utf-8") == EVIDENCE + OLD_WEIGHTS
    run_hour(tmp_path, recorded=OLD_WEIGHTS)
    assert (tmp_path / build.ROUTE_EVIDENCE_NAME).read_text(encoding="utf-8") == EVIDENCE + RECORDED


def test_each_look_s_own_version_is_read(tmp_path):
    flags = cached_pages(tmp_path, methodology_html())
    with capture_into(tmp_path, sleep=lambda _seconds: cite(tmp_path / "html", "5.0.1")):
        captured = fetch_aa.capture(flags[1], flags[3], flags[7])
    assert captured.cited == (VERSION, VERSION, "5.0.1")
    assert list(captured.composition) == COMPOSITION


def test_a_page_without_flight_chunks_exits_naming_it(tmp_path):
    with pytest.raises(SystemExit, match=fetch_aa.METHODOLOGY_URL):
        fetch_aa.flight_payload("<html>nothing here</html>", fetch_aa.METHODOLOGY_URL)
    (tmp_path / "bare").write_text(CITED, encoding="utf-8")
    with pytest.raises(SystemExit, match=fetch_aa.METHODOLOGY_URL):
        fetch_aa.capture(None, None, str(tmp_path / "bare"))


def test_the_recorded_composition_round_trips(tmp_path):
    path = tmp_path / build.ROUTE_EVIDENCE_NAME
    odd = [("a.b_c", decimal.Decimal("12.5"), "  50% off <b>&__DATA__ ✓"), ("d", decimal.Decimal("1E-7"), "$x")]
    for version, composition in ((VERSION, COMPOSITION), (None, COMPOSITION), ("6", odd)):
        path.write_text(build.render_route_evidence(3, True, False, version, composition), encoding="utf-8")
        assert build.read_index_composition(tmp_path) == (version, composition)
        assert build.read_route_evidence(tmp_path) == (3, {"detail"})
    assert build.render_route_evidence(1, False, False, VERSION, COMPOSITION) == EVIDENCE + RECORDED
    assert build.render_route_evidence(1, False, False, None, COMPOSITION) == EVIDENCE + RECORDED.replace(VERSION, "—")
    path.write_bytes((EVIDENCE + RECORDED).replace("\n", "\r\n").encode("utf-8"))
    assert build.read_index_composition(tmp_path) == (VERSION, COMPOSITION)
    assert build.read_route_evidence(tmp_path) == (1, set())


def test_evidence_without_a_composition_records_none(tmp_path):
    path = tmp_path / build.ROUTE_EVIDENCE_NAME
    assert build.read_index_composition(tmp_path) is None
    path.write_text(EVIDENCE, encoding="utf-8")
    assert build.read_index_composition(tmp_path) is None
    assert build.read_route_evidence(tmp_path) == (1, set())
    good = EVIDENCE + RECORDED
    for bad in (good + "\n", good[:-1], EVIDENCE + f"index version: {VERSION}\n", RECORDED, good.replace("index version: ", ""),
                EVIDENCE + RECORDED.partition("\n")[2], good.replace(VERSION, "v5.0.2"), good.replace("5%", "5", 1),
                good.replace("5%", "-5%", 1), good.replace("gdp-pdf", "gdp pdf"), good.replace(" GDP.pdf", ""),
                good.replace("in-run generations: 1", "in-run generations: 0")):
        path.write_text(bad, encoding="utf-8")
        assert build.read_index_composition(tmp_path) is None and build.read_route_evidence(tmp_path) is None


def built_stats(evidence):
    harness = test_build.EmptyAxisGuardTests()
    with harness.capture([test_build.model_fixture()], [test_build.agent_fixture()]) as output:
        if evidence is not None:
            (output.parent / build.ROUTE_EVIDENCE_NAME).write_text(evidence, encoding="utf-8")
        harness.run_build()
        page = output.read_text(encoding="utf-8")
        return page, harness.payload_of(output)["stats"]


def test_the_page_names_the_recorded_composition():
    names = ", ".join(name for _, _, name in COMPOSITION)
    for evidence, sentence in (
            (EVIDENCE + RECORDED, f" v{VERSION} comprises {names}"),
            (EVIDENCE + RECORDED.replace(VERSION, "—"), f" comprises {names}"),
            (EVIDENCE, " comprises —"), (None, " comprises —")):
        assert built_stats(evidence)[1]["evals"] == sentence
    page, stats = built_stats(EVIDENCE + RECORDED.replace("GDP.pdf", "</script><b>__CAPTURED__"))
    assert "</script><b>__CAPTURED__" in stats["evals"] and "</script><b>" not in page


def test_a_fresh_evaluation_name_moves_the_built_page_and_the_counts_do_not():
    marker = (EVIDENCE + RECORDED).encode("utf-8")
    for head, fresh, changed in (
            (marker, marker.replace(b"Terminal-Bench 4.1", b"Terminal-Bench 4.2"), "true\n"),
            (marker, marker.replace(b"5.0.2", b"5.0.3"), "true\n"),
            (marker, marker.replace(b"generations: 1", b"generations: 2"), "false\n"),
            (marker, marker.replace(b"gdp-pdf 5%", b"gdp-pdf 6%"), "false\n")):
        with test_capture_gate.head_serving(test_capture_gate.FIXTURE_MODELS, test_capture_gate.FIXTURE_AGENTS), \
                mock.patch.object(capture_gate, "read_head_window_marker", return_value=head), \
                mock.patch.object(capture_gate, "read_fresh_window_marker", return_value=fresh):
            assert test_capture_gate.run_gate() == (0, changed)
