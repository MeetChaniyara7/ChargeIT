"""What admins can see and change: numbers, stations, chargers, bookings, kiosks, alerts.

Two rules matter most:
- Taking a charger out of service (or a station off the map) must never silently break a booking. If future
  bookings exist the admin is told which ones and must choose to cancel them; each is then cancelled with a
  full refund of what was paid and the driver gets a notice.
- A charger's status changes only through `apply_charger_event` (docs/architecture.md section 7.4).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.slots import ist_date, ist_day_start
from app.features.admin import schemas as s
from app.features.auth.models import User
from app.features.availability.occupancy import occupies_charger
from app.features.bookings import state_machine
from app.features.bookings.models import Booking
from app.features.charging.models import ChargingSession
from app.features.jobs.lazy import run_due_jobs
from app.features.payments.models import Payment
from app.features.stations import repository
from app.features.stations.models import Charger, Operator, Station

PAID_STATUSES = ("CAPTURED", "PARTIALLY_REFUNDED", "REFUNDED")
REAL_BOOKING = ("CONFIRMED", "ACTIVE", "COMPLETED", "NO_SHOW")  # a booking that was actually made (not an unpaid hold)


def _f(value) -> float:
    return float(value or 0)


# ================================================================ overview and reports

def _revenue(db: Session, start: datetime, end: datetime) -> s.Revenue:
    row = db.execute(
        text(
            "SELECT "
            " coalesce(sum(CASE WHEN purpose = 'BOOKING_FEE' THEN amount - refunded_amount END), 0), "
            " coalesce(sum(CASE WHEN purpose = 'ENERGY' THEN amount - refunded_amount END), 0), "
            " coalesce(sum(CASE WHEN purpose = 'WALKIN_PREPAID' THEN amount - refunded_amount END), 0), "
            " coalesce(sum(refunded_amount), 0) "
            "FROM payments WHERE status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED') AND created_at >= :s AND created_at < :e"
        ),
        {"s": start, "e": end},
    ).one()
    return s.Revenue(booking_fees=_f(row[0]), energy=_f(row[1]), walk_ins=_f(row[2]), refunds=_f(row[3]))


def _no_shows_by_station(db: Session, start: datetime, end: datetime, limit: int = 8) -> list[s.StationCount]:
    rows = db.execute(
        text(
            "SELECT st.name, count(*) AS n FROM bookings b "
            "JOIN chargers c ON c.charger_id = b.charger_id JOIN stations st ON st.station_id = c.station_id "
            "WHERE b.status = 'NO_SHOW' AND lower(b.time_range) >= :s AND lower(b.time_range) < :e "
            "GROUP BY st.name ORDER BY n DESC, st.name LIMIT :l"
        ),
        {"s": start, "e": end, "l": limit},
    ).all()
    return [s.StationCount(station_name=r[0], count=r[1]) for r in rows]


def overview(db: Session, now: datetime) -> s.OverviewOut:
    run_due_jobs(db, now)
    today = ist_date(now)
    day_start, day_end = ist_day_start(today), ist_day_start(today + timedelta(days=1))
    first_day = today - timedelta(days=13)
    per_day = dict(
        db.execute(
            text(
                "SELECT (lower(time_range) AT TIME ZONE 'Asia/Kolkata')::date AS d, count(*) FROM bookings "
                "WHERE status = ANY(:st) AND lower(time_range) >= :s AND lower(time_range) < :e GROUP BY 1"
            ),
            {"st": list(REAL_BOOKING), "s": ist_day_start(first_day), "e": day_end},
        ).all()
    )
    return s.OverviewOut(
        today_bookings=db.scalar(
            text("SELECT count(*) FROM bookings WHERE status = ANY(:st) AND lower(time_range) >= :s AND lower(time_range) < :e"),
            {"st": list(REAL_BOOKING), "s": day_start, "e": day_end},
        ),
        active_sessions=db.scalar(select(func.count()).select_from(ChargingSession).where(ChargingSession.ended_at.is_(None))),
        no_shows_week=db.scalar(
            text("SELECT count(*) FROM bookings WHERE status = 'NO_SHOW' AND lower(time_range) >= :s AND lower(time_range) <= :e"),
            {"s": now - timedelta(days=7), "e": now},
        ),
        open_alerts=db.scalar(text("SELECT count(*) FROM admin_alerts WHERE resolved_at IS NULL")),
        revenue=_revenue(db, now - timedelta(days=30), now + timedelta(seconds=1)),
        revenue_days=30,
        bookings_per_day=[
            s.DayCount(day=first_day + timedelta(days=i), count=per_day.get(first_day + timedelta(days=i), 0)) for i in range(14)
        ],
        no_shows_by_station=_no_shows_by_station(db, now - timedelta(days=30), now),
    )


def report(db: Session, date_from: date, date_to: date) -> s.ReportOut:
    if date_to < date_from:
        raise AppError(422, "INVALID_RANGE", "The end date is before the start date.")
    if (date_to - date_from).days > 366:
        raise AppError(422, "INVALID_RANGE", "Pick a range of at most a year.")
    start, end = ist_day_start(date_from), ist_day_start(date_to + timedelta(days=1))
    by_status = db.execute(
        text(
            "SELECT status, count(*) FROM bookings WHERE lower(time_range) >= :s AND lower(time_range) < :e "
            "GROUP BY status ORDER BY count(*) DESC, status"
        ),
        {"s": start, "e": end},
    ).all()
    settlement = db.execute(
        text(
            "SELECT coalesce(o.name, 'No operator'), count(*), coalesce(sum(x.net), 0) FROM ("
            " SELECT st.operator_id, p.amount - p.refunded_amount AS net FROM payments p "
            " JOIN bookings b ON b.booking_id = p.booking_id JOIN chargers c ON c.charger_id = b.charger_id "
            " JOIN stations st ON st.station_id = c.station_id "
            " WHERE p.purpose IN ('ENERGY', 'WALKIN_PREPAID') AND p.status IN ('CAPTURED', 'PARTIALLY_REFUNDED') "
            "   AND p.created_at >= :s AND p.created_at < :e"
            ") x LEFT JOIN operators o ON o.operator_id = x.operator_id GROUP BY 1 ORDER BY 3 DESC, 1"
        ),
        {"s": start, "e": end},
    ).all()
    return s.ReportOut(
        date_from=date_from,
        date_to=date_to,
        bookings_by_status=[s.StatusCount(status=r[0], count=r[1]) for r in by_status],
        no_shows=sum(r[1] for r in by_status if r[0] == "NO_SHOW"),
        revenue=_revenue(db, start, end),
        settlement=[s.SettlementRow(operator_name=r[0], sessions=r[1], energy_revenue=_f(r[2])) for r in settlement],
    )


# ================================================================ stations

SORTS = {
    "name": "s.name", "city": "s.city", "operator": "o.name", "source": "s.data_source",
    "chargers": "charger_count", "status": "s.is_active",
}


def list_stations(db: Session, q: str | None, sort: str, direction: str, active: bool | None, page: int, page_size: int) -> s.StationRows:
    if sort not in SORTS:
        raise AppError(422, "INVALID_SORT", f"Sort by one of: {', '.join(SORTS)}.")
    order = f"{SORTS[sort]} {'DESC' if direction == 'desc' else 'ASC'} NULLS LAST, s.station_id"  # whitelisted above: never user text
    params = {"q": f"%{q.strip()}%" if q and q.strip() else None, "active": active, "l": page_size, "o": (page - 1) * page_size}
    where = (
        "s.vehicle_category = 'FOUR_WHEELER' AND (CAST(:q AS text) IS NULL OR s.name ILIKE :q OR s.city ILIKE :q OR o.name ILIKE :q) "
        "AND (CAST(:active AS boolean) IS NULL OR s.is_active = :active)"
    )
    total = db.scalar(text(f"SELECT count(*) FROM stations s LEFT JOIN operators o ON o.operator_id = s.operator_id WHERE {where}"), params)
    rows = db.execute(
        text(
            "SELECT s.station_id, s.name, s.city, o.name AS operator_name, s.data_source, s.is_active, "
            " (SELECT count(*) FROM chargers c WHERE c.station_id = s.station_id) AS charger_count, "
            " (cardinality(s.estimated_fields) > 0 OR EXISTS (SELECT 1 FROM chargers c WHERE c.station_id = s.station_id "
            "   AND (c.data_source = 'synthetic' OR cardinality(c.estimated_fields) > 0))) AS has_estimated "
            f"FROM stations s LEFT JOIN operators o ON o.operator_id = s.operator_id WHERE {where} ORDER BY {order} LIMIT :l OFFSET :o"
        ),
        params,
    ).all()
    return s.StationRows(
        items=[
            s.StationRow(
                station_id=r.station_id, name=r.name, city=r.city, operator_name=r.operator_name, data_source=r.data_source,
                is_active=r.is_active, charger_count=r.charger_count, has_estimated_data=r.has_estimated,
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )


def _station_out(station: Station) -> s.AdminStation:
    return s.AdminStation(
        station_id=station.station_id, name=station.name, address=station.address, city=station.city,
        latitude=station.latitude, longitude=station.longitude, operator_id=station.operator_id, operator_name=station.operator_name,
        opening_hours=station.opening_hours, is_active=station.is_active, data_source=station.data_source,
        has_estimated_data=station.has_estimated_data,
        chargers=[
            s.AdminCharger(
                charger_id=c.charger_id, label=c.label, connector_type=c.connector_type, current_type=c.current_type,
                power_kw=_f(c.power_kw) if c.power_kw is not None else None,
                price_per_kwh=_f(c.price_per_kwh) if c.price_per_kwh is not None else None,
                status=c.status, data_source=c.data_source,
            )
            for c in station.chargers
        ],
    )


def _station(db: Session, station_id: UUID) -> Station:
    station = repository.get_station(db, station_id)
    if station is None:
        raise AppError(404, "STATION_NOT_FOUND", "Station not found.")
    return station


def get_station(db: Session, station_id: UUID) -> s.AdminStation:
    return _station_out(_station(db, station_id))


def update_station(db: Session, station_id: UUID, data: s.StationUpdate, now: datetime) -> s.AdminStation:
    station = _station(db, station_id)
    changes = data.model_dump(exclude_unset=True, exclude={"cancel_bookings"})
    if changes.get("operator_id") is not None and db.get(Operator, changes["operator_id"]) is None:
        raise AppError(422, "OPERATOR_NOT_FOUND", "That operator does not exist.")
    if changes.get("is_active") is False and station.is_active:
        _guard_future_bookings(db, [c.charger_id for c in station.chargers], data.cancel_bookings, now, "Taking this station off the map")
    for name, value in changes.items():
        if name == "name" and value is not None:
            value = value.strip()
        if name == "is_active" and value is None:
            continue
        setattr(station, name, value)
    db.commit()
    return get_station(db, station_id)


# ================================================================ chargers

def create_charger(db: Session, station_id: UUID, data: s.ChargerCreate) -> s.AdminStation:
    _station(db, station_id)
    db.add(
        Charger(
            station_id=station_id, label=data.label.strip(), connector_type=data.connector_type, current_type=data.current_type,
            power_kw=data.power_kw, price_per_kwh=data.price_per_kwh, status="AVAILABLE", data_source="manual", estimated_fields=[],
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "CHARGER_LABEL_TAKEN", "This station already has a charger with that label.") from exc
    return get_station(db, station_id)


def _charger(db: Session, charger_id: UUID) -> Charger:
    charger = db.scalars(select(Charger).where(Charger.charger_id == charger_id).with_for_update()).first()
    if charger is None:
        raise AppError(404, "CHARGER_NOT_FOUND", "Charger not found.")
    return charger


def update_charger(db: Session, charger_id: UUID, data: s.ChargerUpdate) -> s.AdminStation:
    charger = _charger(db, charger_id)
    changes = data.model_dump(exclude_unset=True)
    for name, value in changes.items():
        if value is None and name in ("label", "connector_type"):
            continue
        setattr(charger, name, value.strip() if name == "label" and value else value)
    if {"power_kw", "price_per_kwh", "connector_type", "current_type"} & changes.keys():
        # The admin has now entered real values: they are no longer generated ("Approximate").
        charger.data_source = "manual"
        charger.estimated_fields = []
    station_id = charger.station_id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "CHARGER_LABEL_TAKEN", "This station already has a charger with that label.") from exc
    return get_station(db, station_id)


def _future_bookings(db: Session, charger_ids: list[UUID], now: datetime) -> list[Booking]:
    """Bookings that still need these chargers: confirmed ones, and holds that have not run out."""
    if not charger_ids:
        return []
    return list(
        db.scalars(
            select(Booking)
            .where(
                Booking.charger_id.in_(charger_ids), Booking.status.in_(("HELD", "CONFIRMED")), occupies_charger(now),
                func.upper(Booking.time_range) > now,
            )
            .order_by(func.lower(Booking.time_range))
            .with_for_update()
        )
    )


def _fee_paid(db: Session, booking_id: UUID) -> Decimal:
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount - Payment.refunded_amount), 0)).where(
            Payment.booking_id == booking_id, Payment.purpose == "BOOKING_FEE", Payment.status.in_(("CAPTURED", "PARTIALLY_REFUNDED"))
        )
    )
    return Decimal(paid or 0)


def _running_session(db: Session, charger_id: UUID) -> ChargingSession | None:
    return db.scalar(select(ChargingSession).where(ChargingSession.charger_id == charger_id, ChargingSession.ended_at.is_(None)))


def affected_by_out_of_service(db: Session, charger_id: UUID, now: datetime) -> s.AffectedOut:
    charger = db.get(Charger, charger_id)
    if charger is None:
        raise AppError(404, "CHARGER_NOT_FOUND", "Charger not found.")
    run_due_jobs(db, now, charger.station_id)
    out = []
    for b in _future_bookings(db, [charger_id], now):
        email = db.scalar(select(User.email).where(User.user_id == b.user_id)) if b.user_id else None
        out.append(
            s.AffectedBooking(
                booking_id=b.booking_id, status=b.status, source=b.source, start=b.start, end=b.end, user_email=email,
                fee_paid=_f(_fee_paid(db, b.booking_id)),
            )
        )
    db.rollback()  # only reading: release the row locks taken above
    return s.AffectedOut(charger_id=charger_id, label=charger.label, charging_now=_running_session(db, charger_id) is not None, bookings=out)


def _cancel_with_full_refund(db: Session, booking: Booking, reason: str, now: datetime) -> Decimal:
    """Cancel a booking because of something on our side: everything the driver paid for it goes back (recorded)."""
    paid = _fee_paid(db, booking.booking_id)
    state_machine.transition(db, booking, "CANCELLED", "ADMIN", reason)
    booking.cancelled_at = now
    booking.cancel_reason = f"{reason}. The booking was cancelled" + (" and your booking fee is refunded in full." if paid > 0 else ".")
    booking.refund_amount = paid
    booking.notice_kind = "CANCELLED_NO_CHARGER"
    booking.notice_text = f"Cancelled: {reason[0].lower()}{reason[1:]}." + (" Your booking fee is refunded in full." if paid > 0 else "")
    for payment in db.scalars(
        select(Payment).where(Payment.booking_id == booking.booking_id, Payment.purpose == "BOOKING_FEE", Payment.status.in_(("CAPTURED", "PARTIALLY_REFUNDED")))
    ):
        payment.refunded_amount = payment.amount
        payment.status = "REFUNDED"
    return paid


def _guard_future_bookings(db: Session, charger_ids: list[UUID], cancel: bool, now: datetime, action: str) -> tuple[int, Decimal]:
    """Stops with 409 HAS_FUTURE_BOOKINGS unless the admin chose to cancel them; otherwise cancels them all."""
    future = _future_bookings(db, charger_ids, now)
    if future and not cancel:
        db.rollback()
        raise AppError(
            409, "HAS_FUTURE_BOOKINGS",
            f"{action} would break {len(future)} booking{'s' if len(future) != 1 else ''}. Cancel them with a full refund, or leave things as they are.",
            {"count": len(future)},
        )
    refunded = Decimal(0)
    for booking in future:
        refunded += _cancel_with_full_refund(db, booking, "The charger was taken out of service", now)
    return len(future), refunded


def set_out_of_service(db: Session, charger_id: UUID, cancel_bookings: bool, now: datetime) -> s.OutOfServiceResult:
    charger = _charger(db, charger_id)
    if charger.status == "OUT_OF_SERVICE":
        return s.OutOfServiceResult(status="OUT_OF_SERVICE", cancelled=0, refunded_total=0, session_ended=False)
    run_due_jobs(db, now, charger.station_id)
    db.refresh(charger)
    cancelled, refunded = _guard_future_bookings(db, [charger_id], cancel_bookings, now, "Taking this charger out of service")

    running = _running_session(db, charger_id)
    if running is not None:  # whoever is charging is stopped and billed up to now
        db.execute(
            text("SELECT finish_session(CAST(:s AS uuid), CAST(:at AS timestamptz), 'ADMIN', 'ADMIN', CAST(:at AS timestamptz))"),
            {"s": running.session_id, "at": now},
        )
    db.execute(
        text("SELECT apply_charger_event(CAST(:c AS uuid), 'OUT_OF_SERVICE', CAST('{}' AS jsonb), 'ADMIN', CAST(:now AS timestamptz))"),
        {"c": charger_id, "now": now},
    )
    db.commit()
    return s.OutOfServiceResult(status="OUT_OF_SERVICE", cancelled=cancelled, refunded_total=_f(refunded), session_ended=running is not None)


def restore_charger(db: Session, charger_id: UUID, now: datetime) -> s.OutOfServiceResult:
    charger = _charger(db, charger_id)
    if charger.status != "OUT_OF_SERVICE":
        raise AppError(409, "NOT_OUT_OF_SERVICE", "This charger is not out of service.")
    status = db.execute(
        text("SELECT apply_charger_event(CAST(:c AS uuid), 'RESTORE', CAST('{}' AS jsonb), 'ADMIN', CAST(:now AS timestamptz))"),
        {"c": charger_id, "now": now},
    ).scalar_one()
    db.commit()
    return s.OutOfServiceResult(status=status, cancelled=0, refunded_total=0, session_ended=False)


def charger_events(db: Session, charger_id: UUID, limit: int) -> list[s.ChargerEventOut]:
    if db.get(Charger, charger_id) is None:
        raise AppError(404, "CHARGER_NOT_FOUND", "Charger not found.")
    rows = db.execute(
        text("SELECT event_id, event, source, details, created_at FROM charger_events WHERE charger_id = :c ORDER BY event_id DESC LIMIT :l"),
        {"c": charger_id, "l": limit},
    ).all()
    return [s.ChargerEventOut(event_id=r[0], event=r[1], source=r[2], details=r[3] or {}, created_at=r[4]) for r in rows]


# ================================================================ bookings

def list_bookings(
    db: Session, station_id: UUID | None, status: str | None, date_from: date | None, date_to: date | None, page: int, page_size: int
) -> s.BookingRows:
    params = {
        "station": station_id, "status": status,
        "s": ist_day_start(date_from) if date_from else None,
        "e": ist_day_start(date_to + timedelta(days=1)) if date_to else None,
        "l": page_size, "o": (page - 1) * page_size,
    }
    where = (
        "(CAST(:station AS uuid) IS NULL OR c.station_id = :station) AND (CAST(:status AS text) IS NULL OR b.status = :status) "
        "AND (CAST(:s AS timestamptz) IS NULL OR lower(b.time_range) >= :s) AND (CAST(:e AS timestamptz) IS NULL OR lower(b.time_range) < :e)"
    )
    join = "FROM bookings b JOIN chargers c ON c.charger_id = b.charger_id JOIN stations st ON st.station_id = c.station_id LEFT JOIN users u ON u.user_id = b.user_id"
    total = db.scalar(text(f"SELECT count(*) {join} WHERE {where}"), params)
    rows = db.execute(
        text(
            "SELECT b.booking_id, b.status, b.source, lower(b.time_range) AS start, upper(b.time_range) AS stop, st.name AS station_name, "
            f"c.label, u.email, b.booking_fee, b.refund_amount, b.created_at {join} WHERE {where} "
            "ORDER BY lower(b.time_range) DESC, b.booking_id LIMIT :l OFFSET :o"
        ),
        params,
    ).all()
    return s.BookingRows(
        items=[
            s.BookingRow(
                booking_id=r[0], status=r[1], source=r[2], start=r[3], end=r[4], station_name=r[5], charger_label=r[6], user_email=r[7],
                booking_fee=_f(r[8]), refund_amount=_f(r[9]), created_at=r[10],
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )


def booking_events(db: Session, booking_id: UUID) -> list[s.BookingEventOut]:
    if db.get(Booking, booking_id) is None:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")
    rows = db.execute(
        text("SELECT event_id, from_status, to_status, actor, reason, created_at FROM booking_events WHERE booking_id = :b ORDER BY created_at, event_id"),
        {"b": booking_id},
    ).all()
    return [s.BookingEventOut(event_id=r[0], from_status=r[1], to_status=r[2], actor=r[3], reason=r[4], created_at=r[5]) for r in rows]


# ================================================================ kiosks and alerts

def list_devices(db: Session) -> list[s.DeviceRow]:
    rows = db.execute(
        text(
            "SELECT d.device_id, d.station_id, st.name, d.name, d.key_prefix, d.is_active, d.last_seen_at, d.created_at "
            "FROM station_devices d JOIN stations st ON st.station_id = d.station_id ORDER BY d.is_active DESC, d.created_at DESC"
        )
    ).all()
    return [
        s.DeviceRow(
            device_id=r[0], station_id=r[1], station_name=r[2], name=r[3], key_prefix=r[4], is_active=r[5], last_seen_at=r[6], created_at=r[7]
        )
        for r in rows
    ]


def list_alerts(db: Session, include_seen: bool, limit: int = 100) -> list[s.AlertOut]:
    rows = db.execute(
        text(
            "SELECT a.alert_id, a.kind, st.name, a.message, a.details, a.created_at, a.resolved_at FROM admin_alerts a "
            "LEFT JOIN stations st ON st.station_id = a.station_id "
            "WHERE (:all OR a.resolved_at IS NULL) ORDER BY a.created_at DESC LIMIT :l"
        ),
        {"all": include_seen, "l": limit},
    ).all()
    return [
        s.AlertOut(alert_id=r[0], kind=r[1], station_name=r[2], message=r[3], details=r[4] or {}, created_at=r[5], resolved_at=r[6])
        for r in rows
    ]


def mark_alert_seen(db: Session, alert_id: UUID, now: datetime) -> s.AlertOut:
    updated = db.execute(
        text("UPDATE admin_alerts SET resolved_at = coalesce(resolved_at, :now) WHERE alert_id = :a RETURNING alert_id"),
        {"a": alert_id, "now": now},
    ).first()
    if updated is None:
        db.rollback()
        raise AppError(404, "ALERT_NOT_FOUND", "Alert not found.")
    db.commit()
    return next(a for a in list_alerts(db, True, 500) if a.alert_id == alert_id)
