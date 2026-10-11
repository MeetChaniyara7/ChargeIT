"""30-minute slots and IST days, including around midnight."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.slots import (
    IST, SLOTS_PER_DAY, ceil_to_slot, day_blocks, floor_to_slot, ist_date, ist_day_start, is_slot_aligned,
)

UTC = timezone.utc


def test_a_day_has_48_half_hour_blocks():
    blocks = day_blocks(date(2026, 10, 12))
    assert len(blocks) == SLOTS_PER_DAY == 48
    assert all(end - start == timedelta(minutes=30) for start, end in blocks)
    assert all(a_end == b_start for (_, a_end), (b_start, _) in zip(blocks, blocks[1:]))  # no gaps or overlaps


def test_ist_day_starts_at_18_30_utc_the_day_before():
    assert ist_day_start(date(2026, 10, 12)) == datetime(2026, 10, 11, 18, 30, tzinfo=UTC)
    first, last = day_blocks(date(2026, 10, 12))[0], day_blocks(date(2026, 10, 12))[-1]
    assert first[0].astimezone(IST).strftime("%H:%M") == "00:00"
    assert last[1].astimezone(IST).strftime("%Y-%m-%d %H:%M") == "2026-10-13 00:00"


def test_days_join_up_at_ist_midnight():
    today_last_end = day_blocks(date(2026, 10, 12))[-1][1]
    tomorrow_first_start = day_blocks(date(2026, 10, 13))[0][0]
    assert today_last_end == tomorrow_first_start


@pytest.mark.parametrize("utc, expected", [
    (datetime(2026, 10, 11, 18, 29, tzinfo=UTC), date(2026, 10, 11)),   # 23:59 IST on the 11th
    (datetime(2026, 10, 11, 18, 30, tzinfo=UTC), date(2026, 10, 12)),   # 00:00 IST on the 12th
    (datetime(2026, 10, 12, 0, 0, tzinfo=UTC), date(2026, 10, 12)),     # 05:30 IST
])
def test_ist_date_around_midnight(utc, expected):
    assert ist_date(utc) == expected


def test_naive_datetimes_count_as_utc():
    assert ist_date(datetime(2026, 10, 11, 18, 30)) == date(2026, 10, 12)


@pytest.mark.parametrize("minute, second, aligned", [(0, 0, True), (30, 0, True), (15, 0, False), (30, 1, False), (59, 59, False)])
def test_alignment(minute, second, aligned):
    assert is_slot_aligned(datetime(2026, 10, 12, 4, minute, second, tzinfo=UTC)) is aligned


def test_alignment_is_the_same_in_ist():
    # 04:30 IST is 23:00 UTC the day before: still on a boundary.
    assert is_slot_aligned(datetime(2026, 10, 11, 23, 0, tzinfo=UTC))


def test_rounding():
    t = datetime(2026, 10, 12, 4, 47, 12, tzinfo=UTC)
    assert floor_to_slot(t) == datetime(2026, 10, 12, 4, 30, tzinfo=UTC)
    assert ceil_to_slot(t) == datetime(2026, 10, 12, 5, 0, tzinfo=UTC)
    exact = datetime(2026, 10, 12, 5, 0, tzinfo=UTC)
    assert floor_to_slot(exact) == ceil_to_slot(exact) == exact


def test_rounding_across_midnight_ist():
    t = datetime(2026, 10, 11, 18, 10, tzinfo=UTC)  # 23:40 IST
    assert ceil_to_slot(t).astimezone(IST).strftime("%Y-%m-%d %H:%M") == "2026-10-12 00:00"
