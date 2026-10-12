"""The time window of a "Charge now" booking (pure, so it is easy to test)."""

from datetime import datetime, timedelta

from app.config import BOOKING_RULES
from app.core.slots import as_utc


def instant_window(now: datetime, next_booking_start: datetime | None) -> tuple[datetime, datetime] | None:
    """From now until the EARLIER of (the next booking minus the buffer) and (now + the maximum).

    Returns None when there is less than the minimum useful time before the next booking.
    """
    start = as_utc(now)
    end = start + timedelta(minutes=BOOKING_RULES.instant_booking_max_minutes)
    if next_booking_start is not None:
        end = min(end, as_utc(next_booking_start) - timedelta(minutes=BOOKING_RULES.buffer_before_next_booking))
    if end - start < timedelta(minutes=BOOKING_RULES.instant_min_minutes):
        return None
    return start, end
