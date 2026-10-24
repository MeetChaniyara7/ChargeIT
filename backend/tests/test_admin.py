"""The admin area: numbers, stations, chargers, out of service, bookings, kiosks, alerts (needs the test database).

Service functions take `now`, so most of these pretend to be at chosen moments of Monday 2026-10-12.
"""

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.features.admin import alerts as alert_helper
from app.features.admin import schemas as s
from app.features.admin import service
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.availability.service import station_availability
from app.features.bookings import service as bookings
from app.features.charging import service as charging
from app.features.kiosk import admin_router
from app.features.payments import service as payments
from app.main import app
from tests import factories
from tests.conftest import needs_db

pytestmark = needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)  # 15:30 IST
M = timedelta(minutes=1)
H = timedelta(hours=1)
WEBHOOK_SECRET = "test-razorpay-webhook-secret"


def _committed(make):
    def wrapper(db, *args, **kwargs):
        result = make(db, *args, **kwargs)
        db.commit()
        return result

    return wrapper


make_station = _committed(factories.make_station)
make_charger = _committed(factories.make_charger)
make_user = _committed(factories.make_user)
make_booking = _committed(factories.make_booking)


def add_payment(db, booking_id, amount=199, purpose="BOOKING_FEE", status="CAPTURED", refunded=0):
    session_id = None
    if purpose == "ENERGY":  # an energy payment belongs to a finished session (a database rule)
        session_id = db.execute(
            text(
                "INSERT INTO charging_sessions (booking_id, charger_id, source, started_at, ended_at, bill_amount, bill_status) "
                "SELECT booking_id, charger_id, 'BOOKING', :at, :at, :a, 'PAID' FROM bookings WHERE booking_id = :b RETURNING session_id"
            ),
            {"b": booking_id, "at": NOW, "a": amount},
        ).scalar_one()
    db.execute(
        text(
            "INSERT INTO payments (booking_id, session_id, purpose, provider_order_id, amount, status, refunded_amount, created_at) "
            "VALUES (:b, :sid, :p, :o, :a, :s, :r, :at)"
        ),
        {"b": booking_id, "sid": session_id, "p": purpose, "o": f"order_{booking_id}_{purpose}", "a": amount, "s": status, "r": refunded, "at": NOW},
    )
    db.commit()


@pytest.fixture
def world(db):
    operator = db.execute(text("INSERT INTO operators (name) VALUES ('Test Power') RETURNING operator_id")).scalar_one()
    db.commit()
    station = make_station(db, "Admin hub", 23.03, 72.55)
    db.execute(text("UPDATE stations SET operator_id = :o, city = 'Ahmedabad' WHERE station_id = :s"), {"o": operator, "s": station})
    db.commit()
    return {
        "operator": operator, "station": station,
        "a": make_charger(db, station, "CCS2", 60, 20, label="A"),
        "b": make_charger(db, station, "CCS2", 60, 20, label="B"),
        "user": make_user(db), "other": make_user(db),
    }


def confirmed(db, world, charger="a", start=NOW + 2 * H, minutes=60, paid=True):
    booking = make_booking(db, world[charger], start, start + minutes * M, user_id=world["user"])
    if paid:
        add_payment(db, booking)
    return booking


def status_of(db, booking_id):
    return db.execute(text("SELECT status FROM bookings WHERE booking_id = :b"), {"b": booking_id}).scalar_one()


def charger_status(db, charger_id):
    return db.execute(text("SELECT status FROM chargers WHERE charger_id = :c"), {"c": charger_id}).scalar_one()


# ================================================================ out of service: never silently breaking bookings

def test_a_charger_with_no_bookings_goes_out_of_service_at_once(db, world):
    result = service.set_out_of_service(db, world["a"], False, NOW)
    assert (result.status, result.cancelled, result.session_ended) == ("OUT_OF_SERVICE", 0, False)
    assert charger_status(db, world["a"]) == "OUT_OF_SERVICE"
    event = db.execute(text("SELECT event, source FROM charger_events WHERE charger_id = :c ORDER BY event_id DESC LIMIT 1"), {"c": world["a"]}).one()
    assert tuple(event) == ("OUT_OF_SERVICE", "ADMIN")


def test_future_bookings_stop_it_until_the_admin_chooses_to_cancel_them(db, world):
    booking = confirmed(db, world)
    with pytest.raises(AppError) as error:
        service.set_out_of_service(db, world["a"], False, NOW)
    assert (error.value.status_code, error.value.code, error.value.details) == (409, "HAS_FUTURE_BOOKINGS", {"count": 1})
    assert charger_status(db, world["a"]) == "AVAILABLE" and status_of(db, booking) == "CONFIRMED"  # nothing changed


def test_cancelling_them_refunds_in_full_and_tells_the_driver(db, world):
    paid, unpaid_instant = confirmed(db, world), confirmed(db, world, start=NOW + 4 * H, paid=False)
    result = service.set_out_of_service(db, world["a"], True, NOW)
    assert (result.cancelled, result.refunded_total) == (2, 199.0)
    for booking in (paid, unpaid_instant):
        assert status_of(db, booking) == "CANCELLED"
    row = db.execute(text("SELECT refund_amount, notice_kind, notice_text, cancel_reason FROM bookings WHERE booking_id = :b"), {"b": paid}).one()
    assert float(row.refund_amount) == 199.0 and row.notice_kind == "CANCELLED_NO_CHARGER"
    assert "refunded in full" in row.notice_text and "out of service" in row.cancel_reason
    payment = db.execute(text("SELECT status, refunded_amount FROM payments WHERE booking_id = :b"), {"b": paid}).one()
    assert (payment.status, float(payment.refunded_amount)) == ("REFUNDED", 199.0)
    unpaid_row = db.execute(text("SELECT refund_amount, notice_text FROM bookings WHERE booking_id = :b"), {"b": unpaid_instant}).one()
    assert float(unpaid_row.refund_amount) == 0 and "refunded" not in unpaid_row.notice_text
    history = db.execute(text("SELECT to_status, actor, reason FROM booking_events WHERE booking_id = :b ORDER BY event_id DESC LIMIT 1"), {"b": paid}).one()
    assert tuple(history) == ("CANCELLED", "ADMIN", "The charger was taken out of service")


def test_a_partly_refunded_fee_gets_only_the_rest_back(db, world):
    booking = make_booking(db, world["a"], NOW + 2 * H, NOW + 3 * H, user_id=world["user"])
    add_payment(db, booking, amount=199, status="PARTIALLY_REFUNDED", refunded=50)
    assert service.set_out_of_service(db, world["a"], True, NOW).refunded_total == 149.0
    assert float(db.execute(text("SELECT refunded_amount FROM payments WHERE booking_id = :b"), {"b": booking}).scalar_one()) == 199.0


def test_only_that_chargers_bookings_are_touched(db, world):
    on_a, on_b = confirmed(db, world, "a"), confirmed(db, world, "b")
    service.set_out_of_service(db, world["a"], True, NOW)
    assert (status_of(db, on_a), status_of(db, on_b)) == ("CANCELLED", "CONFIRMED")


def test_bookings_that_are_over_are_not_in_the_way(db, world):
    make_booking(db, world["a"], NOW - 3 * H, NOW - 2 * H, user_id=world["user"], status="CONFIRMED")
    assert service.set_out_of_service(db, world["a"], False, NOW).cancelled == 0


def test_someone_charging_is_stopped_and_billed(db, world):
    booking = make_booking(db, world["a"], NOW, NOW + H, user_id=world["user"])
    session = charging.start_session(db, booking, NOW, actor="ADMIN")
    result = service.set_out_of_service(db, world["a"], False, NOW + 30 * M)
    assert result.session_ended is True
    row = db.execute(text("SELECT end_reason, bill_amount, bill_status FROM charging_sessions WHERE session_id = :s"), {"s": session.session_id}).one()
    assert (row.end_reason, float(row.bill_amount), row.bill_status) == ("ADMIN", 540.0, "DUE")  # 60 kW x 0.9 x 30 min = 27 kWh (under the 32 kWh the default battery can take) x Rs 20
    assert status_of(db, booking) == "COMPLETED" and charger_status(db, world["a"]) == "OUT_OF_SERVICE"


def test_an_out_of_service_charger_cannot_be_booked_or_shown_free(db, world):
    service.set_out_of_service(db, world["a"], False, NOW)
    with pytest.raises(AppError) as error:
        bookings.create_hold(db, world["user"], world["a"], NOW + 3 * H, 1, None, NOW)
    assert error.value.status_code in (409, 422)
    grid = station_availability(db, world["station"], date(2026, 10, 12), NOW)
    states = {b.state for c in grid.chargers if c.charger_id == world["a"] for b in c.blocks if b.start >= NOW}
    assert states == {"OUT_OF_SERVICE"}


def test_restoring_puts_it_back_and_a_second_restore_is_refused(db, world):
    service.set_out_of_service(db, world["a"], False, NOW)
    assert service.restore_charger(db, world["a"], NOW + M).status == "AVAILABLE"
    with pytest.raises(AppError) as error:
        service.restore_charger(db, world["a"], NOW + 2 * M)
    assert error.value.code == "NOT_OUT_OF_SERVICE"


def test_a_restored_charger_with_a_booking_soon_is_reserved(db, world):
    service.set_out_of_service(db, world["a"], False, NOW)
    confirmed(db, world, start=NOW + 10 * M)
    assert service.restore_charger(db, world["a"], NOW).status == "RESERVED"


def test_a_repair_event_does_not_bring_back_an_out_of_service_charger(db, world):
    service.set_out_of_service(db, world["a"], False, NOW)
    result = db.execute(text("SELECT simulate_charger_event(:c, 'RECOVER', :now)"), {"c": world["a"], "now": NOW}).scalar_one()
    assert charger_status(db, world["a"]) == "OUT_OF_SERVICE" and result["status"] == "OUT_OF_SERVICE"


def test_setting_it_twice_changes_nothing(db, world):
    service.set_out_of_service(db, world["a"], False, NOW)
    assert service.set_out_of_service(db, world["a"], False, NOW).cancelled == 0


def test_the_affected_list_shows_who_would_be_hit(db, world):
    booking = confirmed(db, world)
    out = service.affected_by_out_of_service(db, world["a"], NOW)
    assert out.label == "A" and out.charging_now is False and len(out.bookings) == 1
    assert (out.bookings[0].booking_id, out.bookings[0].fee_paid, out.bookings[0].status) == (booking, 199.0, "CONFIRMED")
    assert out.bookings[0].user_email.endswith("@test.dev")
    assert status_of(db, booking) == "CONFIRMED"  # looking changes nothing


def test_taking_a_station_off_the_map_follows_the_same_rule(db, world):
    booking = confirmed(db, world)
    with pytest.raises(AppError) as error:
        service.update_station(db, world["station"], s.StationUpdate(is_active=False), NOW)
    assert error.value.code == "HAS_FUTURE_BOOKINGS"
    assert db.execute(text("SELECT is_active FROM stations WHERE station_id = :s"), {"s": world["station"]}).scalar_one() is True
    station = service.update_station(db, world["station"], s.StationUpdate(is_active=False, cancel_bookings=True), NOW)
    assert station.is_active is False and status_of(db, booking) == "CANCELLED"


# ================================================================ stations and chargers

def test_station_list_search_sort_and_pages(db, world):
    for i in range(5):
        make_station(db, f"Zeta {i}", 23.1, 72.6)
    everything = service.list_stations(db, None, "name", "asc", None, 1, 100)
    assert everything.total >= 6
    names = [r.name for r in everything.items]
    assert names == sorted(names)
    found = service.list_stations(db, "admin", "name", "asc", None, 1, 20)
    assert [r.name for r in found.items] == ["Admin hub"]
    assert (found.items[0].operator_name, found.items[0].charger_count, found.items[0].data_source, found.items[0].is_active) == ("Test Power", 2, "manual", True)
    assert [r.name for r in service.list_stations(db, "Test Power", "name", "asc", None, 1, 20).items] == ["Admin hub"]  # search reaches the operator
    assert [r.name for r in service.list_stations(db, "ahmedabad", "name", "asc", None, 1, 20).items] == ["Admin hub"]  # and the city
    page2 = service.list_stations(db, "zeta", "name", "desc", None, 2, 2)
    assert (page2.total, page2.page, len(page2.items)) == (5, 2, 2) and [r.name for r in page2.items] == ["Zeta 2", "Zeta 1"]


def test_station_list_sorts_by_chargers_and_filters_status(db, world):
    empty = make_station(db, "No chargers", 23.2, 72.7)
    db.execute(text("UPDATE stations SET is_active = false WHERE station_id = :s"), {"s": empty})
    db.commit()
    by_chargers = service.list_stations(db, None, "chargers", "desc", None, 1, 100).items
    assert by_chargers[0].charger_count >= by_chargers[-1].charger_count
    assert [r.name for r in service.list_stations(db, None, "name", "asc", False, 1, 100).items] == ["No chargers"]
    assert "No chargers" not in [r.name for r in service.list_stations(db, None, "name", "asc", True, 1, 100).items]
    with pytest.raises(AppError) as error:
        service.list_stations(db, None, "name; DROP TABLE stations", "asc", None, 1, 20)
    assert error.value.code == "INVALID_SORT"


def test_search_text_is_never_run_as_sql(db, world):
    assert service.list_stations(db, "%'; DROP TABLE stations; --", "name", "asc", None, 1, 20).items == []
    assert db.execute(text("SELECT count(*) FROM stations")).scalar_one() >= 1


def test_editing_a_station(db, world):
    out = service.update_station(db, world["station"], s.StationUpdate(name="  Renamed hub ", city="Surat", opening_hours="Mo-Su 06:00-22:00"), NOW)
    assert (out.name, out.city, out.opening_hours, out.operator_name, out.data_source) == ("Renamed hub", "Surat", "Mo-Su 06:00-22:00", "Test Power", "manual")
    with pytest.raises(AppError) as error:
        service.update_station(db, world["station"], s.StationUpdate(operator_id="00000000-0000-0000-0000-000000000000"), NOW)
    assert error.value.code == "OPERATOR_NOT_FOUND"
    with pytest.raises(AppError) as error:
        service.update_station(db, "00000000-0000-0000-0000-000000000000", s.StationUpdate(name="x"), NOW)
    assert error.value.code == "STATION_NOT_FOUND"


def test_adding_and_editing_chargers(db, world):
    out = service.create_charger(db, world["station"], s.ChargerCreate(label="C", connector_type="TYPE2", current_type="AC", power_kw=22, price_per_kwh=15))
    new = next(c for c in out.chargers if c.label == "C")
    assert (new.connector_type, new.power_kw, new.price_per_kwh, new.status, new.data_source) == ("TYPE2", 22.0, 15.0, "AVAILABLE", "manual")
    with pytest.raises(AppError) as error:
        service.create_charger(db, world["station"], s.ChargerCreate(label="C", connector_type="CCS2"))
    assert error.value.code == "CHARGER_LABEL_TAKEN"
    edited = service.update_charger(db, new.charger_id, s.ChargerUpdate(price_per_kwh=17.5, label="C2"))
    again = next(c for c in edited.chargers if c.charger_id == new.charger_id)
    assert (again.label, again.price_per_kwh) == ("C2", 17.5)


def test_entering_a_real_value_removes_the_approximate_tag(db, world):
    db.execute(text("UPDATE chargers SET data_source = 'synthetic', estimated_fields = ARRAY['power_kw', 'price_per_kwh'] WHERE charger_id = :c"), {"c": world["a"]})
    db.commit()
    assert service.get_station(db, world["station"]).has_estimated_data is True
    out = service.update_charger(db, world["a"], s.ChargerUpdate(power_kw=50, price_per_kwh=18))
    assert next(c for c in out.chargers if c.charger_id == world["a"]).data_source == "manual"
    assert out.has_estimated_data is False


# ================================================================ bookings list and history

def test_booking_list_filters_and_history(db, world):
    c1 = confirmed(db, world, start=NOW + 2 * H)
    c2 = make_booking(db, world["b"], NOW + 5 * H, NOW + 6 * H, user_id=world["other"])
    db.execute(text("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = :b"), {"b": c2})
    db.commit()
    everything = service.list_bookings(db, world["station"], None, None, None, 1, 20)
    assert everything.total == 2 and [b.booking_id for b in everything.items] == [c2, c1]  # newest slot first
    assert [b.booking_id for b in service.list_bookings(db, world["station"], "CONFIRMED", None, None, 1, 20).items] == [c1]
    assert service.list_bookings(db, None, None, date(2026, 10, 12), date(2026, 10, 12), 1, 20).total == 2  # both are on 12 Oct IST
    assert service.list_bookings(db, None, None, date(2026, 10, 13), None, 1, 20).total == 0
    assert service.list_bookings(db, None, None, None, date(2026, 10, 11), 1, 20).total == 0
    row = next(b for b in everything.items if b.booking_id == c1)
    assert (row.station_name, row.charger_label, row.source, row.booking_fee) == ("Admin hub", "A", "INSTANT", 0.0)
    events = service.booking_events(db, c2)
    assert events[-1].to_status == "CANCELLED" and events[-1].actor in ("USER", "SYSTEM", "ADMIN", "DEVICE")
    with pytest.raises(AppError) as error:
        service.booking_events(db, "00000000-0000-0000-0000-000000000000")
    assert error.value.code == "BOOKING_NOT_FOUND"


# ================================================================ overview and reports

def test_overview_counts_and_revenue(db, world):
    today_booking = confirmed(db, world, start=datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc))
    add_payment(db, today_booking, amount=300, purpose="ENERGY")
    make_booking(db, world["b"], NOW - 2 * H, NOW - H, user_id=world["other"], status="CONFIRMED")
    db.execute(text("UPDATE bookings SET status = 'NO_SHOW' WHERE charger_id = :c"), {"c": world["b"]})
    walk = make_booking(db, world["b"], NOW + 8 * H, NOW + 9 * H, user_id=world["other"])
    add_payment(db, walk, amount=100, purpose="WALKIN_PREPAID", refunded=40, status="PARTIALLY_REFUNDED")
    db.commit()
    out = service.overview(db, NOW)
    assert out.today_bookings == 3 and out.no_shows_week == 1 and out.active_sessions == 0
    assert (out.revenue.booking_fees, out.revenue.energy, out.revenue.walk_ins, out.revenue.refunds) == (199.0, 300.0, 60.0, 40.0)
    assert len(out.bookings_per_day) == 14 and out.bookings_per_day[-1].day == date(2026, 10, 12) and out.bookings_per_day[-1].count == 3
    assert out.no_shows_by_station[0].station_name == "Admin hub" and out.no_shows_by_station[0].count == 1


def test_report_settlement_per_operator(db, world):
    other_station = make_station(db, "Lone hub", 23.4, 72.9)
    lone = make_charger(db, other_station, "CCS2", 60, 20, label="X")
    first = confirmed(db, world, paid=False)
    add_payment(db, first, amount=500, purpose="ENERGY")
    second = make_booking(db, lone, NOW + H, NOW + 2 * H, user_id=world["other"])
    add_payment(db, second, amount=80, purpose="ENERGY")
    report = service.report(db, date(2026, 10, 12), date(2026, 10, 12))
    assert [(r.operator_name, r.energy_revenue, r.sessions) for r in report.settlement] == [("Test Power", 500.0, 1), ("No operator", 80.0, 1)]
    assert report.revenue.energy == 580.0
    assert {r.status: r.count for r in report.bookings_by_status}["CONFIRMED"] == 2
    with pytest.raises(AppError) as error:
        service.report(db, date(2026, 10, 12), date(2026, 10, 1))
    assert error.value.code == "INVALID_RANGE"
    with pytest.raises(AppError):
        service.report(db, date(2024, 1, 1), date(2026, 10, 12))


# ================================================================ kiosks and alerts

def test_kiosks_are_listed_with_last_seen(db, world):
    device, _ = admin_router.create_device(db, world["station"], "Door kiosk")
    rows = service.list_devices(db)
    row = next(r for r in rows if r.device_id == device.device_id)
    assert (row.station_name, row.name, row.is_active, row.last_seen_at) == ("Admin hub", "Door kiosk", True, None)
    assert row.key_prefix and "hash" not in row.model_dump_json()


def test_alerts_can_be_listed_and_marked_seen(db, world):
    assert alert_helper.raise_alert(db, "WEBHOOK_FAILED", "Something failed.", {"x": 1}, station_id=world["station"]) is True
    assert alert_helper.raise_alert(db, "WEBHOOK_FAILED", "Something failed.") is False  # the same alert is not repeated within 10 minutes
    listed = service.list_alerts(db, False)
    assert len(listed) == 1 and listed[0].station_name == "Admin hub" and listed[0].details == {"x": 1}
    seen = service.mark_alert_seen(db, listed[0].alert_id, NOW)
    assert seen.resolved_at == NOW
    assert service.list_alerts(db, False) == [] and len(service.list_alerts(db, True)) == 1
    assert alert_helper.raise_alert(db, "WEBHOOK_FAILED", "Something failed.") is True  # once seen, a new one may be raised
    with pytest.raises(AppError) as error:
        service.mark_alert_seen(db, "00000000-0000-0000-0000-000000000000", NOW)
    assert error.value.code == "ALERT_NOT_FOUND"


def test_a_bad_webhook_signature_raises_one_alert(db, world):
    for _ in range(3):
        with pytest.raises(AppError) as error:
            payments.handle_webhook(db, b"{}", "not-a-signature", None, NOW)
        assert error.value.code == "INVALID_SIGNATURE"
    alerts = service.list_alerts(db, False)
    assert len(alerts) == 1 and alerts[0].kind == "WEBHOOK_FAILED" and alerts[0].details["reason"] == "INVALID_SIGNATURE"


def test_a_webhook_that_fails_midway_is_undone_and_raises_an_alert(db, world, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("the database hiccuped")

    monkeypatch.setattr(payments, "confirm_payment", broken)
    booking = make_booking(db, world["a"], NOW + 2 * H, NOW + 3 * H, user_id=world["user"], status="HELD", hold_expires_at=NOW + H)
    add_payment(db, booking, status="CREATED")
    order = f"order_{booking}_BOOKING_FEE"
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_x", "order_id": order}}}}).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    with pytest.raises(RuntimeError):
        payments.handle_webhook(db, body, signature, "evt_broken", NOW)
    assert db.execute(text("SELECT count(*) FROM webhook_events WHERE provider_event_id = 'evt_broken'")).scalar_one() == 0  # so Razorpay retry is processed afresh
    alerts = service.list_alerts(db, False)
    assert len(alerts) == 1 and "payment.captured" in alerts[0].message and "hiccuped" in alerts[0].details["error"]


# ================================================================ edge cases around bookings

def test_a_booking_across_midnight_india_time_shows_on_both_days(db, world):
    start = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)  # 23:30 IST on 12 October
    held = bookings.create_hold(db, world["user"], world["a"], start, 2, None, NOW)  # ends 00:30 IST on 13 October
    assert (held.start, held.end) == (start, start + H)
    day1 = station_availability(db, world["station"], date(2026, 10, 12), NOW)
    day2 = station_availability(db, world["station"], date(2026, 10, 13), NOW)
    a1 = next(c for c in day1.chargers if c.charger_id == world["a"]).blocks
    a2 = next(c for c in day2.chargers if c.charger_id == world["a"]).blocks
    assert a1[-1].start == start and a1[-1].state == "HELD" and len(a1) == 48  # 23:30 to 24:00 on the first day
    assert a2[0].start == start + 30 * M and a2[0].state == "HELD" and a2[1].state == "FREE"  # 00:00 to 00:30 on the second
    with pytest.raises(AppError) as error:  # nobody else can take either half
        bookings.create_hold(db, world["other"], world["a"], start + 30 * M, 1, None, NOW)
    assert error.value.code == "SLOT_TAKEN"


def test_deleting_a_vehicle_keeps_its_bookings_and_charging_works(db, world):
    from app.features.vehicles import service as vehicles
    from app.features.vehicles.schemas import VehicleIn

    vehicle = vehicles.create(db, world["user"], VehicleIn(nickname="Old car", connector_type="CCS2", battery_kwh=100, is_default=True))
    booking = make_booking(db, world["a"], NOW, NOW + H, user_id=world["user"])
    db.execute(text("UPDATE bookings SET vehicle_id = :v WHERE booking_id = :b"), {"v": vehicle.vehicle_id, "b": booking})
    db.commit()
    vehicles.delete(db, world["user"], vehicle.vehicle_id)
    row = db.execute(text("SELECT status, vehicle_id FROM bookings WHERE booking_id = :b"), {"b": booking}).one()
    assert (row.status, row.vehicle_id) == ("CONFIRMED", None)  # the booking stays; only the link to the car goes
    session = charging.start_session(db, booking, NOW, actor="ADMIN")
    live = charging.get_session(db, world["user"], session.session_id, NOW + 30 * M)
    assert live.energy_kwh == 27.0 and live.battery_percent == 87.5  # the default 40 kWh battery from 20%: 20 + 27/40


# ================================================================ over HTTP

def as_user(user_id, role="USER"):
    app.dependency_overrides[get_current_user] = lambda: User(user_id=user_id, email="x@test.dev", role=role)


ADMIN_ROUTES = [
    ("get", "/api/admin/overview"), ("get", "/api/admin/reports"), ("get", "/api/admin/operators"), ("get", "/api/admin/stations"),
    ("get", "/api/admin/stations/{station}"), ("patch", "/api/admin/stations/{station}"), ("post", "/api/admin/stations/{station}/chargers"),
    ("patch", "/api/admin/chargers/{a}"), ("get", "/api/admin/chargers/{a}/affected"), ("post", "/api/admin/chargers/{a}/out-of-service"),
    ("post", "/api/admin/chargers/{a}/restore"), ("get", "/api/admin/chargers/{a}/events"), ("get", "/api/admin/bookings"),
    ("get", "/api/admin/devices"), ("get", "/api/admin/alerts"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_http_every_admin_route_needs_the_admin_role_on_the_server(db_client, world, method, path):
    path = path.format(**{k: str(v) for k, v in world.items()})
    as_user(world["user"], role="USER")
    assert db_client.request(method.upper(), path, json={}).status_code == 403
    app.dependency_overrides.pop(get_current_user)
    assert db_client.request(method.upper(), path, json={}).status_code == 401


def test_http_out_of_service_flow(db_client, db, world):
    now = datetime.now(timezone.utc)
    booking = make_booking(db, world["a"], now + 2 * H, now + 3 * H, user_id=world["user"])
    add_payment(db, booking)
    as_user(world["other"], role="ADMIN")
    affected = db_client.get(f"/api/admin/chargers/{world['a']}/affected").json()
    assert affected["label"] == "A" and len(affected["bookings"]) == 1 and affected["bookings"][0]["fee_paid"] == 199.0
    refused = db_client.post(f"/api/admin/chargers/{world['a']}/out-of-service", json={})
    assert (refused.status_code, refused.json()["error"]["code"], refused.json()["error"]["details"]["count"]) == (409, "HAS_FUTURE_BOOKINGS", 1)
    done = db_client.post(f"/api/admin/chargers/{world['a']}/out-of-service", json={"cancel_bookings": True}).json()
    assert (done["status"], done["cancelled"], done["refunded_total"]) == ("OUT_OF_SERVICE", 1, 199.0)
    assert db_client.post(f"/api/admin/chargers/{world['a']}/restore").json()["status"] == "AVAILABLE"
    log = db_client.get(f"/api/admin/chargers/{world['a']}/events?limit=5").json()
    assert [e["event"] for e in log][:2] == ["RESTORE", "OUT_OF_SERVICE"]


def test_http_validation_errors(db_client, world):
    as_user(world["user"], role="ADMIN")
    assert db_client.patch(f"/api/admin/stations/{world['station']}", json={"latitude": 123}).status_code == 422
    assert db_client.patch(f"/api/admin/stations/{world['station']}", json={"name": ""}).status_code == 422
    assert db_client.post(f"/api/admin/stations/{world['station']}/chargers", json={"label": "Z", "connector_type": "NOPE"}).status_code == 422
    assert db_client.post(f"/api/admin/stations/{world['station']}/chargers", json={"label": "Z", "connector_type": "CCS2", "power_kw": -5}).status_code == 422
    assert db_client.get("/api/admin/stations?page_size=1000").status_code == 422
    assert db_client.get("/api/admin/stations?sort=password").json()["error"]["code"] == "INVALID_SORT"
    assert db_client.get("/api/admin/bookings?status=BOGUS").status_code == 422
    assert db_client.get(f"/api/admin/stations/{'0' * 8}-0000-0000-0000-{'0' * 12}").status_code == 404


def test_http_overview_and_lists_work(db_client, world):
    as_user(world["user"], role="ADMIN")
    overview = db_client.get("/api/admin/overview").json()
    assert set(overview) >= {"today_bookings", "active_sessions", "no_shows_week", "revenue", "bookings_per_day", "no_shows_by_station"}
    assert len(db_client.get("/api/admin/stations?q=admin").json()["items"]) == 1
    assert db_client.get("/api/admin/operators").json()[0]["name"]
    assert db_client.get("/api/admin/reports").status_code == 200
    assert db_client.get("/api/admin/alerts").json() == []
