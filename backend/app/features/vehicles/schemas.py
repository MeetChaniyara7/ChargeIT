"""Request and response shapes for /api/me/vehicles."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.stations.schemas import ConnectorType


class VehicleIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=40, description="e.g. 'Tata Nexon EV'")
    connector_type: ConnectorType
    battery_kwh: float = Field(gt=0, le=250, description="Usable battery size in kWh")
    is_default: bool = False


class VehicleUpdate(BaseModel):
    """Every field is optional: only the ones sent are changed."""

    nickname: str | None = Field(default=None, min_length=1, max_length=40)
    connector_type: ConnectorType | None = None
    battery_kwh: float | None = Field(default=None, gt=0, le=250)
    is_default: bool | None = None


class VehicleOut(BaseModel):
    vehicle_id: UUID
    nickname: str
    connector_type: ConnectorType | str
    battery_kwh: float
    is_default: bool
    created_at: datetime | None = None
