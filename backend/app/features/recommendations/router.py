"""GET /api/recommendations: "best station" suggestions for a signed-in driver."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.recommendations import service
from app.features.recommendations.schemas import RecommendationResponse
from app.features.stations.schemas import ConnectorType

# Only signed-in users: each request may call the free public routing server.
router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=RecommendationResponse)
def get_recommendations(
    lat: float = Query(..., ge=-90, le=90, description="Where the driver is (or the map centre)"),
    lng: float = Query(..., ge=-180, le=180),
    connector: list[ConnectorType] = Query(default=[], description="Plug types the car can use; empty = any"),
    start: datetime | None = Query(None, description="When charging should start (default: now)"),
    duration: int = Query(60, description="Minutes, in steps of 30"),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return service.recommend(
        db, lat=lat, lng=lng, connectors=list(connector), start=start or now,
        duration_minutes=duration, now=now,
    )

