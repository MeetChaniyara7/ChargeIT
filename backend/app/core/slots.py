"""30-minute booking slots and India-time (IST) days.

Everything is stored in UTC, but people think in IST: "today" and "4:30 PM" mean IST.
India has no daylight saving, so IST is a fixed UTC+05:30 and no time-zone database is
needed. Because 5:30 is a whole number of half-hours, slot boundaries (:00 and :30) are
the same in IST and in UTC, so alignment can be checked on the UTC timestamp directly.
"""

from datetime import date, datetime, time, timedelta, timezone

from app.config import BOOKING_RULES

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
SLOT = timedelta(minutes=BOOKING_RULES.slot_minutes)
SLOTS_PER_DAY = int(timedelta(days=1) / SLOT)


def ist_date(moment: datetime) -> date:
    """The IST calendar date of an instant (naive datetimes are treated as UTC)."""
    return as_utc(moment).astimezone(IST).date()


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def ist_day_start(day: date) -> datetime:
    """Midnight at the start of an IST day, as a UTC timestamp."""
    return datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)


def day_blocks(day: date) -> list[tuple[datetime, datetime]]:
    """Every slot of an IST day as (start, end) UTC pairs: 48 of them for 30-minute slots."""
    start = ist_day_start(day)
    return [(start + i * SLOT, start + (i + 1) * SLOT) for i in range(SLOTS_PER_DAY)]


def is_slot_aligned(moment: datetime) -> bool:
    """True when the time is exactly on a slot boundary (e.g. 4:00 or 4:30, no seconds)."""
    return int(as_utc(moment).timestamp()) % int(SLOT.total_seconds()) == 0 and as_utc(moment).microsecond == 0


def floor_to_slot(moment: datetime) -> datetime:
    """Round down to the start of the slot containing the time: 4:47 -> 4:30."""
    utc = as_utc(moment)
    seconds = int(utc.timestamp())
    step = int(SLOT.total_seconds())
    return datetime.fromtimestamp(seconds - seconds % step, tz=timezone.utc)


def ceil_to_slot(moment: datetime) -> datetime:
    """Round up to the next slot boundary (unchanged if already on one): 4:47 -> 5:00."""
    floored = floor_to_slot(moment)
    return floored if floored == as_utc(moment) else floored + SLOT
