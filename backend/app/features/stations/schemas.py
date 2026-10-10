"""Request and response shapes for the station endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    connector_id: UUID
    charger_id: UUID
    connector_type: str = "CCS2"
    power_kw: float = 50.0
    price_per_kwh: float = 15.0
    status: str = "AVAILABLE"


class ChargerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    charger_id: UUID
    station_id: UUID
    charger_code: str | None = None
    status: str = "AVAILABLE"
    connectors: list[ConnectorResponse] = Field(default_factory=list)


class StationCreate(BaseModel):
    name: str = Field(min_length=1)
    address: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    operator_id: UUID | None = None


class StationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_id: UUID
    name: str
    address: str
    latitude: float
    longitude: float
    operator_id: UUID | None = None
    is_active: bool = True
    created_at: datetime | None = None
    chargers: list[ChargerResponse] = Field(default_factory=list)
