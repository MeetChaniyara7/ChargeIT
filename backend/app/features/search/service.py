"""Suggestions for the Explore search box, from our own database only.

Places (Nominatim) are NOT searched here: its usage policy forbids search-as-you-type,
so the web app calls /api/geocode only when the user presses Enter.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import SEARCH_RULES
from app.features.availability.occupancy import busy_right_now
from app.features.search import repository
from app.features.search.schemas import AreaSuggestion, SuggestResponse
from app.features.stations.service import build_summary


def normalize(text: str) -> str:
    """Trim and collapse spaces: "  tata   power " -> "tata power"."""
    return " ".join(text.split())


def _area(area: repository.Area) -> AreaSuggestion:
    return AreaSuggestion(
        name=area.name,
        station_count=area.station_count,
        latitude=(area.min_lat + area.max_lat) / 2,
        longitude=(area.min_lng + area.max_lng) / 2,
        bbox=[area.min_lat, area.max_lat, area.min_lng, area.max_lng],
    )


def did_you_mean(*sections: list[repository.Match]) -> str | None:
    """The most similar name, but only when nothing actually contains the typed text.

    On a tie the earlier section wins, so pass operators and cities before stations:
    "Tata Power" is a better answer to "tata powr" than one of its station names.
    """
    matches = [m for section in sections for m in section]
    if not matches or any(m.contains_text for m in matches):
        return None
    best = max(matches, key=lambda m: m.score)
    return best.item.name if best.score >= SEARCH_RULES.did_you_mean_similarity else None


def suggest(db: Session, text: str, now: datetime, origin: tuple[float, float] | None = None) -> SuggestResponse:
    q = normalize(text)
    rules = SEARCH_RULES
    stations = repository.find_stations(db, q, rules.match_similarity, rules.max_stations, origin)
    operators = repository.find_operators(db, q, rules.match_similarity, rules.max_operators)
    cities = repository.find_cities(db, q, rules.match_similarity, rules.max_cities)

    busy = busy_right_now(db, [c.charger_id for m in stations for c in m.item.chargers], now)  # one query
    return SuggestResponse(
        query=q,
        stations=[build_summary(m.item, m.item.chargers, busy, now, origin) for m in stations],
        operators=[_area(m.item) for m in operators],
        cities=[_area(m.item) for m in cities],
        did_you_mean=did_you_mean(operators, cities, stations),
    )
