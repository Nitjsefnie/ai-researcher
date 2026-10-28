"""Issue #303: withheld detail enrichment survives the cross-run look-back."""

import copy
import json
import pathlib
import sys
import unittest

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
import capture_gate  # noqa: E402  # pylint: disable=wrong-import-position
import test_fetch_aa as fetch_cases  # noqa: E402  # pylint: disable=wrong-import-position
from test_fetch_aa import detail_record  # noqa: E402  # pylint: disable=wrong-import-position
from test_capture_gate import FIXTURE_AGENTS, head_serving  # noqa: E402  # pylint: disable=wrong-import-position
from test_fetch_aa_membership import capture_pages, detail_record as membership_detail_record, leaderboard, with_gdpval  # noqa: E402  # pylint: disable=wrong-import-position
import build  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order


def rich_detail():
    """The existing route fixture with the detail-only time and size fields."""
    return dict(membership_detail_record(), sizeClass="medium",
                intelligenceIndexTimePerTask=12, intelligenceIndexCost=123)


def previous_capture():
    return build.merge_captures(leaderboard(), [rich_detail()])


def test_no_variant_three_generation_corner_restores_page_fields(tmp_path, monkeypatch):
    previous = previous_capture()
    first, second = leaderboard(), leaderboard()
    first[1]["shortName"], second[1]["shortName"] = "First", "Second"
    detail = dict(rich_detail(), shortName="Third")
    without = capture_pages(tmp_path, monkeypatch, first, second, [detail])
    captured = capture_pages(tmp_path, monkeypatch, first, second, [detail], previous)
    current = next(r for r in captured.models if r["slug"] == "current")

    assert "parameters" not in without.models[0]
    assert not captured.disputed
    assert captured.generations == 3
    assert all("genVariants" not in r for r in captured.models)
    assert current["parameters"] == 27
    assert current["sizeClass"] == "medium"
    assert current["licenseName"] == "Fixture licence"
    assert current["releaseDate"] == "2026-01-01"
    assert current["intelligenceIndexTimePerTask"] == 12
    assert current["intelligenceIndexCost"] == 123
    assert build.build_rows(captured.models) == build.build_rows(previous)
    assert current["carriedDetailFills"] == sorted([
        "creator", "parameters", "sizeClass", "licenseName", "releaseDate",
        "intelligenceIndexTimePerTask", "intelligenceIndexCost",
        "intelligenceIndexCostPerTask"])
    assert_same_pages(previous, captured.models)


def assert_same_pages(previous, current):
    """Compare actual builds, with only raw-byte provenance masked away; both
    sides carry the same GDPval-AA pair so every axis plots."""
    old = (json.dumps(with_gdpval(previous)).encode("utf-8"), FIXTURE_AGENTS)
    fresh = (json.dumps(with_gdpval(current)).encode("utf-8"), FIXTURE_AGENTS)
    with head_serving(*old):
        old_page, new_page = capture_gate.build_page_pair(old, fresh)
    assert capture_gate.mask_digest(old_page) == capture_gate.mask_digest(new_page)


@pytest.mark.parametrize("second_total", [0.75, 1.5])
def test_real_price_conflicts_remain_paired(tmp_path, monkeypatch, second_total):
    first, second = leaderboard(), leaderboard()
    second[1].update(price1mInputTokens=2, price1mOutputTokens=6,
                     intelligenceIndexCostPerTask=second_total)
    prior = rich_detail()
    expected_fills = {key: prior[key] for key in (
        "creator", "intelligenceIndexCost", "intelligenceIndexTimePerTask",
        "licenseName", "parameters", "releaseDate", "sizeClass")}
    cost_key = "intelligenceIndexCostPerTask"
    if second_total == 0.75:
        expected_fills[cost_key] = prior[cost_key]
        expected_cost = prior[cost_key]
    else:
        expected_cost = 1.5
    detail = dict(rich_detail(), intelligenceIndex=53)
    support = membership_detail_record("retired")
    without = capture_pages(tmp_path, monkeypatch, first, second, [detail, support])
    captured = capture_pages(tmp_path, monkeypatch, first, second,
                             [detail, support], previous_capture() + [support])
    current = next(r for r in captured.models if r["slug"] == "current")
    baseline = next(r for r in without.models if r["slug"] == "current")

    assert captured.disputed
    assert captured.generations == 3
    assert current["genVariants"] == baseline["genVariants"]
    assert sorted(v["pin"] for v in current["genVariants"]) == [1, 2]
    assert sorted(v["pout"] for v in current["genVariants"]) == [3, 6]
    assert sorted(v["cost"] for v in current["genVariants"]) == [0.75, second_total]
    assert current[cost_key] == expected_cost
    assert current["carriedDetailFills"] == sorted(expected_fills)
    assert build.cost_per_task(current) == second_total
    for field, expected in expected_fills.items():
        assert current[field] == expected
    row = build.build_rows([current])[0]
    for field in ("pin", "pout"):
        values = build.disputed_field_values(row, field)
        assert values is not None and len(values) == 2
    if second_total != 0.75:
        values = build.disputed_field_values(row, "cost")
        assert values is not None and len(values) == 2
    _, table = build.render_static_tbodies([row])
    pairs = [("$1 / $2", "$2 / $1"), ("$3 / $6", "$6 / $3")]
    if second_total != 0.75:
        pairs.append(("$0.750 / $1.50", "$1.50 / $0.750"))
    for pair in pairs:
        assert any(f'<td class="n dispute">{text}</td>' in table for text in pair)
    # Restored cells produce the same page as today's look variants plus
    # these cells supplied by AA, without changing the paired red cells.
    restored = copy.deepcopy(without.models)
    target = next(r for r in restored if r["slug"] == "current")
    for field, expected in expected_fills.items():
        target[field] = expected
    assert_same_pages(restored, captured.models)


@pytest.mark.parametrize("field,value", [
    ("parameters", 27), ("sizeClass", "medium"), ("licenseName", "MIT"),
    ("releaseDate", "2026-01-01"), ("intelligenceIndexTimePerTask", 12),
    ("intelligenceIndexCost", 123),
])
def test_detail_keys_fill_only_absence(field, value):
    previous = [{"slug": "a", field: value}]
    current = [{"slug": "a"}]
    got = fetch_aa.carry_detail_fills(current, previous, {"slug"})
    assert got == [{"slug": "a", field: value, "carriedDetailFills": [field]}]
    for served in (None, "$undefined", "", 0, "Fresh"):
        current = [{"slug": "a", field: served}]
        assert fetch_aa.carry_detail_fills(current, previous, {"slug"}) == current
    current = [{"slug": "a"}]
    assert fetch_aa.carry_detail_fills(current, [{"slug": "a"}], {"slug"}) == current


def test_leaderboard_universe_absence_stays_absent():
    current = [{"slug": "a"}]
    previous = [{"slug": "a", "contextWindowTokens": 100000,
                 "medianOutputTokensPerSecond": 100,
                 "intelligenceIndexCostPerTask": 0.75}]
    universe = set(previous[0])
    assert fetch_aa.carry_detail_fills(current, previous, universe) == current


@pytest.mark.parametrize("total,restored", [(0.75, True), (1.5, False)])
@pytest.mark.parametrize("nested", [False, True])
def test_carried_breakdown_uses_the_current_total_guard(total, restored, nested):
    cost = "intelligenceIndexCostPerTask"
    current = [{"slug": "a", cost: {"cost": {"total": total}} if nested else total}]
    previous = [dict(membership_detail_record("a"))]
    before = copy.deepcopy((current, previous))
    got = fetch_aa.carry_detail_fills(current, previous, set(previous[0]))[0]
    assert build.cost_per_task(got) == total
    assert isinstance(got[cost], dict) == restored
    assert got.get("carriedDetailFills") == ([cost] if restored else None)
    if restored:
        assert build.breakdown_matches_total(got[cost])
    else:
        assert got[cost] == total
    assert (current, previous) == before


def test_synthetic_fields_are_never_carried_or_overwritten():
    previous = [{"slug": "a", "genVariants": [{"ii": 50}, {}],
                 "crossRunMerged": True, "carriedDetailFills": ["parameters"]}]
    current = [{"slug": "a"}]
    assert fetch_aa.carry_detail_fills(current, previous, {"slug"}) == current
    current = [{"slug": "a", "genVariants": [{"ii": 60}],
                "crossRunMerged": False, "carriedDetailFills": ["licenseName"]}]
    assert fetch_aa.carry_detail_fills(current, previous, {"slug"}) == current


def test_only_a_matching_string_slug_can_receive_fills():
    current = [{"slug": "new"}, {"slug": None}, {"slug": 3}, {}]
    previous = [{"slug": "old", "parameters": 27},
                {"slug": None, "parameters": 27}, {"parameters": 27}]
    assert fetch_aa.carry_detail_fills(current, previous, {"slug"}) == current
    assert fetch_aa.carry_detail_fills(current, [], {"slug"}) == current


def test_marker_is_outside_generation_universe_variants_and_held_fields():
    ordinary = previous_capture()
    marked = copy.deepcopy(ordinary)
    marked[1]["carriedDetailFills"] = ["parameters"]
    universe = fetch_aa.leaderboard_universe([ordinary, marked])
    assert "carriedDetailFills" not in universe
    # Even an explicitly supplied field universe cannot fingerprint the marker.
    explicit = universe | {"carriedDetailFills"}
    assert fetch_aa.generation_key(marked, explicit) == fetch_aa.generation_key(
        ordinary, explicit)
    assert fetch_aa.revisit_key(marked) == fetch_aa.revisit_key(ordinary)
    assert fetch_aa.variant_fields(marked[1]) == fetch_aa.variant_fields(ordinary[1])
    assert fetch_aa.held_records(marked) == fetch_aa.held_records(ordinary)
    # A later presence flip also ranks the old corpus without the marker.
    first, _ = fetch_aa.cross_run_presence_merge(ordinary[:1], ordinary, [ordinary[:1]])
    second, _ = fetch_aa.cross_run_presence_merge(ordinary[:1], marked, [ordinary[:1]])
    assert json.dumps(first) == json.dumps(second)


def test_current_detail_wins_and_no_lookback_remains_unchanged(tmp_path, monkeypatch):
    previous = previous_capture()
    detail = dict(rich_detail(), parameters=72, intelligenceIndexTimePerTask=20)
    without = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(), [detail])
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(),
                             [detail], previous)
    assert json.dumps(captured.models) == json.dumps(without.models)
    assert captured.models[1]["parameters"] == 72
    assert all("carriedDetailFills" not in r for r in captured.models)
    expected = build.merge_captures(leaderboard(), [detail])
    assert json.dumps(without.models) == json.dumps(expected)


@pytest.mark.parametrize("held", [False, True])
def test_fill_runs_after_decisions_without_mutating_their_corpora(
        tmp_path, monkeypatch, held):
    previous = previous_capture()
    previous[1]["carriedDetailFills"] = ["parameters"]
    state = {"remembered": [fetch_aa.revisit_key(previous)],
             "last": fetch_aa.revisit_key(previous), "held": None}
    detail = {k: v for k, v in rich_detail().items() if k != "parameters"}
    if held:
        sparse = build.merge_captures(leaderboard(), [detail])
        other = copy.deepcopy(sparse)
        other[1]["intelligenceIndex"] = 52
        state["remembered"].append(fetch_aa.revisit_key(other))
        state["held"] = {"since": fetch_aa._today().isoformat(), "generations": {  # pylint: disable=protected-access
            fetch_aa.revisit_key(sparse): fetch_aa.held_records(sparse),
            fetch_aa.revisit_key(other): fetch_aa.held_records(other)}}
    before_state = copy.deepcopy(state)
    observed = []
    presence = fetch_aa.cross_run_presence_merge
    revisit = fetch_aa.revisit_merge

    def watch_presence(models, prev, corpora):
        observed.append(("presence", models, corpora, copy.deepcopy((models, corpora))))
        return presence(models, prev, corpora)

    def watch_revisit(models, prev, corpora, tracking):
        observed.append(("revisit", models, corpora, copy.deepcopy((models, corpora))))
        return revisit(models, prev, corpora, tracking)

    monkeypatch.setattr(fetch_aa, "cross_run_presence_merge", watch_presence)
    monkeypatch.setattr(fetch_aa, "revisit_merge", watch_revisit)
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(),
                             [detail], previous, state)
    assert next(r for r in captured.models if r["slug"] == "current")["parameters"] == 27
    assert captured.revisit_action == ("held" if held else "ordinary")
    assert state == before_state
    assert [name for name, *_ in observed] == (
        ["presence", "revisit", "presence"] if held else ["presence", "revisit"])
    for _, models, corpora, before in observed:
        assert (models, corpora) == before
        assert all("parameters" not in r for r in models)
        assert all("carriedDetailFills" not in r for corpus in corpora for r in corpus)


def test_historical_parameter_time_and_frontier_loss_is_restored():
    # GLM-5.3-Flash's recorded projection, 12b3827 -> da86f07. Keep both
    # sides inline so CI needs neither historical git objects nor AA access.
    previous = {"slug": "glm-5-3-flash", "name": "GLM-5.3-Flash",
                "intelligenceIndex": 41.807466113455,
                "intelligenceIndexCostPerTask": {
                    "cost": {"total": 0.2835948232103717},
                    "evaluations": [
                        {"slug": "aa-briefcase", "weightedCostPerTask": 0.14759783137736707},
                        {"slug": "gdpval-aa", "weightedCostPerTask": 0.0335808784225709},
                        {"slug": "automationbench-aa", "weightedCostPerTask": 0.0016171765955884324},
                        {"slug": "terminalbench-4-0", "weightedCostPerTask": 0.08891509918482425},
                        {"slug": "scicode", "weightedCostPerTask": 0.0013985710069444445},
                        {"slug": "humanitys-last-exam", "weightedCostPerTask": 0.002165517108433735},
                        {"slug": "gdp-pdf", "weightedCostPerTask": 0.0031873035500000002},
                        {"slug": "critpt", "weightedCostPerTask": 0.004199942857142857},
                        {"slug": "omniscience", "weightedCostPerTask": 8.973728249999998e-05},
                        {"slug": "artificial-analysis-long-context-reasoning", "weightedCostPerTask": 0.0008427658249999999}]},
                "price1mInputTokens": 0.15, "price1mOutputTokens": 0.5,
                "contextWindowTokens": 1000000, "parameters": 320,
                "sizeClass": "large", "licenseName": "MIT",
                "releaseDate": "2026-08-26",
                "intelligenceIndexTimePerTask": 682.013767232941}
    degraded = {"slug": "glm-5-3-flash", "name": "GLM-5.3-Flash",
                "intelligenceIndex": 41.807466113455,
                "intelligenceIndexCostPerTask": 0.2835948232103717,
                "price1mInputTokens": 0.15, "price1mOutputTokens": 0.5,
                "contextWindowTokens": 1000000}
    assert build.metric_of(build.build_rows([degraded])[0], "parameters") is None
    restored = fetch_aa.carry_detail_fills([degraded], [previous], set(degraded))
    assert {k: v for k, v in restored[0].items() if k != "carriedDetailFills"} == previous
    assert build.build_rows(restored) == build.build_rows([previous])
    assert [r["name"] for r in build.undominated(
        build.build_rows(restored), "parameters")] == ["GLM-5.3-Flash"]
    assert_same_pages([previous], restored)


class CarriedBreakdownSlugTests(unittest.TestCase):
    """--cross-run-lookback: the slug check judges this run's fetch only."""
    DETAIL_URL = fetch_cases.CrossRunLookbackFlagTests.DETAIL_URL
    run_main = fetch_cases.CrossRunLookbackFlagTests.run_main

    def test_a_record_carried_from_the_previous_capture_keeps_its_old_breakdown(self):
        # The previous capture priced a model under an older index version,
        # and this fetch no longer serves it: the presence layer merges it
        # back with that version's breakdown. The slug check judges only
        # what this run fetched, so the carried record cannot red the hour.
        host = {"slug": "detail-host-model",
                "intelligenceIndexCostPerTask": "$undefined"}
        departed = {"slug": "departed-model", "intelligenceIndex": 40,
                    "intelligenceIndexCostPerTask": {
                        "cost": {"total": 1.0}, "evaluations": [
                            {"slug": "scicode", "weightedCostPerTask": 0.6},
                            {"slug": "humanitys-last-exam", "weightedCostPerTask": 0.4}]}}
        prev = json.dumps([host, detail_record(), departed], indent=1)

        _stdout, out_text, exit_exc = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"], prev_text=prev)

        self.assertIsNone(exit_exc)
        carried = next(m for m in json.loads(out_text) if m["slug"] == "departed-model")
        self.assertTrue(carried["crossRunMerged"])
        self.assertEqual(carried["intelligenceIndexCostPerTask"],
                         departed["intelligenceIndexCostPerTask"])

    def test_a_fetched_breakdown_off_the_pinned_slugs_still_exits(self):
        stale = {"cost": {"total": 0.75}, "evaluations": [
            {"slug": "scicode", "weightedCostPerTask": 0.75}]}

        prev = json.dumps([{"slug": "detail-host-model",
                            "intelligenceIndexCostPerTask": "$undefined"},
                           detail_record()], indent=1)

        _stdout, out_text, exit_exc = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"], prev_text=prev,
            detail_overrides={"intelligenceIndexCostPerTask": stale})

        self.assertIsNotNone(exit_exc)
        self.assertIn("fixture-model: cost breakdown slugs left", str(exit_exc))
        self.assertEqual(out_text, prev)

    def test_a_detail_only_breakdown_off_the_pinned_slugs_still_exits(self):
        # A model only the detail route lists is part of this run's fetch.
        stale = {"slug": "detail-only-model", "intelligenceIndex": 40,
                 "intelligenceIndexCostPerTask": {"cost": {"total": 0.75}, "evaluations": [
                     {"slug": "scicode", "weightedCostPerTask": 0.75}]}}
        prev = json.dumps([{"slug": "detail-host-model",
                            "intelligenceIndexCostPerTask": "$undefined"},
                           detail_record()], indent=1)

        _stdout, out_text, exit_exc = self.run_main(
            ["fetch_aa.py", "--cross-run-lookback"], prev_text=prev, detail_extra=[stale])

        self.assertIn("detail-only-model: cost breakdown slugs left", str(exit_exc))
        self.assertEqual(out_text, prev)


class TestGenerationRevisit(unittest.TestCase):
    root: pathlib.Path
    output: pathlib.Path
    state_path: pathlib.Path
    setUp = fetch_cases.TestGenerationRevisit.setUp
    run_hour = fetch_cases.TestGenerationRevisit.run_hour
    state = fetch_cases.TestGenerationRevisit.state
    establish_hold = fetch_cases.TestGenerationRevisit.establish_hold

    def test_in_run_disputes_preserve_state_and_render_held_only_for_members(self):
        cost_key = "intelligenceIndexCostPerTask"
        expected_cost = detail_record()[cost_key]
        held, _ = self.establish_hold()
        frozen = self.state_path.read_bytes()
        for first, second in [(40, 50), (50, 40)]:
            models, _ = self.run_hour(first, second=second)
            self.assertEqual(build.build_rows(models), build.build_rows(held))
            self.assertEqual(self.state_path.read_bytes(), frozen)
        models, _ = self.run_hour(40, second=60)
        self.assertEqual(self.state_path.read_bytes(), frozen)
        self.run_hour(40, second=60, enabled=False)
        without_lookback = json.loads(self.output.read_text())
        # The final look-back can restore a missing plain breakdown, while
        # every in-run variant and the winning total stay exactly the same.
        self.assertEqual(len(without_lookback), len(models))
        for plain, enriched in zip(without_lookback, models):
            ignored = {"intelligenceIndexCostPerTask", "carriedDetailFills"}
            self.assertEqual({k: v for k, v in plain.items() if k not in ignored},
                             {k: v for k, v in enriched.items() if k not in ignored})
            self.assertEqual(build.cost_per_task(plain), build.cost_per_task(enriched))
            if enriched["slug"] == "fixture-model":
                self.assertEqual(enriched[cost_key], expected_cost)
                self.assertEqual(enriched["carriedDetailFills"], [cost_key])
            else:
                self.assertEqual(enriched[cost_key], plain[cost_key])
                self.assertNotIn("carriedDetailFills", enriched)


class TestGenerationRevisitSpeeds(unittest.TestCase):
    def setUp(self):
        self.harness = TestGenerationRevisit()
        self.harness.setUp()
        self.addCleanup(self.harness.doCleanups)

    # The canonical generation (the lower generation_key) is ii 50's for
    # these looks, so `first` -- the canonical side -- runs at ii 50.
    FIRST, SECOND = 50, 40

    def assert_held_speeds(self, first, second):
        rendered = {"medianOutputTokensPerSecond", "intelligenceIndexTimePerTask"}
        unused: dict = {key: 777 for key in fetch_aa.NEVER_RED_FIELDS - rendered}
        self.harness.run_hour(self.FIRST, **first, **unused)
        self.harness.run_hour(self.SECOND, **second, **unused)
        models, _ = self.harness.run_hour(self.FIRST, **first, **unused)
        state_bytes = self.harness.state_path.read_bytes()
        rows = build.build_rows(models)
        self.assertEqual(rows[0]["tps"], first.get("medianOutputTokensPerSecond"))
        self.assertEqual(rows[0]["secs"], first.get("intelligenceIndexTimePerTask"))
        for ii, speed in [(self.FIRST, first), (self.SECOND, second)] * 2:
            current, _ = self.harness.run_hour(ii, **speed, **unused)
            self.assertEqual(build.build_rows(current), rows)
            self.assertEqual(self.harness.state_path.read_bytes(), state_bytes)
        for corpus in self.harness.state()["held"]["generations"].values():
            record = next(m for m in corpus if m["slug"] == "fixture-model")
            # Before hold entry, an ordinary hour carries missing detail
            # speeds from its predecessor; the hold freezes that result.
            expected = first if record["intelligenceIndex"] == self.FIRST else {**first, **second}
            self.assertEqual({k: v for k, v in record.items()
                              if k in fetch_aa.NEVER_RED_FIELDS}, expected)
        captured = fetch_aa.capture(str(self.harness.root / "base.html"),
                                    str(self.harness.root / "detail.html"),
                                    str(self.harness.root / "methodology.html"),
                                    current, self.harness.state())
        self.assertEqual(captured.generations, 1)
        self.assertTrue(captured.disputed)

    def test_held_speeds_above_tolerance_are_frozen_per_generation(self):
        self.assert_held_speeds(
            {"medianOutputTokensPerSecond": 150, "intelligenceIndexTimePerTask": 150},
            {"medianOutputTokensPerSecond": 100, "intelligenceIndexTimePerTask": 100})

    def test_held_speeds_missing_from_canonical_generation_stay_absent(self):
        self.assert_held_speeds(
            {}, {"medianOutputTokensPerSecond": 100, "intelligenceIndexTimePerTask": 100})

    def test_held_speeds_missing_from_other_generation_stay_canonical(self):
        self.assert_held_speeds(
            {"medianOutputTokensPerSecond": 150, "intelligenceIndexTimePerTask": 150}, {})

    def test_unheld_speed_movement_above_tolerance_still_publishes(self):
        before, _ = self.harness.run_hour(
            40, medianOutputTokensPerSecond=150, intelligenceIndexTimePerTask=150)
        state_bytes = self.harness.state_path.read_bytes()
        after, _ = self.harness.run_hour(
            40, medianOutputTokensPerSecond=100, intelligenceIndexTimePerTask=100)
        self.assertIsNone(self.harness.state()["held"])
        self.assertEqual(self.harness.state_path.read_bytes(), state_bytes)
        self.assertNotEqual(before, after)
        row = build.build_rows(after)[0]
        self.assertEqual((row["tps"], row["secs"]), (100, 100))
