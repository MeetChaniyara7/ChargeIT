"""Station tables (schema: database/migrations/003_stations_chargers.sql)."""

from sqlalchemy import ARRAY, Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class Operator(Base):
    __tablename__ = "operators"

    operator_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(Text, nullable=False, unique=True)
    website = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Station(Base):
    __tablename__ = "stations"

    station_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(Text, nullable=False)
    address = Column(Text, nullable=False, server_default="")
    city = Column(Text)
    state = Column(Text)
    postcode = Column(Text)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operators.operator_id"))
    vehicle_category = Column(Text, nullable=False, server_default="FOUR_WHEELER")
    amenities = Column(ARRAY(Text), nullable=False, server_default="{}")
    opening_hours = Column(Text)
    rating = Column(Numeric(2, 1))
    rating_count = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    data_source = Column(Text, nullable=False)
    estimated_fields = Column(ARRAY(Text), nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    operator = relationship("Operator")
    chargers = relationship("Charger", back_populates="station", order_by="Charger.label")

    @property
    def operator_name(self) -> str | None:
        return self.operator.name if self.operator else None

    @property
    def has_estimated_data(self) -> bool:
        """True when any shown value was generated: drives the "approximate data" badge."""
        return bool(self.estimated_fields) or any(c.is_estimated for c in self.chargers)


class Charger(Base):
    __tablename__ = "chargers"

    charger_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id"), nullable=False)
    label = Column(Text, nullable=False)
    connector_type = Column(Text, nullable=False)
    current_type = Column(Text)
    power_kw = Column(Numeric(6, 1))
    price_per_kwh = Column(Numeric(6, 2))
    status = Column(Text, nullable=False, server_default="AVAILABLE")
    data_source = Column(Text, nullable=False)
    estimated_fields = Column(ARRAY(Text), nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="chargers")

    @property
    def is_estimated(self) -> bool:
        return self.data_source == "synthetic" or bool(self.estimated_fields)
