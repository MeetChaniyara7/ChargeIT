"""GET /api/geocode?q=...: turns a place name into coordinates for the map."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.geocoding import service
from app.features.geocoding.schemas import GeocodeResponse

# Only signed-in users: it forwards searches to a free public service with strict limits.
router = APIRouter(prefix="/api/geocode", tags=["Geocoding"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=GeocodeResponse)
def geocode(q: str = Query(..., min_length=2, max_length=200, description="A place, e.g. 'Bopal, Ahmedabad'"), db: Session = Depends(get_db)):
    return service.geocode(db, q)
