"""What to offer when someone's slot was just taken (docs/architecture.md 5.3).

Three groups, each bookable in one tap:
1. other times on the SAME charger, close to the time they wanted;
2. other chargers at the SAME station with the same plug, free for the exact time;
3. the best nearby stations from the recommendation engine.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import BOOKING_RULES
from app.core.slots import SLOT, as_utc
from app.features.availability.occupancy import UNUSABLE_STATUSES, bookings_overlapping, busy_charger_ids
from app.features.bookings.schemas import (
    Alternatives, ChargerAlternative, SlotAlternative, StationAlternative,
)
from app.features.stations.models import Charger

logger = logging.getLogger(__name__)


def free_starts_near(
    busy: list[tuple[datetime, datetime]], wanted_start: datetime, blocks: int, now: datetime, limit: int, *, usable: bool = True
) -> list[SlotAlternative]:
    """Start times (aligned to 30 minutes) near `wanted_start` where `blocks` blocks fit between `busy` windows.

    Pure function: `busy` is the list of (start, end) windows already taken on the charger.
    Nearest in time first; the requested time itself is not offered.
    """
    if not usable:
        return []
    wanted = as_utc(wanted_start)
    length = blocks * SLOT
    latest = as_utc(now) + timedelta(days=BOOKING_RULES.max_days_ahead)
    steps = int(timedelta(hours=BOOKING_RULES.alternative_search_hours) / SLOT)
    candidates = []
    for i in range(-steps, steps + 1):
        start = wanted + i * SLOT
        end = start + length
        if i == 0 or start <= as_utc(now) or start >= latest:
            continue
        if any(b_start < end and b_end > start for b_start, b_end in busy):
            continue
        candidates.append((abs(i), i, start, end))
    candidates.sort()  # nearest first; of two equally near, the earlier one
    return [SlotAlternative(start=s, end=e) for _, _, s, e in candidates[:limit]]


def build(db: Session, charger: Charger, start: datetime, blocks: int, now: datetime, *, with_stations: bool = True) -> Alternatives:
    limit = BOOKING_RULES.max_alternatives_per_group
    start = as_utc(start)
    end = start + blocks * SLOT
    horizon = timedelta(hours=BOOKING_RULES.alternative_search_hours)

    # 1. Same charger, nearby times: ONE query for everything around the requested time.
    around = bookings_overlapping(db, [charger.charger_id], start - horizon - SLOT, end + horizon, now)
    same = free_starts_near(
        [(b_start, b_end) for _, _, b_start, b_end in around], start, blocks, now, limit,
        usable=charger.status not in UNUSABLE_STATUSES,
    )

    # 2. Other chargers here with the same plug, free for the exact window: ONE query.
    others = [
        c for c in charger.station.chargers
        if c.charger_id != charger.charger_id and c.connector_type == charger.connector_type and c.status not in UNUSABLE_STATUSES
    ]
    busy = busy_charger_ids(db, [c.charger_id for c in others], start, end, now)
    other_chargers = [
        ChargerAlternative(
            charger_id=c.charger_id, label=c.label, connector_type=c.connector_type,
            power_kw=float(c.power_kw) if c.power_kw is not None else None,
            price_per_kwh=float(c.price_per_kwh) if c.price_per_kwh is not None else None,
            start=start, end=end,
        )
        for c in others if c.charger_id not in busy
    ][:limit]

    # 3. Nearby stations: reuse the recommendation engine, but never fail the request if it can't answer.
    stations: list[StationAlternative] = []
    if with_stations:
        try:
            from app.features.recommendations import service as recommendations

            result = recommendations.recommend(
                db, lat=charger.station.latitude, lng=charger.station.longitude, connectors=[charger.connector_type],
                start=start, duration_minutes=blocks * BOOKING_RULES.slot_minutes, now=now,
            )
            for rec in result.results:
                if rec.station.station_id == charger.station_id:
                    continue
                stations.append(
                    StationAlternative(
                        station_id=rec.station.station_id, name=rec.station.name, distance_km=rec.distance_km,
                        travel_minutes=rec.travel_minutes, reason=rec.reason, start=result.window_start, end=result.window_end,
                    )
                )
        except Exception:  # alternatives are a courtesy; the 409 itself must always go out
            logger.exception("Could not build station alternatives")
            db.rollback()
    return Alternatives(
        charger_id=charger.charger_id, blocks=blocks, same_charger=same, other_chargers=other_chargers, stations=stations[:limit],
    )
