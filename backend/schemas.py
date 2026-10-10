from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

# 1. User Schemas
class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    pass

class GoogleLoginRequest(BaseModel):
    credential: str

class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserSync(BaseModel):
    user_id: UUID
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserResponse(UserBase):
    user_id: UUID
    google_user_id: Optional[str] = None
    role: str = "USER"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# 2. Operator Schemas
class OperatorBase(BaseModel):
    name: str
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None

class OperatorCreate(OperatorBase):
    pass

class OperatorResponse(OperatorBase):
    operator_id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 3. Connector Schemas
class ConnectorBase(BaseModel):
    connector_type: str = "CCS2"
    power_kw: float = 50.0
    price_per_kwh: float = 15.0
    status: str = "AVAILABLE"

class ConnectorCreate(ConnectorBase):
    charger_id: UUID

class ConnectorResponse(ConnectorBase):
    connector_id: UUID
    charger_id: UUID

    class Config:
        from_attributes = True

# 4. Charger Schemas
class ChargerBase(BaseModel):
    charger_code: Optional[str] = None
    status: str = "AVAILABLE"

class ChargerCreate(ChargerBase):
    station_id: UUID

class ChargerResponse(ChargerBase):
    charger_id: UUID
    station_id: UUID
    connectors: List[ConnectorResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

# 5. Station Schemas
class StationBase(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    is_active: bool = True

class StationCreate(StationBase):
    operator_id: Optional[UUID] = None

class StationResponse(StationBase):
    station_id: UUID
    operator_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    chargers: List[ChargerResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

# 6. Reservation Schemas
class ReservationCreate(BaseModel):
    user_id: UUID
    charger_id: UUID
    connector_id: Optional[UUID] = None
    start_time: datetime
    end_time: datetime

class ReservationResponse(BaseModel):
    reservation_id: UUID
    user_id: UUID
    charger_id: UUID
    connector_id: Optional[UUID] = None
    reservation_date: Optional[datetime] = None
    start_time: datetime
    end_time: datetime
    status: str

    class Config:
        from_attributes = True

# 7. Charging Session Schemas
class ChargingSessionCreate(BaseModel):
    user_id: UUID
    charger_id: UUID
    reservation_id: Optional[UUID] = None

class ChargingSessionResponse(BaseModel):
    session_id: UUID
    user_id: UUID
    charger_id: UUID
    reservation_id: Optional[UUID] = None
    kwh_consumed: float
    total_cost: float
    session_start: datetime
    session_end: Optional[datetime] = None
    status: str

    class Config:
        from_attributes = True
