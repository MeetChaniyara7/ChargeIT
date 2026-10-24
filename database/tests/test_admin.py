"""Migration 015: taking a charger out of service and back, and the new alert kind, called straight in SQL."""

import pytest

from database.tests.conftest import needs_db
from database.tests.test_jobs import START, M, CCS, charger_status, make_booking, make_station, one

pytestmark = needs_db


def event(db, charger, name, at=START):
    return one(db, "SELECT apply_charger_event(%s, %s, '{}', 'ADMIN', %s)", charger, name, at)


def test_out_of_service_and_restore_are_logged_events(db):
    _, [charger] = make_station(db, CCS)
    assert event(db, charger, "OUT_OF_SERVICE") == "OUT_OF_SERVICE"
    assert charger_status(db, charger) == "OUT_OF_SERVICE"
    assert event(db, charger, "RESTORE") == "AVAILABLE"
    logged = [r[0] for r in db.execute("SELECT event FROM charger_events WHERE charger_id = %s ORDER BY event_id", (charger,))]
    assert logged == ["OUT_OF_SERVICE", "RESTORE"]


def test_a_repair_does_not_bring_back_an_out_of_service_charger(db):
    _, [charger] = make_station(db, CCS)
    event(db, charger, "OUT_OF_SERVICE")
    assert event(db, charger, "RECOVER") == "REJECTED"
    assert charger_status(db, charger) == "OUT_OF_SERVICE"


def test_restore_only_works_on_an_out_of_service_charger(db):
    _, [charger] = make_station(db, CCS)
    assert event(db, charger, "RESTORE") == "REJECTED"
    assert charger_status(db, charger) == "AVAILABLE"


def test_a_broken_or_charging_charger_can_be_taken_out_of_service(db):
    _, [a, b] = make_station(db, ("A", "CCS2", 60, 20), ("B", "CCS2", 60, 20))
    event(db, a, "FAULT")
    assert event(db, a, "OUT_OF_SERVICE") == "OUT_OF_SERVICE"
    event(db, b, "SESSION_START")
    assert event(db, b, "OUT_OF_SERVICE") == "OUT_OF_SERVICE"


def test_restore_goes_to_reserved_when_a_booking_is_about_to_start(db):
    _, [charger] = make_station(db, CCS)
    make_booking(db, charger, START + 10 * M, 60)
    event(db, charger, "OUT_OF_SERVICE")
    assert event(db, charger, "RESTORE") == "RESERVED"


def test_the_webhook_alert_kind_is_allowed_and_others_are_not(db):
    db.execute("INSERT INTO admin_alerts (kind, message) VALUES ('WEBHOOK_FAILED', 'x')")
    db.execute("INSERT INTO admin_alerts (kind, message) VALUES ('KIOSK_OTP_GUESSING', 'x')")
    with pytest.raises(Exception, match="admin_alerts_kind_check"):
        db.execute("INSERT INTO admin_alerts (kind, message) VALUES ('MADE_UP', 'x')")
