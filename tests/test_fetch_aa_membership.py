"""Issue #266: retain AA's detail-only models through every capture path."""

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
import build  # noqa: E402  # pylint: disable=wrong-import-position
from test_build import v5_evaluations  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order


@pytest.mark.parametrize("rich_key", ["initialModels", "models"])
def test_initial_models_competes_with_models_by_richness_not_length(rich_key):
    rich = detail_record()
    index = [{"slug": f"m{i}", "name": f"M{i}", "releaseSlug": f"m{i}"}
             for i in range(5)]
    payload = json.dumps([{rich_key: [rich]}, {"models": index}], separators=(",", ":"))
    assert fetch_aa.richest_models_array(payload) == [rich]


def test_no_scored_array_names_the_observed_arrays_and_fields():
    index = {"slug": "a", "name": "A", "releaseSlug": "a"}
    payload = json.dumps({"models": [index], "initialModels": []}, separators=(",", ":"))
    with pytest.raises(SystemExit) as caught:
        fetch_aa.richest_models_array(payload)
    message = str(caught.value)
    assert "arrays: initialModels, models" in message
    assert "3 fields (name, releaseSlug, slug)" in message
    for expected in ("expected", "intelligenceIndex", "intelligenceIndexCostPerTask",
                     "contextWindowTokens"):
        assert expected in message
    assert "schema changed" not in message


@pytest.mark.parametrize("payload,names", [
    ('{"other":[]}', "none"),
    ('{"models":[],"initialModels":[]}', "initialModels, models"),
    ('{"models":[invalid],"initialModels":[{"slug":}]}', "initialModels, models"),
    ('{"models":[{"slug":"a"}', "models"),
])
def test_refusal_reports_empty_or_unreadable_candidates(payload, names):
    with pytest.raises(SystemExit) as caught:
        fetch_aa.richest_models_array(payload)
    message = str(caught.value)
    assert f"no full scored model records found in arrays: {names};" in message
    assert "richest record had 0 fields (none); expected scored records" in message
    assert "intelligenceIndexCostPerTask" in message
    assert "contextWindowTokens" in message
    assert "schema changed" not in message


def detail_record(slug="current", ii=51):
    """Small synthetic scored record with the detail route's published shape."""
    return {
        "slug": slug, "name": slug.title(), "shortName": slug.title(),
        "intelligenceIndex": ii,
        "contextWindowTokens": 100000, "parameters": 27,
        "price1mInputTokens": 1, "price1mOutputTokens": 3,
        "isOpenWeights": False, "deprecated": slug == "retired",
        "isReasoning": True, "intelligenceIndexIsEstimated": False,
        "licenseName": "Fixture licence", "releaseDate": "2026-01-01",
        "creator": {"id": "lab", "slug": "lab", "name": "Detail Lab",
                    "logo": None, "color": "gray", "country": "US"},
        "intelligenceIndexCostPerTask": {
            "cost": {"total": 0.75}, "evaluations": v5_evaluations(0.75)},
        "codingIndex": 40, "releaseSlug": slug,
        "medianTimeToFirstTokenSeconds": 0.1,
        "medianEndToEndResponseTimeSeconds": 1,
        "quartile25OutputTokensPerSecond": 90,
        "quartile75OutputTokensPerSecond": 110,
        # Shared identity must agree too for the matching-generation cases.
        **({"modelCreatorName": "Leaderboard Lab"} if slug == "current" else {}),
    }


def leaderboard(ii=51):
    record = {k: v for k, v in detail_record(ii=ii).items()
              if k not in ("parameters", "licenseName", "releaseDate", "creator")}
    record.update(intelligenceIndexCostPerTask=0.75,
                  modelCreatorName="Leaderboard Lab", medianOutputTokensPerSecond=100)
    return [{"slug": "host", "intelligenceIndexCostPerTask": None}, record]


def page(records, rich_name):
    index = [{"slug": r["slug"], "name": r.get("name", r["slug"]),
              "releaseSlug": r["slug"]} for r in records]
    payload = json.dumps([{rich_name: records}, {"models": index}],
                         separators=(",", ":"))
    return f"<script>self.__next_f.push([1,{json.dumps(payload)}])</script>"


def capture_pages(tmp_path, monkeypatch, first, second, detail, prev=None, state=None):
    base = tmp_path / "base.html"
    detail_path = tmp_path / "detail.html"
    methodology = tmp_path / "methodology.html"
    base.write_text(page(first, "initialModels"), encoding="utf-8")
    detail_path.write_text(page(detail, "models"), encoding="utf-8")
    methodology.write_text(
        f"Artificial Analysis Intelligence Index v{fetch_aa.INDEX_VERSION}",
        encoding="utf-8")

    def next_look(_seconds):
        base.write_text(page(second, "initialModels"), encoding="utf-8")

    monkeypatch.setattr(fetch_aa, "_sleep", next_look)
    return fetch_aa.capture(str(base), str(detail_path), str(methodology), prev, state)


@pytest.mark.parametrize("first_ii,second_ii,detail_ii,generations,filled", [
    (51, 51, 51, 1, [51]), (51, 51, 53, 2, [51]),
    (51, 52, 51, 2, [51]), (51, 52, 52, 2, [52]), (51, 52, 53, 3, [])])
def test_detail_only_additions_preserve_existing_records_and_in_run_decision(
        tmp_path, monkeypatch, first_ii, second_ii, detail_ii, generations, filled):
    """Invariance to adding detail-only records, not an old-merge reference."""
    first, second = leaderboard(first_ii), leaderboard(second_ii)
    shared_detail = [detail_record(ii=detail_ii)]
    baseline = capture_pages(tmp_path, monkeypatch, first, second, shared_detail)
    retired = detail_record("retired")
    older = detail_record("older")
    captured = capture_pages(tmp_path, monkeypatch, first, second,
                             shared_detail + [retired, older])
    assert {r["slug"] for r in captured.models} == {"host", "current", "retired", "older"}
    existing = [r for r in captured.models if r["slug"] in {"host", "current"}]
    assert json.dumps(existing) == json.dumps(baseline.models)
    assert captured.generations == generations
    current = next(r for r in existing if r["slug"] == "current")
    assert current.get("parameters") == (27 if filled else None)
    if first_ii == second_ii:
        assert "genVariants" not in current
        assert current["intelligenceIndexCostPerTask"]["cost"]["total"] == 0.75
    else:
        assert sorted(v["ii"] for v in current["genVariants"]) == [51, 52]
        # The breakdown widens only the generation the detail route matched.
        assert isinstance(current["intelligenceIndexCostPerTask"], dict) == (
            current["intelligenceIndex"] in filled)
    assert captured.disputed == baseline.disputed
    assert captured.generations == baseline.generations
    reversed_capture = capture_pages(tmp_path, monkeypatch, second, first,
                                     [older, retired] + shared_detail)
    assert json.dumps(captured.models) == json.dumps(reversed_capture.models)


def test_detail_only_presence_does_not_dispute_but_leaderboard_flip_does(
        tmp_path, monkeypatch):
    first = leaderboard() + [{"slug": "new", "intelligenceIndex": 30}]
    second = leaderboard()
    detail = [detail_record(), detail_record("retired"), detail_record("new", 30)]
    captured = capture_pages(tmp_path, monkeypatch, first, second, detail)
    by_slug = {r["slug"]: r for r in captured.models}
    assert "retired" in by_slug
    assert "genVariants" not in by_slug["retired"]
    assert sum(bool(v) for v in by_slug["new"]["genVariants"]) == 1
    assert captured.disputed


def test_cross_run_presence_sees_union_as_served_evidence(tmp_path, monkeypatch):
    retired = detail_record("retired")
    previous = build.merge_captures(leaderboard(), [detail_record()]) + [retired]
    previous.append({"slug": "gone", "intelligenceIndex": 30})
    detail = [detail_record(), retired, detail_record("new", 30)]
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(),
                             detail, previous)
    assert captured.cross_run.dropped == ["gone"]
    assert captured.cross_run.readded == ["new"]
    retired_now = next(r for r in captured.models if r["slug"] == "retired")
    assert "crossRunMerged" not in retired_now
    assert "genVariants" not in retired_now
    current_now = next(r for r in captured.models if r["slug"] == "current")
    assert json.dumps(current_now) == json.dumps(previous[1])


def test_cross_run_generation_revisit_keeps_union_through_hold_and_exit(
        tmp_path, monkeypatch):
    state = {"remembered": [], "last": None, "held": None}
    previous = None
    captures = []
    for ii in (51, 52, 51, 52, 53):
        captured = capture_pages(
            tmp_path, monkeypatch, leaderboard(ii), leaderboard(ii),
            [detail_record(ii=ii), detail_record("retired")], previous, state)
        assert {r["slug"] for r in captured.models} == {"host", "current", "retired"}
        captures.append(captured)
        previous = captured.models
    assert captures[2].revisit_action == "hold entered"
    assert captures[3].revisit_action == "held"
    assert build.build_rows(captures[2].models) == build.build_rows(captures[3].models)
    retired = next(r for r in captures[2].models if r["slug"] == "retired")
    assert all(v["ii"] == 51 for v in retired["genVariants"])
    assert captures[4].revisit_action == "hold ended"
    assert all("genVariants" not in r for r in captures[4].models)


def test_in_run_dispute_of_held_members_retains_detail_only_models(
        tmp_path, monkeypatch):
    state = {"remembered": [], "last": None, "held": None}
    previous = None
    for ii in (51, 52, 51):
        previous = capture_pages(
            tmp_path, monkeypatch, leaderboard(ii), leaderboard(ii),
            [detail_record(ii=ii), detail_record("retired")], previous, state).models
    before = json.dumps(state)
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(51), leaderboard(52),
                             [detail_record(), detail_record("retired")], previous, state)
    assert captured.revisit_action == "held"
    assert json.dumps(state) == before
    assert build.build_rows(captured.models) == build.build_rows(previous)
    assert "retired" in {r["slug"] for r in captured.models}


@pytest.mark.parametrize("creator,expected", [
    ({"name": "Detail Lab"}, "Detail Lab"),
    (..., None), (None, None), ("Lab", None), ([{"name": "Lab"}], None),
    ({"name": 42}, None), ({}, None), ({"name": None}, None)])
def test_detail_only_lab_uses_only_a_string_creator_name(
        tmp_path, monkeypatch, creator, expected):
    retired = detail_record("retired")
    if creator is ...:
        retired.pop("creator")
    else:
        retired["creator"] = creator
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(),
                             [detail_record(), retired])
    model = next(r for r in captured.models if r["slug"] == "retired")
    assert model.get("modelCreatorName") == expected
    assert ("modelCreatorName" in model) == (expected is not None)
    assert "medianOutputTokensPerSecond" not in model


def test_detail_only_explicit_lab_wins_over_creator_name(tmp_path, monkeypatch):
    retired = detail_record("retired")
    retired["modelCreatorName"] = "Explicit Lab"
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(),
                             [detail_record(), retired])
    model = next(r for r in captured.models if r["slug"] == "retired")
    assert model["modelCreatorName"] == "Explicit Lab"
    assert model["creator"]["name"] == "Detail Lab"


def test_build_renders_detail_only_retirement_lab_speed_and_mismatch(
        tmp_path, monkeypatch, capsys):
    retired = detail_record("retired", ii=60)
    captured = capture_pages(tmp_path, monkeypatch, leaderboard(), leaderboard(),
                             [detail_record(), retired])
    raw, agents, output = (tmp_path / name for name in ("models.json", "agents.json", "page.html"))
    raw.write_text(json.dumps(captured.models), encoding="utf-8")
    agents.write_text(json.dumps([{
        "id": "agent", "displayLabel": "Agent", "agentName": "Agent",
        "hostModelSlug": "current", "indexScore": 0.5,
        "mean": {"costUsd": 1, "agentWallTimeSec": 10}}]), encoding="utf-8")
    (tmp_path / "captured-at.txt").write_text("2026-10-17\n", encoding="utf-8")
    for name, path in (("ROOT", tmp_path), ("RAW", raw),
                       ("AGENTS_RAW", agents), ("OUT", output)):
        monkeypatch.setattr(build, name, path)
    build.main(generation_state=None)
    stdout = capsys.readouterr().out
    assert "MISMATCH -- still undominated: Retired" in stdout
    html = output.read_text(encoding="utf-8")
    rows = build.build_rows(captured.models)
    row = next(r for r in rows if r["name"] == "Retired")
    assert row["creator"] == "Detail Lab"
    assert row["tps"] is None
    assert row["dep"] is True
    _, table = build.render_static_tbodies([row])
    assert '<span class="tag">vendor-retired</span>' in table
    assert '<td>Detail Lab</td>' in table
    assert '<td class="n">$3</td><td class="n">—</td><td class="n">100K</td>' in table
    assert table in html

    # Detail-only membership does not relax the existing empty-axis refusal.
    for record in captured.models:
        record.pop("parameters", None)
    raw.write_text(json.dumps(captured.models), encoding="utf-8")
    with pytest.raises(SystemExit, match="no rows carry a score/cost pair for: parameters"):
        build.main(generation_state=None)


@pytest.mark.parametrize("rescued,outcome", [
    ("no-extra", "hold"), ("neither", "hold"), ("parameters", "publish"),
])
def test_three_generation_window_uses_leaderboard_provenance(
        tmp_path, monkeypatch, capsys, rescued, outcome):
    """Real capture CLI through build: extras cannot erase a route window."""
    data = tmp_path / "data"
    data.mkdir()
    base, detail, methodology, agents = (tmp_path / name for name in
                                         ("base.html", "detail.html", "method.html", "agents.html"))
    retired = detail_record("retired")
    if rescued != "parameters":
        retired.pop("parameters")
        retired.pop("intelligenceIndex")
    detail_rows = [detail_record(ii=53)]
    if rescued != "no-extra":
        detail_rows.append(retired)
    base.write_text(page(leaderboard(51), "initialModels"), encoding="utf-8")
    detail.write_text(page(detail_rows, "models"), encoding="utf-8")
    methodology.write_text(f"Artificial Analysis Intelligence Index v{fetch_aa.INDEX_VERSION}",
                           encoding="utf-8")
    agents_payload = json.dumps({"rows": [
        {"id": str(i), "displayLabel": f"Agent {i}", "hostModelSlug": "current",
         "indexScore": 0.5, "mean": {"costUsd": 1}} for i in range(5)]})
    agents.write_text(f"<script>self.__next_f.push([1,{json.dumps(agents_payload)}])</script>",
                      encoding="utf-8")
    output = tmp_path / "page.html"
    raw, raw_agents = data / "aa-raw-models.json", data / "aa-raw-coding-agents.json"
    for module, paths in ((fetch_aa, {"ROOT": tmp_path, "OUT": raw,
                                      "AGENTS_OUT": raw_agents, "STAMP": data / "captured-at.txt"}),
                          (build, {"ROOT": tmp_path, "RAW": raw,
                                   "AGENTS_RAW": raw_agents, "OUT": output})):
        for key, value in paths.items():
            monkeypatch.setattr(module, key, value)
    monkeypatch.setattr(sys, "argv", ["fetch_aa.py", "--html", str(base),
                                      "--detail-html", str(detail), "--agents-html", str(agents),
                                      "--methodology-html", str(methodology)])
    monkeypatch.setattr(fetch_aa, "_sleep", lambda _seconds:
                        base.write_text(page(leaderboard(52), "initialModels"), encoding="utf-8"))
    # Redirect only marker IO while exercising the real recording decision.
    record_window = fetch_aa.record_cost_window
    monkeypatch.setattr(fetch_aa, "record_cost_window", lambda priced, dropped, **kwargs:
                        record_window(priced, dropped, data / "cost-breakdown-window.txt", **kwargs))
    fetch_aa.main()
    assert "3 generation(s) observed in-run" in capsys.readouterr().out
    if outcome == "hold":
        with pytest.raises(build.WindowHold, match="3 generation\\(s\\) observed in-run"):
            build.main(generation_state=None)
        assert not output.exists()
    else:
        build.main(generation_state=None)
        assert output.exists()
    assert (data / "cost-breakdown-window.txt").exists()
    assert "changed shape" not in capsys.readouterr().out
