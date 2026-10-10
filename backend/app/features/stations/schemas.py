"""Request and response shapes for the station endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChargerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    charger_id: UUID
    label: str
    connector_type: str
    current_type: str | None = None
    power_kw: float | None = None
    price_per_kwh: float | None = None
    status: str
    data_source: str
    # True when this charger or any of its values was generated, not imported.
    is_estimated: bool


class StationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_id: UUID
    name: str
    address: str
    city: str | None = None
    latitude: float
    longitude: float
    operator_name: str | None = None
    vehicle_category: str
    opening_hours: str | None = None
    rating: float | None = None
    rating_count: int = 0
    is_active: bool
    data_source: str
    has_estimated_data: bool
    chargers: list[ChargerResponse] = Field(default_factory=list)


class StationCreate(BaseModel):
    """Admins add stations by hand; they are tagged data_source = 'manual'."""

    name: str = Field(min_length=1)
    address: str = ""
    city: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    operator_id: UUID | None = None
