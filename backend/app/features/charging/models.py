"""Charging sessions (schema: database/migrations/006_charging.sql).

Phase 4 only READS them, to find unpaid energy bills. Starting and stopping sessions is Phase 5.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"))
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    source = Column(Text, nullable=False)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    energy_kwh = Column(Numeric(10, 3), nullable=False)
    bill_amount = Column(Numeric(10, 2))
    bill_status = Column(Text)
