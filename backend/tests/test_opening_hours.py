"""Opening hours: open / closed / unknown (never guessed)."""

from datetime import datetime, timezone

import pytest

from app.features.stations.opening_hours import is_open_now


def ist(weekday_name: str, hhmm: str) -> datetime:
    """A moment in IST on a given weekday (week of Mon 12 Oct 2026), as UTC."""
    day = {"Mo": 12, "Tu": 13, "We": 14, "Th": 15, "Fr": 16, "Sa": 17, "Su": 18}[weekday_name]
    hour, minute = map(int, hhmm.split(":"))
    from app.core.slots import IST
    return datetime(2026, 10, day, hour, minute, tzinfo=IST).astimezone(timezone.utc)


@pytest.mark.parametrize("hours", [None, "", "   "])
def test_missing_hours_are_unknown(hours):
    assert is_open_now(hours, ist("Mo", "12:00")) is None


def test_24_7_is_always_open():
    assert is_open_now("24/7", ist("Su", "03:00")) is True


@pytest.mark.parametrize("weekday, time_, expected", [
    ("Mo", "08:00", True), ("Mo", "07:59", False), ("Mo", "21:59", True), ("Mo", "22:00", False),
])
def test_plain_daily_range(weekday, time_, expected):
    assert is_open_now("08:00-22:00", ist(weekday, time_)) is expected


def test_mo_su_full_day():
    assert is_open_now("Mo-Su 00:00-24:00", ist("Sa", "23:59")) is True


@pytest.mark.parametrize("weekday, time_, expected", [
    ("Fr", "10:00", True), ("Sa", "10:00", False), ("Sa", "16:00", True), ("Su", "10:00", False), ("Mo", "20:00", False),
])
def test_day_specific_rules(weekday, time_, expected):
    assert is_open_now("Mo-Fr 09:00-18:00; Sa 16:00-20:00", ist(weekday, time_)) is expected


def test_days_not_mentioned_are_closed():
    assert is_open_now("Mo-Fr 09:00-18:00", ist("Su", "12:00")) is False


def test_later_rule_overrides_earlier_for_the_same_day():
    assert is_open_now("Mo-Su 08:00-22:00; Su off", ist("Su", "12:00")) is False
    assert is_open_now("Mo-Su 08:00-22:00; Su off", ist("Sa", "12:00")) is True


@pytest.mark.parametrize("time_, expected", [("23:00", True), ("02:00", True), ("06:00", False), ("12:00", False), ("21:59", False)])
def test_overnight_range(time_, expected):
    assert is_open_now("22:00-06:00", ist("Mo", time_)) is expected


def test_two_ranges_in_one_day():
    assert is_open_now("Mo-Sa 08:00-12:00,14:00-18:00", ist("Tu", "13:00")) is False
    assert is_open_now("Mo-Sa 08:00-12:00,14:00-18:00", ist("Tu", "15:00")) is True


def test_day_list_and_wrapping_range():
    assert is_open_now("Sa,Su 10:00-14:00", ist("Su", "11:00")) is True
    assert is_open_now("Fr-Mo 10:00-14:00", ist("Sa", "11:00")) is True   # Fri, Sat, Sun, Mon
    assert is_open_now("Fr-Mo 10:00-14:00", ist("We", "11:00")) is False


@pytest.mark.parametrize("hours", ["sunrise-sunset", "Mo-Fr 09:00-18:00; PH off", "by appointment", "Mo-Xx 09:00-18:00", "25:00-26:00"])
def test_things_we_cannot_read_are_unknown(hours):
    assert is_open_now(hours, ist("Mo", "12:00")) is None
