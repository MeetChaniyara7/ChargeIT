"""Database queries for stations."""

import math
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.features.stations.models import Charger, Station


def _has_valid_coordinates(station: Station) -> bool:
    lat, lng = station.latitude, station.longitude
    return (
        isinstance(lat, (int, float))
        and isinstance(lng, (int, float))
        and math.isfinite(lat)
        and math.isfinite(lng)
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    )


def _with_chargers(db: Session):
    # Load chargers and their connectors in two extra queries instead of one per station.
    return db.query(Station).options(selectinload(Station.chargers).selectinload(Charger.connectors))


def list_stations(db: Session) -> list[Station]:
    """Every station that can be placed on a map. Rows with broken coordinates are skipped."""
    return [s for s in _with_chargers(db).all() if _has_valid_coordinates(s)]


def get_station(db: Session, station_id: UUID) -> Station | None:
    return _with_chargers(db).filter(Station.station_id == station_id).first()


def create_station(db: Session, **fields) -> Station:
    station = Station(**fields)
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
