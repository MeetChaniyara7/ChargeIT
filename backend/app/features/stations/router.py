"""Station endpoints. Reading is public (the map works before login); creating needs an admin."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import BOOKING_RULES
from app.core.errors import AppError
from app.db import get_db
from app.features.auth.dependencies import require_admin
from app.features.stations import repository, service
from app.features.stations.repository import StationQuery
from app.features.stations.schemas import (
    ConnectorType, StationCount, StationCreate, StationDetail, StationSearchResponse,
)
from app.features.stations.service import SearchFilters

router = APIRouter(prefix="/api/stations", tags=["Stations"])

MAX_RADIUS_KM = 100.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    """'min_lng,min_lat,max_lng,max_lat' -> four numbers, or a clear 422 error."""
    try:
        min_lng, min_lat, max_lng, max_lat = (float(part) for part in text.split(","))
    except ValueError:
        raise AppError(422, "INVALID_BBOX", "bbox must be four numbers: min_lng,min_lat,max_lng,max_lat.") from None
    if not (-180 <= min_lng < max_lng <= 180 and -90 <= min_lat < max_lat <= 90):
        raise AppError(422, "INVALID_BBOX", "bbox must have min < max and stay within valid coordinates.")
    return min_lng, min_lat, max_lng, max_lat


def origin_from(lat: float | None, lng: float | None) -> tuple[float, float] | None:
    """Both coordinates or neither; a lone one is a 422 error."""
    if (lat is None) != (lng is None):
        raise AppError(422, "INVALID_LOCATION", "Give both lat and lng, or neither.")
    return (lat, lng) if lat is not None and lng is not None else None


@router.get("", response_model=StationSearchResponse)
def search_stations(
    bbox: str | None = Query(None, description="Map area: min_lng,min_lat,max_lng,max_lat"),
    lat: float | None = Query(None, ge=-90, le=90, description="Search point: sorts by distance"),
    lng: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, gt=0, le=MAX_RADIUS_KM, description="With lat/lng: only stations this near"),
    connector: list[ConnectorType] = Query(default=[], description="Plug types; a station matches if it has any"),
    min_power_kw: float | None = Query(None, gt=0, description="Only chargers at least this fast"),
    max_price: float | None = Query(None, gt=0, description="Only chargers at most this price per kWh (INR)"),
    operator: str | None = Query(None, min_length=1, max_length=120, description="Only this operator's stations"),
    open_now: bool = Query(False, description="Hide stations known to be closed right now"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    center = origin_from(lat, lng)
    box = _parse_bbox(bbox) if bbox else None
    # "Near me" without an explicit area defaults to the standard recommendation radius.
    radius = radius_km if radius_km else (BOOKING_RULES.recommendation_radius_km if center and not box else None)
    query = StationQuery(
        bbox=box, center=center, radius_km=radius if center else None,
        connectors=list(connector), min_power_kw=min_power_kw, max_price_per_kwh=max_price,
        operator=operator, limit=limit,
    )
    try:
        return service.search(db, SearchFilters(query=query, open_now=open_now), _now())
    except SQLAlchemyError as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Charging station data is temporarily unavailable.") from exc


@router.get("/count", response_model=StationCount)
def count_stations(db: Session = Depends(get_db)):
    """How many stations are on the map (shown on the landing page)."""
    try:
        return StationCount(count=repository.count_stations(db))
    except SQLAlchemyError as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Charging station data is temporarily unavailable.") from exc


@router.get("/{station_id}", response_model=StationDetail)
def get_station(
    station_id: UUID,
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    return service.detail(db, station_id, _now(), origin_from(lat, lng))


@router.post(
    "",
    response_model=StationDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_station(payload: StationCreate, db: Session = Depends(get_db)):
    station = repository.create_station(db, **payload.model_dump())
    return service.detail(db, station.station_id, _now())
