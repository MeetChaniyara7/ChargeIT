"""Charging sessions (schema: database/migrations/006_charging.sql)."""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"))
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    device_id = Column(UUID(as_uuid=True))
    source = Column(Text, nullable=False)  # BOOKING | WALK_IN | EXTERNAL
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    end_reason = Column(Text)
    start_soc_percent = Column(Numeric(5, 2))
    energy_kwh = Column(Numeric(10, 3), nullable=False, server_default="0")
    bill_amount = Column(Numeric(10, 2))
    bill_status = Column(Text)  # DUE | PAID | PREPAID_SETTLED
    prepaid_amount = Column(Numeric(10, 2))
    paid_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking")
    charger = relationship("Charger")
