"""Refund tiers, at and around every boundary (docs/architecture.md 6.3)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.features.bookings.refunds import refund_for

START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)


def refund(minutes_before: float, fee=199):
    return refund_for(START - timedelta(minutes=minutes_before), START, fee)


@pytest.mark.parametrize(
    "minutes_before, percent, amount",
    [
        (24 * 60, 100, "199.00"),
        (121, 100, "199.00"),
        (120, 100, "199.00"),   # exactly 2 hours: still the best tier
        (119.9, 75, "149.25"),
        (31, 75, "149.25"),
        (30, 75, "149.25"),     # exactly 30 minutes
        (29.9, 50, "99.50"),
        (16, 50, "99.50"),
        (15, 50, "99.50"),      # exactly 15 minutes
        (14.9, 0, "0.00"),
        (1, 0, "0.00"),
        (0, 0, "0.00"),
        (-30, 0, "0.00"),       # after the start
    ],
)
def test_tiers_and_boundaries(minutes_before, percent, amount):
    result = refund(minutes_before)
    assert (result.percent, result.amount) == (percent, Decimal(amount))


def test_amounts_have_two_decimals_and_round_half_up():
    assert refund(60, "199").amount == Decimal("149.25")
    assert refund(20, "199").amount == Decimal("99.50")
    assert refund(60, "101").amount == Decimal("75.75")
    assert refund(60, "0.05").amount == Decimal("0.04")  # 0.0375 -> 0.04


def test_every_result_explains_itself():
    assert "full refund" in refund(180).reason
    assert "75%" in refund(60).reason
    assert "50%" in refund(20).reason
    assert "not refunded" in refund(5).reason


def test_zero_fee_means_zero_refund():
    assert refund(180, 0).amount == Decimal("0.00")


def test_naive_times_are_treated_as_utc():
    result = refund_for(datetime(2026, 10, 12, 7, 0), datetime(2026, 10, 12, 10, 0), 199)
    assert result.percent == 100
