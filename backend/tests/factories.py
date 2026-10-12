"""Small helpers that put rows into the test database."""

import itertools
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

_counter = itertools.count(1)


def make_station(
    db: Session, name: str = "Test station", lat: float = 23.03, lng: float = 72.55, *,
    category: str = "FOUR_WHEELER", active: bool = True, opening_hours: str | None = None,
    rating: float | None = None, estimated: list[str] | None = None, operator: str | None = None,
) -> UUID:
    operator_id = None
    if operator:
        operator_id = db.execute(
            text("INSERT INTO operators (name) VALUES (:n) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING operator_id"),
            {"n": operator},
        ).scalar_one()
    return db.execute(
        text(
            "INSERT INTO stations (name, address, latitude, longitude, vehicle_category, is_active, opening_hours, "
            "rating, estimated_fields, operator_id, data_source) "
            "VALUES (:name, 'Somewhere', :lat, :lng, :cat, :active, :hours, :rating, :est, :op, 'manual') RETURNING station_id"
        ),
        {"name": name, "lat": lat, "lng": lng, "cat": category, "active": active, "hours": opening_hours,
         "rating": rating, "est": estimated or [], "op": operator_id},
    ).scalar_one()


def make_charger(
    db: Session, station_id: UUID, connector: str = "CCS2", power: float | None = 60, price: float | None = 20, *,
    status: str = "AVAILABLE", label: str | None = None, data_source: str = "manual", estimated: list[str] | None = None,
) -> UUID:
    return db.execute(
        text(
            "INSERT INTO chargers (station_id, label, connector_type, power_kw, price_per_kwh, status, data_source, estimated_fields) "
            "VALUES (:sid, :label, :conn, :power, :price, :status, :src, :est) RETURNING charger_id"
        ),
        {"sid": station_id, "label": label or f"{connector}-{next(_counter)}", "conn": connector, "power": power,
         "price": price, "status": status, "src": data_source, "est": estimated or []},
    ).scalar_one()


def make_user(db: Session) -> UUID:
    return db.execute(
        text("INSERT INTO users (email) VALUES (:e) RETURNING user_id"), {"e": f"user{next(_counter)}-{uuid4().hex[:6]}@test.dev"}
    ).scalar_one()


def make_booking(
    db: Session, charger_id: UUID, start: datetime, end: datetime, *, status: str = "CONFIRMED",
    hold_expires_at: datetime | None = None, user_id: UUID | None = None,
) -> UUID:
    """Insert a booking the way the app will: INSTANT bookings may start CONFIRMED, APP bookings start HELD."""
    source = "APP" if status == "HELD" else "INSTANT"
    return db.execute(
        text(
            "INSERT INTO bookings (user_id, charger_id, source, status, time_range, hold_expires_at) "
            "VALUES (:u, :c, :src, :st, tstzrange(:s, :e, '[)'), :h) RETURNING booking_id"
        ),
        {"u": user_id or make_user(db), "c": charger_id, "src": source, "st": status, "s": start, "e": end, "h": hold_expires_at},
    ).scalar_one()


HOUR = timedelta(hours=1)


def make_due_bill(db: Session, user_id: UUID, charger_id: UUID, amount: float = 223.20) -> UUID:
    """An unpaid energy bill: a finished charging session for one of the user's bookings."""
    booking_id = db.execute(
        text(
            "INSERT INTO bookings (user_id, charger_id, source, status, time_range) "
            "VALUES (:u, :c, 'INSTANT', 'CONFIRMED', tstzrange(now() - interval '4 hours', now() - interval '3 hours', '[)')) RETURNING booking_id"
        ),
        {"u": user_id, "c": charger_id},
    ).scalar_one()
    db.execute(text("UPDATE bookings SET status = 'ACTIVE' WHERE booking_id = :b"), {"b": booking_id})
    db.execute(text("UPDATE bookings SET status = 'COMPLETED' WHERE booking_id = :b"), {"b": booking_id})
    return db.execute(
        text(
            "INSERT INTO charging_sessions (booking_id, charger_id, source, started_at, ended_at, energy_kwh, bill_amount, bill_status) "
            "VALUES (:b, :c, 'BOOKING', now() - interval '4 hours', now() - interval '3 hours', 12.4, :amt, 'DUE') RETURNING session_id"
        ),
        {"b": booking_id, "c": charger_id, "amt": amount},
    ).scalar_one()
