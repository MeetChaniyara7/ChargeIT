"""The bookings table (schema: database/migrations/004_bookings.sql).

Phase 3 only READS bookings (to show what is free). Creating and changing bookings, always
through the status rules, arrives in Phase 4.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TSTZRANGE, UUID
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
    source = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    # One value holding the start and end, e.g. [10:00, 11:00). Always UTC.
    time_range = Column(TSTZRANGE, nullable=False)
    hold_expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
