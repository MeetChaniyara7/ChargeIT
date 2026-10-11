import datetime as dt

from pydantic import BaseModel

from app.features.stations.schemas import StationSummary


class Recommendation(BaseModel):
    # For recommendations, the station's charger_free and power/price fields describe the
    # compatible chargers that are free for the REQUESTED WINDOW (not just right now).
    station: StationSummary
    score: float  # 0 to 1, higher is better
    reason: str  # e.g. "2 CCS2 chargers free · 1.2 km · 60 kW"
    free_compatible: int
    travel_minutes: float
    # True = real road time from OSRM. False = straight-line estimate (OSRM was unavailable).
    travel_is_routed: bool
    distance_km: float


class RecommendationResponse(BaseModel):
    window_start: dt.datetime
    window_end: dt.datetime
    results: list[Recommendation]
