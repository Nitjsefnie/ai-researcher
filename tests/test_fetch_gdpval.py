"""GDPval cost extraction and schema controls."""
import copy
import importlib
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

DATA_PATH = "/data/example.txt"


def model(**changes):
    row = {
        "id": "model-id", "slug": "test-model", "gdpval": -401.79,
        "canonicalEvalTokenCounts": {"gdpval": {
            "input": 1_000_000, "cacheableInput": 800_000,
            "answer": 200_000, "reasoning": 100_000}},
        "cacheHitRate": 0.75, "price1mInputTokens": 2,
        "price1mOutputTokens": 10, "cacheHitPrice": 0.5,
        "cacheWritePrice": 3,
    }
    row.update(changes)
    return row


def payload(row=None, fallback=None):
    return {"models": [model() if row is None else row],
            "priceFallbackByModelId": {} if fallback is None else fallback}


def get_costs(data):
    route = importlib.import_module("fetch_gdpval")
    return route.costs(data, DATA_PATH)


def test_cacheable_input_prices_the_remainder_at_the_write_price():
    assert get_costs(payload()) == {"test-model": 4.5 / 220}


def test_null_cacheable_input_does_not_need_a_hit_rate():
    row = model(cacheHitRate=None)
    row["canonicalEvalTokenCounts"]["gdpval"]["cacheableInput"] = None
    assert get_costs(payload(row)) == {"test-model": 5 / 220}


@pytest.mark.parametrize("changes,expected", [
    ({"cacheHitPrice": None}, 5.4 / 220),
    ({"cacheWritePrice": None}, 4.1 / 220),
    ({"cacheHitPrice": None, "cacheWritePrice": None}, 5 / 220),
])
def test_null_cache_prices_fall_back_to_input_price(changes, expected):
    assert get_costs(payload(model(**changes)))["test-model"] == pytest.approx(expected)


@pytest.mark.parametrize("fraction", ["input", "output", "reasoning"])
def test_any_nonzero_gdpval_fallback_fraction_omits_the_cost(fraction):
    rates: dict[str, float] = {"input": 0, "output": 0, "reasoning": 0}
    rates[fraction] = 0.01
    fallback = {"model-id": {"rateByEval": {"gdpval-aa": rates}}}
    assert get_costs(payload(fallback=fallback)) == {}


def test_all_zero_fallback_keeps_the_cost():
    fallback = {"model-id": {"rateByEval": {"gdpval-aa": {
        "input": 0, "output": 0, "reasoning": 0}}}}
    assert get_costs(payload(fallback=fallback)) == {"test-model": 4.5 / 220}


def test_absent_gdpval_fallback_ignores_intelligence_index_rate():
    fallback = {"model-id": {"rateByEval": {}, "intelligenceIndexRate": {
        "input": 1, "output": 1, "reasoning": 1}}}
    assert get_costs(payload(fallback=fallback)) == {"test-model": 4.5 / 220}


@pytest.mark.parametrize("missing", ["input", "output", "reasoning"])
def test_a_fallback_missing_any_fraction_is_a_schema_change(missing):
    rates = {"input": 0, "output": 0, "reasoning": 0}
    rates.pop(missing)
    fallback = {"model-id": {"rateByEval": {"gdpval-aa": rates}}}
    with pytest.raises(SystemExit, match=DATA_PATH):
        get_costs(payload(fallback=fallback))


@pytest.mark.parametrize("changes", [
    {"gdpval": None}, {"canonicalEvalTokenCounts": None},
    {"cacheHitRate": None}, {"price1mInputTokens": None},
    {"price1mOutputTokens": None},
    {"price1mInputTokens": 0, "price1mOutputTokens": 0,
     "cacheHitPrice": 0, "cacheWritePrice": 0},
])
def test_missing_inputs_or_nonpositive_cost_are_not_emitted(changes):
    assert get_costs(payload(model(**changes))) == {}


@pytest.mark.parametrize("data", [
    {"models": [], "priceFallbackByModelId": {}, "extra": 1},
    {"models": {}, "priceFallbackByModelId": {}},
    {"models": [None], "priceFallbackByModelId": {}},
    {"models": [{}], "priceFallbackByModelId": {}},
    payload(model(id=[])),
    {"models": [], "priceFallbackByModelId": []},
    payload(model(canonicalEvalTokenCounts={"gdpval": {"input": 1}})),
    payload(model(canonicalEvalTokenCounts={"gdpval": {
        "input": 1, "cacheableInput": None, "answer": 1, "reasoning": 1, "extra": 2}})),
    payload(model(canonicalEvalTokenCounts={"gdpval": {
        "input": 1, "cacheableInput": None, "answer": 1, "reasoning": True}})),
    payload(model(canonicalEvalTokenCounts={"gdpval": {
        "input": 1, "cacheableInput": 2, "answer": 1, "reasoning": 1}})),
    payload(fallback={"model-id": {"rateByEval": {"gdpval-aa": {
        "input": 0, "output": 0}}}}),
    payload(fallback={"model-id": {"rateByEval": {"gdpval-aa": None}}}),
])
def test_schema_change_refuses_with_the_data_path(data):
    before = copy.deepcopy(data)
    with pytest.raises(SystemExit, match=DATA_PATH):
        get_costs(data)
    assert data == before
