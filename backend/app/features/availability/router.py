"""GET /api/stations/{id}/availability: the slot grid the station page draws."""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.slots import ist_date
from app.db import get_db
from app.features.availability import service
from app.features.availability.schemas import StationAvailability

router = APIRouter(prefix="/api/stations", tags=["Availability"])


@router.get("/{station_id}/availability", response_model=StationAvailability)
def get_availability(
    station_id: UUID,
    day: date | None = Query(None, alias="date", description="India-time day, YYYY-MM-DD (default: today)"),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    return service.station_availability(db, station_id, day or ist_date(now), now)
