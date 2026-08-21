import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# 1. Users Table
class UserProfile(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_user_id = Column(String(255), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), nullable=False, server_default="USER", default="USER")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    reservations = relationship("Reservation", back_populates="user")
    sessions = relationship("ChargingSession", back_populates="user")

# 2. Operators Table
class Operator(Base):
    __tablename__ = "operators"

    operator_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stations = relationship("Station", back_populates="operator")

# 3. Stations Table
class Station(Base):
    __tablename__ = "stations"

    station_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.operator_id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    operator = relationship("Operator", back_populates="stations")
    chargers = relationship("Charger", back_populates="station", cascade="all, delete-orphan")

# 4. Chargers Table
class Charger(Base):
    __tablename__ = "chargers"

    charger_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id"), nullable=False)
    charger_code = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="AVAILABLE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="chargers")
    connectors = relationship("Connector", back_populates="charger", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="charger")
    sessions = relationship("ChargingSession", back_populates="charger")

# 5. Connectors Table
class Connector(Base):
    __tablename__ = "connectors"

    connector_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    connector_type = Column(String(50), nullable=False, default="CCS2")
    power_kw = Column(Float, nullable=False, default=50.0)
    price_per_kwh = Column(Float, nullable=False, default=15.0)
    status = Column(String(50), nullable=False, default="AVAILABLE")

    charger = relationship("Charger", back_populates="connectors")
    reservations = relationship("Reservation", back_populates="connector")

# 6. Reservations Table
class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    connector_id = Column(UUID(as_uuid=True), ForeignKey("connectors.connector_id"), nullable=True)
    reservation_date = Column(DateTime(timezone=True), server_default=func.now())
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(50), nullable=False, default="CONFIRMED")

    user = relationship("UserProfile", back_populates="reservations")
    charger = relationship("Charger", back_populates="reservations")
    connector = relationship("Connector", back_populates="reservations")
    charging_session = relationship("ChargingSession", back_populates="reservation", uselist=False)

# 7. Charging Sessions Table
class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("reservations.reservation_id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    kwh_consumed = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    session_start = Column(DateTime(timezone=True), server_default=func.now())
    session_end = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")

    user = relationship("UserProfile", back_populates="sessions")
    charger = relationship("Charger", back_populates="sessions")
    reservation = relationship("Reservation", back_populates="charging_session")
