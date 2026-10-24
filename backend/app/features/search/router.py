"""GET /api/search/suggest?q=...: stations, operators and cities matching what the user is typing."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import SEARCH_RULES
from app.core.errors import AppError
from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.search import repository, service
from app.features.search.schemas import OperatorChip, SuggestResponse
from app.features.stations.router import origin_from

router = APIRouter(prefix="/api/search", tags=["Search"], dependencies=[Depends(get_current_user)])


@router.get("/suggest", response_model=SuggestResponse)
def suggest(
    q: str = Query(..., max_length=SEARCH_RULES.max_query_length, description="What the user typed, e.g. 'tata power'"),
    lat: float | None = Query(None, ge=-90, le=90, description="With lng: nearer stations rank higher"),
    lng: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    if len(service.normalize(q)) < SEARCH_RULES.min_query_length:
        raise AppError(422, "QUERY_TOO_SHORT", f"Type at least {SEARCH_RULES.min_query_length} characters.")
    origin = origin_from(lat, lng)
    try:
        return service.suggest(db, q, datetime.now(timezone.utc), origin)
    except SQLAlchemyError as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Search is temporarily unavailable.") from exc


@router.get("/operators", response_model=list[OperatorChip])
def popular_operators(db: Session = Depends(get_db)):
    """The brands with the most stations: the "Brand" filter chips on the Explore page."""
    try:
        return [OperatorChip(name=n, station_count=c) for n, c in repository.top_operators(db, 8)]
    except SQLAlchemyError as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", "Search is temporarily unavailable.") from exc
