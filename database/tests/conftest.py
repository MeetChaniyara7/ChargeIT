"""Database tests run against TEST_DATABASE_URL, a throwaway local PostgreSQL database.

The schema is wiped and rebuilt from the migrations once per test run. Every test runs
inside a transaction that is rolled back afterwards, so tests never affect each other.
Tests that need a database are skipped when TEST_DATABASE_URL is not set.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from database import common
from database.migrate import apply_pending, reset_schema

HAS_TEST_DB = bool(os.getenv("TEST_DATABASE_URL"))
needs_db = pytest.mark.skipif(not HAS_TEST_DB, reason="TEST_DATABASE_URL not set")


@pytest.fixture(scope="session")
def migrated_db():
    if not HAS_TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    with common.connect("TEST_DATABASE_URL") as conn:
        reset_schema(conn)
        apply_pending(conn, verbose=False)
    yield


@pytest.fixture
def db(migrated_db):
    """A connection whose changes are rolled back after the test."""
    with common.connect("TEST_DATABASE_URL") as conn:
        yield conn
        conn.rollback()


# ---------- small helpers that create rows for tests ----------

T0 = datetime(2026, 10, 12, 4, 30, tzinfo=timezone.utc)  # 10:00 IST


def slot(start_offset_min: int, length_min: int) -> str:
    """A '[start, end)' range string, measured in minutes from T0."""
    start = T0 + timedelta(minutes=start_offset_min)
    end = start + timedelta(minutes=length_min)
    return f"[{start.isoformat()}, {end.isoformat()})"


def make_user(conn, email: str = "driver@test.dev") -> str:
    return conn.execute("INSERT INTO users (email) VALUES (%s) RETURNING user_id", (email,)).fetchone()[0]


def make_charger(conn) -> str:
    station_id = conn.execute(
        "INSERT INTO stations (name, latitude, longitude, data_source) "
        "VALUES ('Test station', 23.03, 72.55, 'manual') RETURNING station_id"
    ).fetchone()[0]
    return conn.execute(
        "INSERT INTO chargers (station_id, label, connector_type, current_type, power_kw, price_per_kwh, data_source) "
        "VALUES (%s, 'CCS2-1', 'CCS2', 'DC', 60, 20, 'manual') RETURNING charger_id",
        (station_id,),
    ).fetchone()[0]


def make_booking(conn, charger_id, user_id, time_range: str, status="CONFIRMED", source="INSTANT") -> str:
    """Insert a booking. INSTANT bookings may start as CONFIRMED; APP/WALK_IN start as HELD."""
    return conn.execute(
        "INSERT INTO bookings (user_id, charger_id, source, status, time_range) "
        "VALUES (%s, %s, %s, %s, %s::tstzrange) RETURNING booking_id",
        (user_id, charger_id, source, status, time_range),
    ).fetchone()[0]
