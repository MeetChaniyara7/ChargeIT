"""Response shape for search suggestions."""

from pydantic import BaseModel

from app.features.stations.schemas import StationSummary


class AreaSuggestion(BaseModel):
    """An operator or a city, with how many visible stations it has."""

    name: str
    station_count: int
    # The middle of those stations, and the area covering all of them in Nominatim's
    # order (south, north, west, east), so the map can fit them like a place.
    latitude: float
    longitude: float
    bbox: list[float]


class SuggestResponse(BaseModel):
    query: str
    stations: list[StationSummary]
    operators: list[AreaSuggestion]
    cities: list[AreaSuggestion]
    # A close spelling when nothing contains the typed text, e.g. "Tata Power" for "tata powr".
    did_you_mean: str | None = None
