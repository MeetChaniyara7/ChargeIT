"""A user's vehicles (schema: database/migrations/002_users_vehicles.sql)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    nickname = Column(Text, nullable=False)
    connector_type = Column(Text, nullable=False)
    battery_kwh = Column(Numeric(5, 1), nullable=False)
    is_default = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
