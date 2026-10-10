"""Station tables as they exist in the current database.

These map to the hand-edited schema, so some attribute names differ from column names
(Station.name is stored in `station_name`, Charger.charger_code in `charger_number`).
Phase 2 replaces this with the migrated schema from docs/architecture.md section 5.
"""

import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class Operator(Base):
    __tablename__ = "operators"

    operator_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stations = relationship("Station", back_populates="operator")


class Station(Base):
    __tablename__ = "stations"

    station_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column("station_name", String(255), nullable=False)
    address = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.operator_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # The current table has no is_active column; every station counts as active until Phase 2.
    @property
    def is_active(self) -> bool:
        return True

    operator = relationship("Operator", back_populates="stations")
    chargers = relationship("Charger", back_populates="station", cascade="all, delete-orphan")


class Charger(Base):
    __tablename__ = "chargers"

    charger_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id"), nullable=False)
    charger_code = Column("charger_number", String(50), nullable=True)
    status = Column(String(50), nullable=False, default="AVAILABLE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="chargers")
    connectors = relationship("Connector", back_populates="charger", cascade="all, delete-orphan")


class Connector(Base):
    __tablename__ = "connectors"

    connector_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    connector_type = Column(String(50), nullable=False, default="CCS2")
    power_kw = Column(Float, nullable=False, default=50.0)
    price_per_kwh = Column(Float, nullable=False, default=15.0)
    status = Column(String(50), nullable=False, default="AVAILABLE")

    charger = relationship("Charger", back_populates="connectors")
