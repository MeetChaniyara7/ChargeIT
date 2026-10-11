"""GET /recommendations: the best stations for this driver, this time, this plug.

Steps: find stations within 15 km -> work out which compatible chargers are free for the
whole requested window (one query) -> ask OSRM for real drive times to the nearest few
(one request, straight-line fallback) -> score and rank (scoring.py) -> explain each pick.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import BOOKING_RULES, RECOMMENDATION_RULES
from app.core.connectors import CONNECTOR_LABELS
from app.core.errors import AppError
from app.features.availability.occupancy import busy_charger_ids
from app.features.recommendations import scoring
from app.features.recommendations.osrm import TravelTimes, travel_times
from app.features.recommendations.schemas import Recommendation, RecommendationResponse
from app.features.stations import repository
from app.features.stations.models import Charger
from app.features.stations.repository import StationQuery
from app.features.stations.service import build_summary


def validate_window(start: datetime, duration_minutes: int, now: datetime) -> tuple[datetime, datetime]:
    rules = RECOMMENDATION_RULES
    slot_minutes = BOOKING_RULES.slot_minutes
    if not (rules.min_duration_minutes <= duration_minutes <= rules.max_duration_minutes) or duration_minutes % slot_minutes:
        raise AppError(
            422, "INVALID_DURATION",
            f"Duration must be between {rules.min_duration_minutes} and {rules.max_duration_minutes} minutes, in steps of {slot_minutes}.",
        )
    start = max(start, now)  # nobody can charge in the past
    if start > now + timedelta(days=BOOKING_RULES.max_days_ahead):
        raise AppError(422, "START_TOO_FAR", f"Start must be within the next {BOOKING_RULES.max_days_ahead} days.")
    return start, start + timedelta(minutes=duration_minutes)


def recommend(
    db: Session,
    *,
    lat: float,
    lng: float,
    connectors: list[str],
    start: datetime,
    duration_minutes: int,
    now: datetime,
    travel: TravelTimes | None = None,
) -> RecommendationResponse:
    travel = travel or travel_times  # looked up now (not when the module loads) so tests can swap it
    window_start, window_end = validate_window(start, duration_minutes, now)
    rules = RECOMMENDATION_RULES

    query = StationQuery(center=(lat, lng), radius_km=BOOKING_RULES.recommendation_radius_km, connectors=connectors, limit=200)
    stations = repository.find_stations(db, query)[: query.limit]  # nearest first

    def compatible(charger: Charger) -> bool:
        return not connectors or charger.connector_type in connectors

    all_compat = [c for s in stations for c in s.chargers if compatible(c)]
    busy = busy_charger_ids(db, [c.charger_id for c in all_compat], window_start, window_end, now)  # ONE query

    def is_free(c: Charger) -> bool:
        return c.status == "AVAILABLE" and c.charger_id not in busy

    with_free = [(s, [c for c in s.chargers if compatible(c) and is_free(c)]) for s in stations]
    with_free = [(s, free) for s, free in with_free if free]
    pool = with_free[: rules.candidate_pool]  # the nearest few that actually have a free charger
    if not pool:
        return RecommendationResponse(window_start=window_start, window_end=window_end, results=[])

    trips = travel.estimate((lat, lng), [(s.latitude, s.longitude) for s, _ in pool])  # ONE routing request
    label = CONNECTOR_LABELS.get(connectors[0]) if len(connectors) == 1 else None

    candidates, details = [], {}
    for (station, free), trip in zip(pool, trips):
        powers = [float(c.power_kw) for c in free if c.power_kw is not None]
        prices = [float(c.price_per_kwh) for c in free if c.price_per_kwh is not None]
        candidates.append(
            scoring.Candidate(
                station_id=str(station.station_id),
                free_compatible=len(free),
                travel_minutes=trip.minutes,
                travel_is_routed=trip.routed,
                distance_km=trip.distance_km,
                max_power_kw=max(powers) if powers else None,
                min_price_per_kwh=min(prices) if prices else None,
                rating=float(station.rating) if station.rating is not None else None,
                has_estimated_data=station.has_estimated_data,
                connector_label=label,
            )
        )
        details[str(station.station_id)] = (station, [c for c in station.chargers if compatible(c)], trip)

    results = []
    for scored in scoring.rank(candidates, limit=rules.max_results):
        station, compat_chargers, trip = details[scored.candidate.station_id]
        summary = build_summary(station, compat_chargers, busy, window_start, (lat, lng))
        results.append(
            Recommendation(
                station=summary.model_copy(update={"distance_km": round(trip.distance_km, 2)}),
                score=scored.score,
                reason=scored.reason,
                free_compatible=scored.candidate.free_compatible,
                travel_minutes=round(trip.minutes, 1),
                travel_is_routed=trip.routed,
                distance_km=round(trip.distance_km, 2),
            )
        )
    return RecommendationResponse(window_start=window_start, window_end=window_end, results=results)

