"""Station endpoints. Reading is public (the map works before login); creating needs an admin."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db import get_db
from app.features.auth.dependencies import require_admin
from app.features.stations import repository
from app.features.stations.schemas import StationCreate, StationResponse

router = APIRouter(prefix="/api/stations", tags=["Stations"])


@router.get("", response_model=list[StationResponse])
def list_stations(db: Session = Depends(get_db)):
    try:
        return repository.list_stations(db)
    except SQLAlchemyError as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Charging station data is temporarily unavailable.") from exc


@router.get("/{station_id}", response_model=StationResponse)
def get_station(station_id: UUID, db: Session = Depends(get_db)):
    station = repository.get_station(db, station_id)
    if not station:
        raise AppError(404, "STATION_NOT_FOUND", "Station not found.")
    return station


@router.post(
    "",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_station(payload: StationCreate, db: Session = Depends(get_db)):
    return repository.create_station(db, **payload.model_dump())
