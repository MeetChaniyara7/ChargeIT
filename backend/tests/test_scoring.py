"""Recommendation scoring: pure functions, no database or network."""

import pytest

from app.config import RECOMMENDATION_RULES, RECOMMENDATION_WEIGHTS, RecommendationWeights
from app.features.recommendations import scoring
from app.features.recommendations.scoring import Candidate, rank, reason_text, score_candidate


def candidate(station_id="a", **overrides) -> Candidate:
    base = dict(
        station_id=station_id, free_compatible=2, travel_minutes=10.0, travel_is_routed=True, distance_km=4.0,
        max_power_kw=60.0, min_price_per_kwh=20.0, rating=4.0, has_estimated_data=False, connector_label="CCS2",
    )
    base.update(overrides)
    return Candidate(**base)


def test_weights_add_up_to_one():
    w = RECOMMENDATION_WEIGHTS
    assert w.travel_time + w.availability + w.power + w.price + w.rating + w.data_quality == pytest.approx(1.0)


@pytest.mark.parametrize("fn, low, high", [
    (scoring.travel_score, 25, 5),          # shorter drive scores higher
    (scoring.availability_score, 1, 3),     # more free chargers scores higher
    (scoring.power_score, 22, 120),         # faster scores higher
    (scoring.price_score, 28, 12),          # cheaper scores higher
    (scoring.rating_score, 3.0, 4.8),       # better rated scores higher
])
def test_each_factor_improves_in_the_right_direction(fn, low, high):
    assert 0 <= fn(low) < fn(high) <= 1


def test_factors_are_clamped_to_0_1():
    assert scoring.travel_score(500) == 0 and scoring.travel_score(0) == 1
    assert scoring.availability_score(50) == 1
    assert scoring.power_score(900) == 1
    assert scoring.price_score(2) == 1 and scoring.price_score(99) == 0


def test_unknown_values_are_neutral_or_pessimistic_never_rewarded():
    assert scoring.rating_score(None) == RECOMMENDATION_RULES.unknown_rating_score
    assert scoring.price_score(None) == 0   # hiding a price does not help a station
    assert scoring.power_score(None) == 0
    assert scoring.data_quality_score(True) < scoring.data_quality_score(False) == 1


def test_a_better_station_ranks_first():
    close_fast = candidate("close", travel_minutes=5, distance_km=2, max_power_kw=120, min_price_per_kwh=18)
    far_slow = candidate("far", travel_minutes=25, distance_km=11, max_power_kw=22, min_price_per_kwh=26)
    assert [s.candidate.station_id for s in rank([far_slow, close_fast])] == ["close", "far"]


def test_more_free_chargers_beats_a_slightly_shorter_drive():
    two_free = candidate("two", free_compatible=2, travel_minutes=9)
    one_free = candidate("one", free_compatible=1, travel_minutes=8)
    assert rank([one_free, two_free])[0].candidate.station_id == "two"


def test_real_data_beats_estimated_data_when_all_else_is_equal():
    real = candidate("real", has_estimated_data=False)
    guessed = candidate("guessed", has_estimated_data=True)
    assert [s.candidate.station_id for s in rank([guessed, real])] == ["real", "guessed"]


def test_changing_the_weights_changes_the_winner():
    near = candidate("near", travel_minutes=3, distance_km=1, max_power_kw=22, min_price_per_kwh=28)
    fast = candidate("fast", travel_minutes=20, distance_km=9, max_power_kw=120, min_price_per_kwh=28)
    wants_near = RecommendationWeights(travel_time=0.9, availability=0.0, power=0.0, price=0.0, rating=0.1, data_quality=0.0)
    wants_fast = RecommendationWeights(travel_time=0.0, availability=0.0, power=0.9, price=0.0, rating=0.1, data_quality=0.0)
    assert rank([near, fast], weights=wants_near)[0].candidate.station_id == "near"
    assert rank([near, fast], weights=wants_fast)[0].candidate.station_id == "fast"


def test_ties_are_broken_by_shorter_drive_then_by_id_so_the_order_is_stable():
    a = candidate("b-id", travel_minutes=10)
    b = candidate("a-id", travel_minutes=10)
    c = candidate("c-id", travel_minutes=9.99)
    # identical scores for a and b; c has the same inputs except a (slightly) shorter drive so it scores higher anyway
    order = [s.candidate.station_id for s in rank([a, b, c])]
    assert order[0] == "c-id" and order[1:] == ["a-id", "b-id"]
    assert [s.candidate.station_id for s in rank([b, a, c])] == order  # same answer whatever the input order


def test_stations_with_nothing_free_are_never_recommended():
    assert rank([candidate("none", free_compatible=0)]) == []


def test_no_candidates_means_no_results():
    assert rank([]) == []


def test_results_are_limited():
    many = [candidate(f"s{i}", travel_minutes=1 + i) for i in range(12)]
    assert len(rank(many)) == RECOMMENDATION_RULES.max_results
    assert len(rank(many, limit=3)) == 3


def test_score_is_between_0_and_1_and_exposes_its_parts():
    scored = score_candidate(candidate())
    assert 0 <= scored.score <= 1
    assert set(scored.parts) == {"travel_time", "availability", "power", "price", "rating", "data_quality"}
    best = score_candidate(candidate(travel_minutes=0, free_compatible=9, max_power_kw=500, min_price_per_kwh=1, rating=5, has_estimated_data=False))
    assert best.score == pytest.approx(1.0)


@pytest.mark.parametrize("overrides, expected", [
    ({}, "2 CCS2 chargers free · 4.0 km · 60 kW"),
    ({"free_compatible": 1}, "1 CCS2 charger free · 4.0 km · 60 kW"),
    ({"connector_label": None}, "2 chargers free · 4.0 km · 60 kW"),
    ({"max_power_kw": None}, "2 CCS2 chargers free · 4.0 km"),
    ({"max_power_kw": 22.5, "distance_km": 12.34}, "2 CCS2 chargers free · 12.3 km · 22.5 kW"),
])
def test_reason_text(overrides, expected):
    assert reason_text(candidate(**overrides)) == expected
