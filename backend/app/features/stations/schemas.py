"""Request and response shapes for the station endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Must match the database's connector_type domain and frontend/shared/src/constants.ts.
ConnectorType = Literal["CCS2", "TYPE2", "CHADEMO", "BHARAT_AC001", "BHARAT_DC001", "TYPE1", "OTHER"]


class StationSummary(BaseModel):
    """A station with a live summary of its chargers: what the map and list show.

    When a connector or power filter is used, the charger_* and power/price fields describe
    only the chargers that match the filter (a driver with a CCS2 car sees CCS2 chargers).
    """

    station_id: UUID
    name: str
    address: str
    city: str | None = None
    latitude: float
    longitude: float
    operator_name: str | None = None
    vehicle_category: str
    opening_hours: str | None = None
    # True / False when the opening hours are understood, null when unknown (never guessed).
    is_open_now: bool | None = None
    rating: float | None = None
    rating_is_estimated: bool = False
    rating_count: int = 0
    data_source: str
    # True when any shown value was generated instead of imported ("Approximate" badge).
    has_estimated_data: bool
    charger_total: int
    charger_free: int  # usable and not booked at this moment
    connector_types: list[ConnectorType | str]
    min_power_kw: float | None = None
    max_power_kw: float | None = None
    min_price_per_kwh: float | None = None
    # Only when a search point (lat/lng) was given:
    distance_km: float | None = None
    eta_minutes_estimate: int | None = None  # straight-line estimate, not a routed time


class ChargerDetail(BaseModel):
    charger_id: UUID
    label: str
    connector_type: str
    current_type: str | None = None
    power_kw: float | None = None
    price_per_kwh: float | None = None
    status: str
    free_now: bool  # usable and not booked at this moment
    data_source: str
    is_estimated: bool  # the charger or any of its values was generated
    estimated_fields: list[str] = Field(default_factory=list)


class StationDetail(StationSummary):
    chargers: list[ChargerDetail]


class StationSearchResponse(BaseModel):
    stations: list[StationSummary]
    count: int
    limit: int
    # True when more stations matched than the limit allowed: zoom in or add a filter.
    truncated: bool


class StationCount(BaseModel):
    count: int


class StationCreate(BaseModel):
    """Admins add stations by hand; they are tagged data_source = 'manual'."""

    name: str = Field(min_length=1)
    address: str = ""
    city: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    operator_id: UUID | None = None
