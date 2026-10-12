"""The bookings table (schema: database/migrations/004_bookings.sql).

Status changes go ONLY through state_machine.transition(); the database trigger enforces the
same rules. The no-double-booking rule is the database's exclusion constraint.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import TSTZRANGE, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base

# Statuses in which a booking occupies its charger. The database's no-double-booking
# constraint applies to exactly these.
LIVE_STATUSES = ("HELD", "CONFIRMED", "ACTIVE")


class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    charger_id = Column(UUID(as_uuid=True), ForeignKey("chargers.charger_id"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.vehicle_id"))
    source = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    # One value holding the start and end, e.g. [10:00, 11:00). Always UTC.
    time_range = Column(TSTZRANGE, nullable=False)
    hold_expires_at = Column(DateTime(timezone=True))
    otp_hash = Column(Text)
    otp_used_at = Column(DateTime(timezone=True))
    booking_fee = Column(Numeric(10, 2), nullable=False, server_default="0")
    refund_amount = Column(Numeric(10, 2), nullable=False, server_default="0")
    cancelled_at = Column(DateTime(timezone=True))
    cancel_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    charger = relationship("Charger")  # queries load it explicitly (joinedload) when they need it

    @property
    def start(self):
        return self.time_range.lower

    @property
    def end(self):
        return self.time_range.upper
