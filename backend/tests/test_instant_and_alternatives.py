"""Pure logic: the "Charge now" window and the alternative times offered when a slot is taken."""

from datetime import datetime, timedelta, timezone

from app.features.bookings.alternatives import free_starts_near
from app.features.bookings.instant import instant_window

NOW = datetime(2026, 10, 12, 10, 7, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def test_instant_window_without_a_later_booking_is_two_hours():
    assert instant_window(NOW, None) == (NOW, NOW + 120 * M)


def test_instant_window_stops_five_minutes_before_the_next_booking():
    assert instant_window(NOW, NOW + 60 * M) == (NOW, NOW + 55 * M)


def test_a_booking_more_than_two_hours_away_does_not_shorten_it():
    assert instant_window(NOW, NOW + 300 * M) == (NOW, NOW + 120 * M)
    assert instant_window(NOW, NOW + 125 * M) == (NOW, NOW + 120 * M)  # exactly the maximum


def test_no_window_when_the_next_booking_is_too_close():
    assert instant_window(NOW, NOW + 10 * M) is None  # 5 minutes of room
    assert instant_window(NOW, NOW + 5 * M) is None
    assert instant_window(NOW, NOW + 20 * M) == (NOW, NOW + 15 * M)  # 15 minutes is the minimum


def test_naive_times_are_treated_as_utc():
    assert instant_window(datetime(2026, 10, 12, 10, 0), None)[0].tzinfo == timezone.utc


# ---- alternatives on the same charger ----

WANTED = datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc)


def at(hour, minute=0):
    return WANTED.replace(hour=hour, minute=minute)


def test_offers_the_nearest_free_times_but_not_the_requested_one():
    result = free_starts_near([(at(14), at(15))], WANTED, 2, NOW, 3)  # 1 hour wanted, 14:00-15:00 taken
    starts = [a.start for a in result]
    assert WANTED not in starts
    assert starts[0] in (at(13), at(15))  # nearest to 14:00 that fits two blocks
    assert all(a.end - a.start == timedelta(hours=1) for a in result)


def test_never_offers_a_time_that_overlaps_a_booking():
    result = free_starts_near([(at(13), at(16))], WANTED, 2, NOW, 6)
    assert result
    for alt in result:
        assert not (alt.start < at(16) and alt.end > at(13))


def test_never_offers_the_past_or_beyond_seven_days():
    soon = datetime(2026, 10, 12, 14, 10, tzinfo=timezone.utc)
    assert all(a.start > soon for a in free_starts_near([], WANTED, 1, soon, 6))
    far = WANTED + timedelta(days=7)
    assert all(a.start < soon + timedelta(days=7) for a in free_starts_near([], far, 1, soon, 6))


def test_nothing_offered_for_a_charger_out_of_service():
    assert free_starts_near([], WANTED, 1, NOW, 3, usable=False) == []


def test_limit_and_alignment():
    result = free_starts_near([], WANTED, 1, NOW, 3)
    assert len(result) == 3
    assert all(a.start.minute in (0, 30) and a.start.second == 0 for a in result)
