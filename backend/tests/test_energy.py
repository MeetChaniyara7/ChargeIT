"""The energy formula: examples, and proof that Python and SQL give exactly the same answer."""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.config import BOOKING_RULES, CHARGING_RULES
from app.features.charging.energy import battery_percent, bill_amount, energy_kwh
from tests.conftest import needs_db

START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def kwh(power, minutes, battery=None, soc=None):
    return energy_kwh(power, START, START + timedelta(minutes=minutes), battery, soc)


def test_power_times_hours_times_efficiency():
    assert kwh(60, 60, battery=100) == Decimal("54.000")      # 60 kW x 1 h x 0.9
    assert kwh(7.4, 30, battery=100) == Decimal("3.330")      # 7.4 x 0.5 x 0.9
    assert kwh(22, 90, battery=100) == Decimal("29.700")


def test_the_battery_limits_what_can_go_in():
    assert kwh(60, 600, battery=50, soc=20) == Decimal("40.000")   # 50 kWh x 80% of room
    assert kwh(60, 600, battery=50, soc=100) == Decimal("0.000")   # already full


def test_without_a_vehicle_or_a_start_level_the_defaults_apply():
    assert CHARGING_RULES.default_battery_kwh == 40 and CHARGING_RULES.default_start_soc_percent == 20
    assert kwh(60, 600) == Decimal("32.000")                       # 40 kWh x 80%
    assert kwh(60, 600, soc=70) == Decimal("12.000")               # 40 kWh x 30%
    assert kwh(60, 600, battery=100) == Decimal("80.000")          # 100 kWh x 80%


def test_nothing_is_delivered_for_no_time_negative_time_or_unknown_power():
    assert kwh(60, 0) == Decimal("0.000")
    assert energy_kwh(60, START, START - HOUR) == Decimal("0.000")
    assert kwh(None, 60) == Decimal("0.000")


def test_naive_times_are_treated_as_utc():
    assert energy_kwh(60, datetime(2026, 10, 12, 10, 0), datetime(2026, 10, 12, 11, 0), battery_kwh=100) == Decimal("54.000")


def test_bill_amount():
    assert bill_amount(Decimal("54.000"), 20) == Decimal("1080.00")
    assert bill_amount(Decimal("12.345"), Decimal("17.5")) == Decimal("216.04")   # 216.0375 rounds up
    assert bill_amount(Decimal("12"), None) == Decimal("0.00")


@pytest.mark.parametrize(
    "energy, battery, soc, expected",
    [(0, 40, 20, 20.0), (8, 40, 20, 40.0), (32, 40, 20, 100.0), (50, 40, 20, 100.0), (0, None, None, 20.0), (10, 100, 50, 60.0)],
)
def test_battery_percent_rises_from_the_start_level_and_stops_at_100(energy, battery, soc, expected):
    assert battery_percent(energy, battery, soc) == expected


@needs_db
def test_job_rules_in_the_database_match_the_python_rules(db):
    """The SQL jobs read job_rules; the API reads config.py. They must never disagree."""
    rules = {name: float(value) for name, value in db.execute(text("SELECT name, value FROM job_rules")).all()}
    assert rules == {
        "reservation_lock_before_start": BOOKING_RULES.reservation_lock_before_start,
        "no_show_after_start": BOOKING_RULES.no_show_after_start,
        "buffer_before_next_booking": BOOKING_RULES.buffer_before_next_booking,
        "charging_efficiency": CHARGING_RULES.efficiency,
        "default_start_soc_percent": CHARGING_RULES.default_start_soc_percent,
        "default_battery_kwh": CHARGING_RULES.default_battery_kwh,
    }


@needs_db
def test_python_and_sql_give_the_same_energy_for_many_random_sessions(db):
    rng = random.Random(20261012)
    for _ in range(400):
        power = rng.choice([None, 3.3, 7.4, 11, 22, 25, 30, 50, 60, 120, 150, round(rng.uniform(1, 200), 1)])
        seconds = rng.choice([0, 1, 59, 60, 1799, 1800, 3600, 5400, 7200, rng.randrange(0, 40000)])
        battery = rng.choice([None, 20, 30.5, 40, 75, 100, 250])
        soc = rng.choice([None, 0, 5, 20, 33.5, 80, 99, 100])
        until = START + timedelta(seconds=seconds, microseconds=rng.choice([0, 0, 250000, 999999]))

        in_sql = db.execute(
            text("SELECT session_energy_kwh(CAST(:p AS numeric), CAST(:s AS timestamptz), CAST(:u AS timestamptz), CAST(:b AS numeric), CAST(:c AS numeric))"), {"p": power, "s": START, "u": until, "b": battery, "c": soc}
        ).scalar_one()
        in_python = energy_kwh(power, START, until, battery, soc)
        assert in_python == in_sql, (power, seconds, battery, soc, in_python, in_sql)

        price = rng.choice([None, 0, 9.5, 17.33, 20, 24.99])
        assert bill_amount(in_python, price) == db.execute(text("SELECT session_bill_amount(CAST(:e AS numeric), CAST(:p AS numeric))"), {"e": in_python, "p": price}).scalar_one()
