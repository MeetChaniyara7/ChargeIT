"""Scoring for "best station": PURE functions (no database, no network), so they are easy to test.

Each station gets six scores between 0 and 1, which are combined with the weights in
app/config.py (RECOMMENDATION_WEIGHTS). The result is a number from 0 to 1; higher is better.

    travel_time   a short drive scores high
    availability  more compatible chargers free in the requested window scores high
    power         faster charging scores high
    price         cheaper scores high
    rating        better rated scores high
    data_quality  real data scores higher than estimated data
"""

from dataclasses import dataclass

from app.config import RECOMMENDATION_RULES, RECOMMENDATION_WEIGHTS, RecommendationRules, RecommendationWeights


@dataclass(frozen=True)
class Candidate:
    """Everything the score needs to know about one station (already worked out by the caller)."""

    station_id: str
    free_compatible: int  # compatible chargers free for the whole requested window
    travel_minutes: float
    travel_is_routed: bool  # True = real road time from OSRM, False = straight-line estimate
    distance_km: float
    max_power_kw: float | None  # fastest free compatible charger
    min_price_per_kwh: float | None  # cheapest free compatible charger
    rating: float | None
    has_estimated_data: bool
    connector_label: str | None = None  # e.g. "CCS2" when the driver asked for one plug type


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    score: float
    parts: dict[str, float]  # each factor's 0-1 score, useful for debugging and tests
    reason: str


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def travel_score(minutes: float, rules: RecommendationRules = RECOMMENDATION_RULES) -> float:
    return clamp01(1 - minutes / rules.slow_travel_minutes)


def availability_score(free: int, rules: RecommendationRules = RECOMMENDATION_RULES) -> float:
    return clamp01(free / rules.full_availability_chargers)


def power_score(power_kw: float | None, rules: RecommendationRules = RECOMMENDATION_RULES) -> float:
    return clamp01((power_kw or 0) / rules.fast_power_kw)


def price_score(price: float | None, rules: RecommendationRules = RECOMMENDATION_RULES) -> float:
    """Cheap = 1, expensive = 0. Unknown price counts as the worst, so it never wins by hiding."""
    if price is None:
        return 0.0
    return clamp01((rules.expensive_price_inr - price) / (rules.expensive_price_inr - rules.cheap_price_inr))


def rating_score(rating: float | None, rules: RecommendationRules = RECOMMENDATION_RULES) -> float:
    return rules.unknown_rating_score if rating is None else clamp01(rating / 5)


def data_quality_score(has_estimated_data: bool, rules: RecommendationRules = RECOMMENDATION_RULES) -> float:
    return rules.estimated_data_score if has_estimated_data else 1.0


def reason_text(c: Candidate) -> str:
    """A short explanation: "2 CCS2 chargers free · 1.2 km · 60 kW"."""
    plug = f"{c.connector_label} " if c.connector_label else ""
    noun = "charger" if c.free_compatible == 1 else "chargers"
    parts = [f"{c.free_compatible} {plug}{noun} free"]
    parts.append(f"{c.distance_km:.1f} km")
    if c.max_power_kw:
        parts.append(f"{c.max_power_kw:g} kW")
    return " · ".join(parts)


def score_candidate(
    c: Candidate,
    weights: RecommendationWeights = RECOMMENDATION_WEIGHTS,
    rules: RecommendationRules = RECOMMENDATION_RULES,
) -> Scored:
    parts = {
        "travel_time": travel_score(c.travel_minutes, rules),
        "availability": availability_score(c.free_compatible, rules),
        "power": power_score(c.max_power_kw, rules),
        "price": price_score(c.min_price_per_kwh, rules),
        "rating": rating_score(c.rating, rules),
        "data_quality": data_quality_score(c.has_estimated_data, rules),
    }
    total = sum(getattr(weights, name) * value for name, value in parts.items())
    return Scored(candidate=c, score=round(total, 4), parts=parts, reason=reason_text(c))


def rank(
    candidates: list[Candidate],
    weights: RecommendationWeights = RECOMMENDATION_WEIGHTS,
    rules: RecommendationRules = RECOMMENDATION_RULES,
    limit: int | None = None,
) -> list[Scored]:
    """Best first. Only stations with at least one free compatible charger are recommended.

    Ties are broken by the shorter drive, then by station ID, so the order never changes between calls.
    """
    scored = [score_candidate(c, weights, rules) for c in candidates if c.free_compatible > 0]
    scored.sort(key=lambda s: (-s.score, s.candidate.travel_minutes, s.candidate.station_id))
    return scored[: limit if limit is not None else rules.max_results]
