"""The availability grid: booked, held, expired hold, past, out of service (needs the test database)."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from app.core.errors import AppError
from app.core.slots import IST, day_blocks
from app.features.availability import service
from tests.conftest import needs_db
from tests.factories import HOUR, make_booking, make_charger, make_station

pytestmark = needs_db

DAY = date(2026, 10, 12)  # a Monday, IST
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # 15:30 IST: blocks before this are past


def at(hhmm: str) -> datetime:
    """A time on DAY in India time, as UTC."""
    hour, minute = map(int, hhmm.split(":"))
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=IST).astimezone(timezone.utc)


def states(availability, charger_index: int = 0) -> dict[str, str]:
    """{'16:00': 'BOOKED', ...} for one charger, keyed by the block's IST start time."""
    return {b.start.astimezone(IST).strftime("%H:%M"): b.state for b in availability.chargers[charger_index].blocks}


def grid(db, station_id, now=NOW, day=DAY):
    return service.station_availability(db, station_id, day, now)


def test_one_day_has_48_blocks_per_charger_and_the_server_clock_is_included(db):
    station = make_station(db)
    make_charger(db, station)
    make_charger(db, station)
    availability = grid(db, station)
    assert [len(c.blocks) for c in availability.chargers] == [48, 48]
    assert availability.now == NOW and availability.timezone == "Asia/Kolkata" and availability.slot_minutes == 30
    assert availability.chargers[0].blocks[0].start == day_blocks(DAY)[0][0]


def test_every_state(db):
    station = make_station(db)
    booked, held, expired, broken = (make_charger(db, station, label=f"C{i}") for i in range(4))
    db.execute(text("UPDATE chargers SET status = 'FAULTED' WHERE charger_id = :c"), {"c": broken})
    make_booking(db, booked, at("17:00"), at("18:00"))                                                       # confirmed
    make_booking(db, held, at("17:00"), at("17:30"), status="HELD", hold_expires_at=NOW + timedelta(minutes=4))   # live hold
    make_booking(db, expired, at("17:00"), at("17:30"), status="HELD", hold_expires_at=NOW - timedelta(minutes=2))  # ran out
    a = grid(db, station)
    by_label = {c.label: i for i, c in enumerate(a.chargers)}

    s_booked = states(a, by_label["C0"])
    assert s_booked["17:00"] == s_booked["17:30"] == "BOOKED" and s_booked["18:00"] == "FREE"
    assert states(a, by_label["C1"])["17:00"] == "HELD"
    assert states(a, by_label["C2"])["17:00"] == "FREE"  # lazy expiry: free before any background job runs
    assert states(a, by_label["C0"])["15:00"] == "PAST"  # block ended before now (15:30)
    assert states(a, by_label["C0"])["15:30"] == "FREE"  # the block in progress is still bookable (e.g. "Charge now")
    assert set(states(a, by_label["C3"]).values()) == {"PAST", "OUT_OF_SERVICE"}  # broken charger: never free


def test_a_booking_that_starts_the_day_before_still_blocks_the_start_of_the_day(db):
    station = make_station(db)
    charger = make_charger(db, station)
    make_booking(db, charger, at("00:00") - HOUR, at("00:30") + timedelta(minutes=0))  # 23:00 yesterday to 00:30 today
    yesterday_now = at("00:00") - 2 * HOUR  # before it all, so nothing is "past" yet
    a = service.station_availability(db, station, DAY, yesterday_now)
    assert states(a)["00:00"] == "BOOKED" and states(a)["00:30"] == "FREE"


def test_a_booking_on_another_day_does_not_show(db):
    station = make_station(db)
    charger = make_charger(db, station)
    make_booking(db, charger, at("17:00") + timedelta(days=1), at("18:00") + timedelta(days=1))
    assert set(states(grid(db, station)).values()) <= {"PAST", "FREE"}


def test_cancelled_and_finished_bookings_do_not_block(db):
    station = make_station(db)
    charger = make_charger(db, station)
    booking = make_booking(db, charger, at("17:00"), at("18:00"))
    db.execute(text("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = :b"), {"b": booking})
    assert states(grid(db, station))["17:00"] == "FREE"


def test_future_day_has_no_past_blocks(db):
    station = make_station(db)
    make_charger(db, station)
    a = service.station_availability(db, station, DAY + timedelta(days=2), NOW)
    assert set(states(a).values()) == {"FREE"}


def test_dates_outside_the_booking_window_are_rejected(db):
    station = make_station(db)
    make_charger(db, station)
    with pytest.raises(AppError) as exc:
        service.station_availability(db, station, DAY + timedelta(days=8), NOW)
    assert exc.value.code == "DATE_OUT_OF_RANGE"
    with pytest.raises(AppError):
        service.station_availability(db, station, DAY - timedelta(days=2), NOW)
    service.station_availability(db, station, DAY - timedelta(days=1), NOW)  # yesterday is allowed
    service.station_availability(db, station, DAY + timedelta(days=7), NOW)  # and a week ahead


def test_unknown_station_is_not_found(db):
    with pytest.raises(AppError) as exc:
        service.station_availability(db, "00000000-0000-0000-0000-000000000000", DAY, NOW)
    assert exc.value.code == "STATION_NOT_FOUND"


def test_the_number_of_queries_does_not_depend_on_chargers_or_bookings(db):
    def queries_for(charger_count: int) -> int:
        station = make_station(db, f"Q{charger_count}")
        for _ in range(charger_count):
            charger = make_charger(db, station)
            for hour in range(8, 20, 2):
                make_booking(db, charger, at(f"{hour}:00"), at(f"{hour + 1}:00"))
        statements: list[str] = []
        engine = db.get_bind().engine if hasattr(db.get_bind(), "engine") else db.get_bind()
        record = lambda conn, cursor, statement, *a: statements.append(statement)  # noqa: E731
        event.listen(engine, "before_cursor_execute", record)
        try:
            grid(db, station)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(statements)

    assert queries_for(1) == queries_for(8)  # not one query per block or per charger


def test_http_endpoint(db_client, db):
    station = make_station(db)
    make_charger(db, station)
    today = datetime.now(timezone.utc).astimezone(IST).date()
    body = db_client.get(f"/api/stations/{station}/availability", params={"date": today.isoformat()}).json()
    assert body["date"] == today.isoformat() and len(body["chargers"][0]["blocks"]) == 48
    assert {b["state"] for b in body["chargers"][0]["blocks"]} <= {"PAST", "FREE", "BOOKED", "HELD", "OUT_OF_SERVICE"}
    assert db_client.get(f"/api/stations/{station}/availability", params={"date": "2031-01-01"}).json()["error"]["code"] == "DATE_OUT_OF_RANGE"
    assert db_client.get(f"/api/stations/{station}/availability", params={"date": "tomorrow"}).status_code == 422
    assert db_client.get("/api/stations/00000000-0000-0000-0000-000000000000/availability").status_code == 404
