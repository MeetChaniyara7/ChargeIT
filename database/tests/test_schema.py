"""Schema-wide safety checks."""

import pytest
from psycopg import errors

from database.tests.conftest import make_charger, make_user


def test_every_table_has_row_level_security(db):
    unprotected = db.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"
    ).fetchall()
    assert unprotected == [], f"Tables without row-level security: {unprotected}"


def test_unknown_connector_type_is_rejected(db):
    station = db.execute(
        "INSERT INTO stations (name, latitude, longitude, data_source) VALUES ('S', 23, 72, 'manual') RETURNING station_id"
    ).fetchone()[0]
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "INSERT INTO chargers (station_id, label, connector_type, data_source) VALUES (%s, 'X', 'TESLA', 'manual')",
            (station,),
        )


def test_email_is_unique_ignoring_case(db):
    make_user(db, "Meet@Example.com")
    with pytest.raises(errors.UniqueViolation):
        make_user(db, "meet@example.com")


def test_only_one_default_vehicle_per_user(db):
    user = make_user(db)
    insert = "INSERT INTO vehicles (user_id, nickname, connector_type, battery_kwh, is_default) VALUES (%s, %s, 'CCS2', 40, true)"
    db.execute(insert, (user, "Nexon"))
    with pytest.raises(errors.UniqueViolation):
        db.execute(insert, (user, "Second car"))


def test_charger_runs_only_one_session_at_a_time(db):
    charger = make_charger(db)
    insert = "INSERT INTO charging_sessions (charger_id, source) VALUES (%s, 'EXTERNAL')"
    db.execute(insert, (charger,))
    with pytest.raises(errors.UniqueViolation):
        db.execute(insert, (charger,))


def test_haversine_distance(db):
    # Ahmedabad to Gandhinagar is roughly 23-25 km in a straight line.
    km = db.execute("SELECT haversine_km(23.0225, 72.5714, 23.2156, 72.6369)").fetchone()[0]
    assert 22 < km < 25
