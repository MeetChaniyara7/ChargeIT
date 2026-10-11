"""Search queries: stations, operators and cities whose names match typed text.

Matching uses pg_trgm (migration 010). A name matches when it contains the text
(ILIKE) or is similar enough to it (word similarity, which tolerates typos). Every
row comes back with a score from 0 to 1, so real matches always rank above typos:
    1.0   the name starts with the text
    0.95  the name contains it
    0.9   the station's address contains it (stations only)
    <0.9  similar spelling only
"""

from dataclasses import dataclass

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.features.stations.models import Operator, Station
from app.features.stations.repository import DEFAULT_CATEGORY

PREFIX_SCORE = 1.0
NAME_SCORE = 0.95
ADDRESS_SCORE = 0.9
CONTAINS_SCORE = ADDRESS_SCORE  # at or above this, the text really appears


@dataclass
class Match[T]:
    item: T
    score: float

    @property
    def contains_text(self) -> bool:
        return self.score >= CONTAINS_SCORE


@dataclass
class Area:
    """Stations grouped by operator or city."""

    name: str
    station_count: int
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contains(column, text: str) -> ColumnElement[bool]:
    return column.ilike(f"%{_escape_like(text)}%", escape="\\")


def _score(column, text: str, address=None) -> ColumnElement[float]:
    similarity = func.extensions.word_similarity(text, column)
    whens = [
        (column.ilike(f"{_escape_like(text)}%", escape="\\"), literal(PREFIX_SCORE)),
        (_contains(column, text), literal(NAME_SCORE)),
    ]
    if address is not None:
        whens.append((_contains(address, text), literal(ADDRESS_SCORE)))
    return case(*whens, else_=func.least(similarity, literal(CONTAINS_SCORE - 0.01)))


def _matches(column, text: str, min_similarity: float, address=None) -> ColumnElement[bool]:
    conditions = [_contains(column, text), func.extensions.word_similarity(text, column) >= min_similarity]
    if address is not None:
        conditions.append(_contains(address, text))
    return or_(*conditions)


def _visible():
    return (Station.is_active, Station.vehicle_category == DEFAULT_CATEGORY)


def find_stations(
    db: Session, text: str, min_similarity: float, limit: int, center: tuple[float, float] | None = None
) -> list[Match[Station]]:
    """Best-matching stations by name (or address), then nearest first when a point is given."""
    score = _score(Station.name, text, Station.address).label("score")
    order = [score.desc()]
    if center:
        order.append(func.haversine_km(Station.latitude, Station.longitude, center[0], center[1]))
    stmt = (
        select(Station, score)
        .where(*_visible(), _matches(Station.name, text, min_similarity, Station.address))
        .options(selectinload(Station.chargers), joinedload(Station.operator))
        .order_by(*order, Station.name, Station.station_id)
        .limit(limit)
    )
    return [Match(station, float(s)) for station, s in db.execute(stmt).unique()]


def _areas(db: Session, name_column, text: str, min_similarity: float, limit: int, *joins) -> list[Match[Area]]:
    score = func.max(_score(name_column, text)).label("score")
    stmt = select(
        name_column,
        func.count(Station.station_id),
        func.min(Station.latitude), func.max(Station.latitude),
        func.min(Station.longitude), func.max(Station.longitude),
        score,
    ).select_from(Station)
    for target, condition in joins:
        stmt = stmt.join(target, condition)
    stmt = (
        stmt.where(*_visible(), name_column.is_not(None), name_column != "", _matches(name_column, text, min_similarity))
        .group_by(name_column)
        .order_by(score.desc(), func.count(Station.station_id).desc(), name_column)
        .limit(limit)
    )
    return [
        Match(Area(name, count, min_lat, max_lat, min_lng, max_lng), float(s))
        for name, count, min_lat, max_lat, min_lng, max_lng, s in db.execute(stmt)
    ]


def find_operators(db: Session, text: str, min_similarity: float, limit: int) -> list[Match[Area]]:
    """Operators with at least one visible station, with how many they run."""
    return _areas(db, Operator.name, text, min_similarity, limit, (Operator, Station.operator_id == Operator.operator_id))


def find_cities(db: Session, text: str, min_similarity: float, limit: int) -> list[Match[Area]]:
    """Cities that have visible stations, with how many ("Ahmedabad " and "Ahmedabad" count as one)."""
    return _areas(db, func.trim(Station.city), text, min_similarity, limit)
