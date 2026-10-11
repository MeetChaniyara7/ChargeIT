"""Database queries for stations."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.geo import bbox_around
from app.features.stations.models import Charger, Operator, Station

# The app is car-focused for now; two-wheeler stations stay in the database for a future section.
DEFAULT_CATEGORY = "FOUR_WHEELER"


@dataclass
class StationQuery:
    """What to look for. All filters are optional and combine with AND."""

    bbox: tuple[float, float, float, float] | None = None  # min_lng, min_lat, max_lng, max_lat
    center: tuple[float, float] | None = None  # lat, lng: sort by distance from here
    radius_km: float | None = None  # with center: only stations within this distance
    connectors: list[str] = field(default_factory=list)  # any of these plug types
    min_power_kw: float | None = None
    max_price_per_kwh: float | None = None  # only chargers at most this price (unknown price excluded)
    operator: str | None = None  # operator name, any capitalisation
    category: str = DEFAULT_CATEGORY
    limit: int = 200


def _with_details():
    # Chargers load in ONE extra query for all stations, not one query per station.
    return (selectinload(Station.chargers), joinedload(Station.operator))


def find_stations(db: Session, q: StationQuery) -> list[Station]:
    """Matching active stations (at most limit + 1, so the caller can tell if it was cut off)."""
    stmt = (
        select(Station)
        .where(Station.is_active, Station.vehicle_category == q.category)
        .options(*_with_details())
    )

    # Cheap rectangle first (uses the index on latitude/longitude), exact circle after.
    box = q.bbox
    if q.center and q.radius_km:
        box = box or bbox_around(q.center[0], q.center[1], q.radius_km)
    if box:
        min_lng, min_lat, max_lng, max_lat = box
        stmt = stmt.where(Station.longitude.between(min_lng, max_lng), Station.latitude.between(min_lat, max_lat))

    if q.operator:
        stmt = stmt.where(
            Station.operator_id.in_(select(Operator.operator_id).where(func.lower(Operator.name) == q.operator.strip().lower()))
        )

    distance = None
    if q.center:
        distance = func.haversine_km(Station.latitude, Station.longitude, q.center[0], q.center[1])
        if q.radius_km:
            stmt = stmt.where(distance <= q.radius_km)

    charger_conditions = []
    if q.connectors:
        charger_conditions.append(Charger.connector_type.in_(q.connectors))
    if q.min_power_kw is not None:
        charger_conditions.append(Charger.power_kw >= q.min_power_kw)
    if q.max_price_per_kwh is not None:
        charger_conditions.append(Charger.price_per_kwh <= q.max_price_per_kwh)
    if charger_conditions:
        stmt = stmt.where(exists().where(Charger.station_id == Station.station_id, *charger_conditions))

    stmt = stmt.order_by(distance if distance is not None else Station.name, Station.station_id).limit(q.limit + 1)
    return list(db.scalars(stmt).unique())


def count_stations(db: Session, category: str = DEFAULT_CATEGORY) -> int:
    return db.scalar(
        select(func.count()).select_from(Station).where(Station.is_active, Station.vehicle_category == category)
    ) or 0


def get_station(db: Session, station_id: UUID) -> Station | None:
    return db.scalars(select(Station).where(Station.station_id == station_id).options(*_with_details())).unique().first()


def create_station(db: Session, **fields) -> Station:
    station = Station(**fields, data_source="manual")
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
