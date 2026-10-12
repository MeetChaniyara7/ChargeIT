"""How much of the booking fee comes back when a booking is cancelled (docs/architecture.md 6.3).

A pure function: no database, no clock. The tiers live in BOOKING_RULES.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.config import BOOKING_RULES
from app.core.slots import as_utc

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Refund:
    amount: Decimal  # rupees, 2 decimals
    percent: int
    reason: str  # shown to the user: why this percentage applies


def _describe(percent: int, min_minutes: int) -> str:
    hours, minutes = divmod(min_minutes, 60)
    threshold = f"{hours} hour{'s' if hours != 1 else ''}" if hours and not minutes else f"{min_minutes} minutes"
    if percent == 100:
        return f"Cancelled at least {threshold} before the start: full refund."
    if percent == 0:
        return f"Cancelled less than {_tier_floor()} minutes before the start: the booking fee is not refunded."
    return f"Cancelled at least {threshold} before the start: {percent}% refund."


def _tier_floor() -> int:
    """The smallest non-zero tier's threshold (15 minutes), used in the zero-refund message."""
    return min(t.min_minutes_before for t in BOOKING_RULES.refund_tiers if t.percent > 0)


def refund_for(cancelled_at: datetime, start: datetime, fee: Decimal | int | float | str) -> Refund:
    """The refund for cancelling at `cancelled_at` a booking that starts at `start`.

    The tier whose time limit is met wins, and the boundary counts for the driver:
    exactly 2 hours before is still 100%, exactly 30 minutes before is 75%, and
    exactly 15 minutes before is 50%.
    """
    fee = Decimal(str(fee))
    time_left = as_utc(start) - as_utc(cancelled_at)
    for tier in BOOKING_RULES.refund_tiers:  # ordered from the most generous
        if time_left >= timedelta(minutes=tier.min_minutes_before):
            amount = (fee * tier.percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
            return Refund(amount, tier.percent, _describe(tier.percent, tier.min_minutes_before))
    return Refund(Decimal("0.00"), 0, _describe(0, 0))
