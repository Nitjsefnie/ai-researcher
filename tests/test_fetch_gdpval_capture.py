"""The GDPval evaluation route and the capture's dispute layers."""
import gzip
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import fetch_aa  # noqa: E402  # pylint: disable=wrong-import-position
from test_fetch_aa import (  # noqa: E402  # pylint: disable=wrong-import-position
    agent_payload, agent_row, detail_payload, flight_html, leaderboard_payload,
    methodology_html,
)
from test_fetch_aa_membership import (  # noqa: E402  # pylint: disable=wrong-import-position
    detail_record, leaderboard, page,
)
from test_fetch_gdpval import model, payload  # noqa: E402  # pylint: disable=wrong-import-position
from test_fetch_gdpval_route import fixture_files  # noqa: E402  # pylint: disable=wrong-import-position


def _capture(tmp_path, monkeypatch, first, second, detail, costs, prev=None, state=None,
             evaluated=None):
    base, detailed, method = [tmp_path / name for name in ("base.html", "detail.html", "method.html")]
    base.write_text(page(first, "initialModels"), encoding="utf-8")
    detailed.write_text(page(detail, "models"), encoding="utf-8")
    method.write_text(methodology_html(), encoding="utf-8")
    monkeypatch.setattr(fetch_aa, "_sleep", lambda _: base.write_text(
        page(second, "initialModels"), encoding="utf-8"))
    if evaluated is None:
        evaluated = [{"slug": slug} for slug in costs] or [{"slug": "current"}]
    snapshot = fetch_aa.fetch_gdpval.Evaluation(evaluated, costs, "/data/example.txt")
    return fetch_aa.capture(str(base), str(detailed), str(method), prev, state,
                            gdpval_loader=lambda: snapshot)


def test_join_uses_slug_and_keeps_detail_only_rows(tmp_path, monkeypatch):
    first = leaderboard()
    detail = [detail_record(), detail_record("retired")]
    captured = _capture(tmp_path, monkeypatch, first, first, detail,
                        {"current": 1.25, "retired": 2.5, "not-captured": 3})
    records = {row["slug"]: row for row in captured.models}
    assert "id" not in records["current"]
    assert records["current"]["gdpvalCostPerTask"] == 1.25
    assert records["retired"]["gdpvalCostPerTask"] == 2.5
    assert "gdpvalCostPerTask" not in records["host"]
    assert "not-captured" not in records


@pytest.mark.parametrize("observed,expected", [
    ({"slug": "current", "intelligenceIndex": 51}, {51: 1.25}),
    ({"slug": "current", "intelligenceIndex": 52}, {52: 1.25}),
    ({"slug": "current", "price1mInputTokens": 1}, {51: 1.25, 52: 1.25}),
    ({"slug": "current", "intelligenceIndex": 53}, {}),
    ({"slug": "current", "intelligenceIndex": 51,
      "medianOutputTokensPerSecond": 999}, {51: 1.25}),
], ids=["match-first", "match-second", "match-both", "match-neither", "never-red"])
def test_evaluation_cost_joins_only_matching_in_run_generations(
        tmp_path, monkeypatch, observed, expected):
    first, second = leaderboard(51), leaderboard(52)
    detail = [detail_record(ii=51)]
    baseline = _capture(tmp_path, monkeypatch, first, second, detail, {}, evaluated=[observed])
    captured = _capture(tmp_path, monkeypatch, first, second, detail,
                        {"current": 1.25}, evaluated=[observed])
    assert captured.disputed == baseline.disputed
    current = next(row for row in captured.models if row["slug"] == "current")
    without_cost = next(row for row in baseline.models if row["slug"] == "current")
    assert [v["ii"] for v in current["genVariants"]] == [
        v["ii"] for v in without_cost["genVariants"]]
    assert {v["ii"] for v in current["genVariants"]} == {51, 52}
    assert {v["ii"]: v["gdpvalCost"] for v in current["genVariants"]
            if "gdpvalCost" in v} == expected
    assert ("gdpvalCostPerTask" in current) == bool(expected)


def test_evaluation_cost_does_not_change_canonical_generation_order(tmp_path, monkeypatch):
    first, second = leaderboard(51), leaderboard(52)
    detail = [detail_record(ii=51)]
    observed = [{"slug": "current", "intelligenceIndex": 51}]
    baseline = _capture(tmp_path, monkeypatch, first, second, detail, {}, evaluated=observed)
    captured = _capture(tmp_path, monkeypatch, first, second, detail,
                        {"current": 0.01}, evaluated=observed)
    rows = [next(r for r in result.models if r["slug"] == "current")
            for result in (baseline, captured)]
    assert [[v["ii"] for v in row["genVariants"]] for row in rows] == [[52, 51], [52, 51]]


def test_evaluation_does_not_assign_a_cost_to_an_absent_model_variant(tmp_path, monkeypatch):
    first = leaderboard(51)
    second = [first[0], dict(first[1], slug="other")]
    evaluated = [{"slug": "current", "intelligenceIndex": 51},
                 {"slug": "other", "intelligenceIndex": 51}]
    captured = _capture(tmp_path, monkeypatch, first, second, [detail_record(ii=51)],
                        {"current": 1.25, "other": 2.5}, evaluated=evaluated)
    current = next(row for row in captured.models if row["slug"] == "current")
    assert len(current["genVariants"]) == 2
    assert sum(not variant for variant in current["genVariants"]) == 1
    assert [v["gdpvalCost"] for v in current["genVariants"] if v] == [1.25]


def test_comparison_fields_include_fields_found_only_in_later_evaluation_records(tmp_path, monkeypatch):
    first, second = leaderboard(51), leaderboard(52)
    evaluated = [{"slug": "unshared", "price1mInputTokens": 1},
                 {"slug": "current", "price1mInputTokens": 1, "intelligenceIndex": 51}]
    captured = _capture(tmp_path, monkeypatch, first, second, [detail_record(ii=51)],
                        {"current": 1.25}, evaluated=evaluated)
    current = next(row for row in captured.models if row["slug"] == "current")
    assert {v["ii"]: v["gdpvalCost"] for v in current["genVariants"]
            if "gdpvalCost" in v} == {51: 1.25}


@pytest.mark.parametrize("observed,expected", [(51, 2.5), (53, None)])
def test_disputed_detail_only_cost_requires_a_matching_look(tmp_path, monkeypatch, observed, expected):
    first, second = leaderboard(51), leaderboard(52)
    evaluated = [{"slug": "current", "intelligenceIndex": observed},
                 {"slug": "retired", "intelligenceIndex": observed}]
    captured = _capture(tmp_path, monkeypatch, first, second,
                        [detail_record(ii=51), detail_record("retired", ii=51)],
                        {"current": 1.25, "retired": 2.5}, evaluated=evaluated)
    retired = next(row for row in captured.models if row["slug"] == "retired")
    assert retired.get("gdpvalCostPerTask") == expected


@pytest.mark.parametrize("observed,expected", [
    ({"intelligenceIndex": 51}, [1.25, None]),
    ({"intelligenceIndex": 52}, [None, 1.25]),
    ({"price1mInputTokens": 1}, [1.25, 1.25]),
    ({"intelligenceIndex": 53}, [None, None]),
])
def test_cross_run_layer_receives_only_matching_corpora(tmp_path, monkeypatch, observed, expected):
    corpora = []

    def remember(models, _previous, inputs, _state):
        corpora.extend(inputs)
        return models, inputs, False, None

    monkeypatch.setattr(fetch_aa, "revisit_merge", remember)
    _capture(tmp_path, monkeypatch, leaderboard(51), leaderboard(52), [detail_record(ii=51)],
             {"current": 1.25}, state={}, evaluated=[dict(observed, slug="current")])
    assert [next(r for r in corpus if r["slug"] == "current").get("gdpvalCostPerTask")
            for corpus in corpora] == expected


def test_quiet_capture_uses_evaluation_cost_even_if_generations_differ(tmp_path, monkeypatch):
    first = leaderboard(51)
    captured = _capture(tmp_path, monkeypatch, first, first, [detail_record(ii=51)],
                        {"current": 1.25}, evaluated=[{"slug": "current", "intelligenceIndex": 99}])
    current = next(row for row in captured.models if row["slug"] == "current")
    assert not captured.disputed
    assert current["gdpvalCostPerTask"] == 1.25
    assert "genVariants" not in current


def test_no_shared_comparison_fields_refuses_and_names_the_data_file(tmp_path, monkeypatch):
    first = leaderboard()
    with pytest.raises(SystemExit, match="/data/example.txt"):
        _capture(tmp_path, monkeypatch, first, first, [detail_record()], {}, evaluated=[])


def test_missing_current_cost_is_not_carried_from_previous_capture(tmp_path, monkeypatch):
    first = leaderboard()
    previous = [dict(row, gdpvalCostPerTask=1.25) if row["slug"] == "current" else row
                for row in first]
    captured = _capture(tmp_path, monkeypatch, first, first, [detail_record()], {}, previous)
    current = next(row for row in captured.models if row["slug"] == "current")
    assert "gdpvalCostPerTask" not in current


def test_presence_merge_keeps_a_departed_models_cost_as_a_variant(tmp_path, monkeypatch):
    first = leaderboard()
    previous = first + [{"slug": "departed", "intelligenceIndex": 40,
                         "gdpvalCostPerTask": 2.5}]
    captured = _capture(tmp_path, monkeypatch, first, first, [detail_record()], {}, previous)
    departed = next(row for row in captured.models if row["slug"] == "departed")
    assert departed["crossRunMerged"]
    assert sorted(v.get("gdpvalCost", 0) for v in departed["genVariants"]) == [0, 2.5]


def test_revisit_holds_each_generations_cost():
    first = [{"slug": "model", "intelligenceIndex": 50, "gdpvalCostPerTask": 1.25}]
    second = [{"slug": "model", "intelligenceIndex": 50, "gdpvalCostPerTask": 2.5}]
    state: dict = {"remembered": [], "last": None, "held": None}
    fetch_aa.remember_generation(state, fetch_aa.revisit_key(first))
    fetch_aa.revisit_merge(second, first, [second], state)
    held, corpora, rendering, action = fetch_aa.revisit_merge(first, second, [first], state)
    assert rendering and action == "hold entered"
    assert sorted(v["gdpvalCost"] for v in held[0]["genVariants"]) == [1.25, 2.5]
    assert all("gdpvalCostPerTask" in records[0] for records in corpora)


def _main_files(tmp_path, monkeypatch, content=None):
    base, detail, agents, method = [tmp_path / name for name in
                                    ("base.html", "detail.html", "agents.html", "method.html")]
    base.write_text(flight_html(leaderboard_payload()), encoding="utf-8")
    detail.write_text(flight_html(detail_payload()), encoding="utf-8")
    agents.write_text(flight_html(agent_payload([agent_row(f"Agent {i}") for i in range(5)])),
                      encoding="utf-8")
    method.write_text(methodology_html(), encoding="utf-8")
    if content is None:
        content = gzip.compress(json.dumps(payload(model(slug="fixture-model"))).encode("utf-8"))
    evaluation, data = fixture_files(tmp_path, content=content)
    paths = {"ROOT": tmp_path, "OUT": tmp_path / "models.json",
             "AGENTS_OUT": tmp_path / "agents.json", "STAMP": tmp_path / "stamp.txt"}
    for name, path in paths.items():
        monkeypatch.setattr(fetch_aa, name, path)
    monkeypatch.setattr(fetch_aa, "_sleep", lambda _: None)
    marker = tmp_path / "window.txt"
    record = fetch_aa.record_cost_window
    monkeypatch.setattr(fetch_aa, "record_cost_window", lambda priced, dropped, **kwargs:
                        record(priced, dropped, marker, **kwargs))
    args = ["fetch_aa.py", "--html", str(base), "--detail-html", str(detail),
            "--agents-html", str(agents), "--methodology-html", str(method),
            "--gdpval-html", str(evaluation), "--gdpval-data", str(data)]
    monkeypatch.setattr(sys, "argv", args)
    return paths, marker, evaluation, data


def test_main_writes_joined_cost_without_manifest(tmp_path, monkeypatch):
    paths, _, evaluation, _ = _main_files(tmp_path, monkeypatch)
    fetch_aa.main()
    captured = paths["OUT"].read_text(encoding="utf-8")
    row = next(r for r in json.loads(captured) if r["slug"] == "fixture-model")
    assert row["gdpvalCostPerTask"] == 4.5 / 220
    manifest = json.loads(fetch_aa.flight_payload(evaluation.read_text(encoding="utf-8")))["manifest"]
    assert manifest["key"] not in captured and manifest["path"] not in captured


def test_main_uses_decrypted_records_to_match_a_disputed_generation(tmp_path, monkeypatch):
    evaluation = model(slug="current", intelligenceIndex=51)
    content = gzip.compress(json.dumps(payload(evaluation)).encode("utf-8"))
    paths, _, _, _ = _main_files(tmp_path, monkeypatch, content)
    first, second = leaderboard(51), leaderboard(52)
    for look in (first, second):
        look[1].update(price1mInputTokens=2, price1mOutputTokens=10)
    detail = detail_record(ii=51)
    detail.update(price1mInputTokens=2, price1mOutputTokens=10)
    base, detailed = tmp_path / "base.html", tmp_path / "detail.html"
    base.write_text(page(first, "initialModels"), encoding="utf-8")
    detailed.write_text(page([detail], "models"), encoding="utf-8")
    monkeypatch.setattr(fetch_aa, "_sleep", lambda _: base.write_text(
        page(second, "initialModels"), encoding="utf-8"))
    fetch_aa.main()
    current = next(r for r in json.loads(paths["OUT"].read_text(encoding="utf-8"))
                   if r["slug"] == "current")
    assert {v["ii"]: v["gdpvalCost"] for v in current["genVariants"]
            if "gdpvalCost" in v} == {51: 4.5 / 220}
    assert "gdpval" not in current
    assert all("gdpval" not in variant for variant in current["genVariants"])


def test_empty_evaluation_field_set_leaves_existing_outputs_unchanged(tmp_path, monkeypatch):
    content = gzip.compress(b'{"models":[],"priceFallbackByModelId":{}}')
    paths, marker, _, _ = _main_files(tmp_path, monkeypatch, content)
    outputs = [paths["OUT"], paths["AGENTS_OUT"], paths["STAMP"], marker]
    for path in outputs:
        path.write_bytes(b"previous output")
    with pytest.raises(SystemExit, match="/data/example.txt"):
        fetch_aa.main()
    assert all(path.read_bytes() == b"previous output" for path in outputs)


def test_version_mismatch_refuses_before_evaluation_fetch(monkeypatch):
    events = []

    def fetch_page(_cached, url=fetch_aa.URL):
        events.append(url)
        assert url == fetch_aa.METHODOLOGY_URL
        return methodology_html("99.0")

    monkeypatch.setattr(sys, "argv", ["fetch_aa.py"])
    monkeypatch.setattr(fetch_aa, "fetch_html", fetch_page)
    monkeypatch.setattr(fetch_aa.fetch_gdpval, "fetch", lambda *_args: events.append("evaluation"))
    with pytest.raises(SystemExit, match="Intelligence Index v99.0"):
        fetch_aa.main()
    assert events == [fetch_aa.METHODOLOGY_URL]


def test_main_reads_methodology_once_before_evaluation(tmp_path, monkeypatch):
    _main_files(tmp_path, monkeypatch)
    events = []
    real_page, real_evaluation = fetch_aa.fetch_html, fetch_aa.fetch_gdpval.fetch

    def fetch_page(cached, url=fetch_aa.URL):
        events.append(url)
        return real_page(cached, url)

    def fetch_evaluation(*args):
        events.append("evaluation")
        return real_evaluation(*args)

    monkeypatch.setattr(fetch_aa, "fetch_html", fetch_page)
    monkeypatch.setattr(fetch_aa.fetch_gdpval, "fetch", fetch_evaluation)
    fetch_aa.main()
    assert events[:2] == [fetch_aa.METHODOLOGY_URL, "evaluation"]
    assert events.count(fetch_aa.METHODOLOGY_URL) == 1


@pytest.mark.parametrize("kind", ["page", "version", "manifest", "data", "tag", "gzip", "json", "schema"])
def test_main_refusal_leaves_all_capture_files_unchanged(tmp_path, monkeypatch, kind):
    content = {"gzip": b"bad gzip", "json": gzip.compress(b"bad JSON"),
               "schema": gzip.compress(b'{"models":[]}')}.get(kind)
    paths, marker, evaluation, data = _main_files(tmp_path, monkeypatch, content)
    state = paths["OUT"].with_name("aa-generation-state.json")
    sentinel_paths = [paths["OUT"], paths["AGENTS_OUT"], paths["STAMP"], marker, state]
    for path in sentinel_paths:
        path.write_bytes(b"previous output")
    paths["OUT"].write_text("[]", encoding="utf-8")
    state.write_text('{"held": null, "last": null, "remembered": []}', encoding="utf-8")
    before = {path: path.read_bytes() for path in sentinel_paths}
    sys.argv.append("--cross-run-lookback")
    if kind == "page":
        sys.argv[sys.argv.index("--gdpval-html") + 1] = str(tmp_path / "missing")
    elif kind == "version":
        evaluation.write_text("<title>GDPval-AA v2.2</title>", encoding="utf-8")
    elif kind == "manifest":
        evaluation.write_text("<title>GDPval-AA v2.1</title>", encoding="utf-8")
    elif kind == "data":
        sys.argv[sys.argv.index("--gdpval-data") + 1] = str(tmp_path / "missing")
    elif kind == "tag":
        body = bytearray(data.read_bytes())
        body[-1] ^= 1
        data.write_bytes(body)
    with pytest.raises(SystemExit) as caught:
        fetch_aa.main()
    expected = "evaluations/gdpval-aa" if kind in {"page", "version", "manifest"} else "/data/example.txt"
    assert expected in str(caught.value)
    reason = {"page": "page read failed", "version": "page title", "manifest": "flight manifest",
              "data": "data read failed", "tag": "authentication", "gzip": "gzip decompression",
              "json": "JSON decoding", "schema": "schema changed"}[kind]
    assert reason in str(caught.value)
    assert {path: path.read_bytes() for path in sentinel_paths} == before
