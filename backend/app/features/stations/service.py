"""Station search and detail: turns database rows into the live summaries the app shows."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import RECOMMENDATION_RULES
from app.core.errors import AppError
from app.core.geo import estimate_drive_minutes, haversine_km
from app.features.availability.occupancy import busy_right_now
from app.features.stations import repository
from app.features.stations.models import Charger, Station
from app.features.stations.opening_hours import is_open_now
from app.features.stations.repository import StationQuery
from app.features.stations.schemas import (
    ChargerDetail, StationDetail, StationSearchResponse, StationSummary,
)


@dataclass
class SearchFilters:
    query: StationQuery
    open_now: bool = False


def _is_free(charger: Charger, busy: set[UUID]) -> bool:
    """Free right now: working (status AVAILABLE) and no live booking covering this moment."""
    return charger.status == "AVAILABLE" and charger.charger_id not in busy


def _matches(charger: Charger, q: StationQuery) -> bool:
    if q.connectors and charger.connector_type not in q.connectors:
        return False
    if q.min_power_kw is not None and (charger.power_kw is None or float(charger.power_kw) < q.min_power_kw):
        return False
    return q.max_price_per_kwh is None or (
        charger.price_per_kwh is not None and float(charger.price_per_kwh) <= q.max_price_per_kwh
    )


def build_summary(
    station: Station,
    chargers: Sequence[Charger],
    busy: set[UUID],
    now: datetime,
    origin: tuple[float, float] | None = None,
) -> StationSummary:
    """One station's summary over the given chargers (all of them, or just the ones matching a filter)."""
    powers = [float(c.power_kw) for c in chargers if c.power_kw is not None]
    prices = [float(c.price_per_kwh) for c in chargers if c.price_per_kwh is not None]

    distance = eta = None
    if origin:
        distance = round(haversine_km(origin[0], origin[1], station.latitude, station.longitude), 2)
        eta = estimate_drive_minutes(distance, RECOMMENDATION_RULES.drive_speed_kmh)

    return StationSummary(
        station_id=station.station_id,
        name=station.name,
        address=station.address,
        city=station.city,
        latitude=station.latitude,
        longitude=station.longitude,
        operator_name=station.operator_name,
        vehicle_category=station.vehicle_category,
        opening_hours=station.opening_hours,
        is_open_now=is_open_now(station.opening_hours, now),
        rating=float(station.rating) if station.rating is not None else None,
        rating_is_estimated="rating" in (station.estimated_fields or []),
        rating_count=station.rating_count,
        data_source=station.data_source,
        has_estimated_data=station.has_estimated_data,
        charger_total=len(chargers),
        charger_free=sum(_is_free(c, busy) for c in chargers),
        connector_types=sorted({c.connector_type for c in chargers}),
        min_power_kw=min(powers) if powers else None,
        max_power_kw=max(powers) if powers else None,
        min_price_per_kwh=min(prices) if prices else None,
        distance_km=distance,
        eta_minutes_estimate=eta,
    )


def search(db: Session, filters: SearchFilters, now: datetime) -> StationSearchResponse:
    q = filters.query
    rows = repository.find_stations(db, q)
    truncated = len(rows) > q.limit
    rows = rows[: q.limit]

    matching = {s.station_id: [c for c in s.chargers if _matches(c, q)] for s in rows}
    busy = busy_right_now(db, [c.charger_id for chargers in matching.values() for c in chargers], now)  # one query

    summaries = [build_summary(s, matching[s.station_id], busy, now, q.center) for s in rows]
    if filters.open_now:
        # Only hide stations KNOWN to be closed; unknown hours stay visible.
        summaries = [s for s in summaries if s.is_open_now is not False]
    return StationSearchResponse(stations=summaries, count=len(summaries), limit=q.limit, truncated=truncated)


def detail(db: Session, station_id: UUID, now: datetime, origin: tuple[float, float] | None = None) -> StationDetail:
    station = repository.get_station(db, station_id)
    if not station or not station.is_active:
        raise AppError(404, "STATION_NOT_FOUND", "Station not found.")
    busy = busy_right_now(db, [c.charger_id for c in station.chargers], now)
    summary = build_summary(station, station.chargers, busy, now, origin)
    chargers = [
        ChargerDetail(
            charger_id=c.charger_id,
            label=c.label,
            connector_type=c.connector_type,
            current_type=c.current_type,
            power_kw=float(c.power_kw) if c.power_kw is not None else None,
            price_per_kwh=float(c.price_per_kwh) if c.price_per_kwh is not None else None,
            status=c.status,
            free_now=_is_free(c, busy),
            data_source=c.data_source,
            is_estimated=c.is_estimated,
            estimated_fields=list(c.estimated_fields or []),
        )
        for c in station.chargers
    ]
    return StationDetail(**summary.model_dump(), chargers=chargers)
