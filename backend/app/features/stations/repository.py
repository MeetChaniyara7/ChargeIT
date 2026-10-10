"""Database queries for stations."""

from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.features.stations.models import Station

# The app is car-focused for now; two-wheeler stations stay in the database for a future section.
DEFAULT_CATEGORY = "FOUR_WHEELER"


def _with_details(db: Session):
    # Chargers load in one extra query for all stations, instead of one query per station.
    return db.query(Station).options(selectinload(Station.chargers), joinedload(Station.operator))


def list_stations(db: Session, vehicle_category: str = DEFAULT_CATEGORY) -> list[Station]:
    """Active stations for one vehicle category. (Phase 3 adds map-area and radius filters.)"""
    return (
        _with_details(db)
        .filter(Station.is_active, Station.vehicle_category == vehicle_category)
        .order_by(Station.name)
        .all()
    )


def get_station(db: Session, station_id: UUID) -> Station | None:
    return _with_details(db).filter(Station.station_id == station_id).first()


def create_station(db: Session, **fields) -> Station:
    station = Station(**fields, data_source="manual")
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
