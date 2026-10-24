"""Admin endpoints. Every route here needs role ADMIN, checked on the server (hiding a button is not security)."""

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.slots import ist_date
from app.db import get_db
from app.features.admin import audit, manage
from app.features.admin import schemas as s
from app.features.admin import schemas_manage as m
from app.features.admin import service
from app.features.auth.dependencies import require_admin
from app.features.auth.models import User
from app.features.kiosk.schemas import DeviceCreated, DeviceOut

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _charger_name(db: Session, charger_id: UUID) -> str:
    """Station and charger label, for the activity log."""
    row = db.execute(
        text("SELECT st.name, c.label FROM chargers c JOIN stations st ON st.station_id = c.station_id WHERE c.charger_id = :c"), {"c": charger_id}
    ).first()
    return f"{row[0]} / {row[1]}" if row else str(charger_id)


# ---- numbers

@router.get("/overview", response_model=s.OverviewOut)
def overview(db: Session = Depends(get_db)):
    """Today numbers, 30-day revenue and the two chart series."""
    return service.overview(db, _now())


@router.get("/reports", response_model=s.ReportOut)
def report(
    date_from: date | None = Query(None, description="First day, India time. Default: 30 days ago."),
    date_to: date | None = Query(None, description="Last day, India time. Default: today."),
    db: Session = Depends(get_db),
):
    """Bookings by status, no-shows, revenue (booking fees, energy, walk-ins), refunds and operator settlement."""
    today = ist_date(_now())
    return service.report(db, date_from or today - timedelta(days=29), date_to or today)


# ---- stations and chargers

@router.get("/operators", response_model=list[m.OperatorRow])
def operators(db: Session = Depends(get_db)):
    return manage.list_operators(db)


@router.post("/operators", response_model=m.OperatorRow, status_code=status.HTTP_201_CREATED)
def create_operator(body: m.OperatorIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    row = manage.create_operator(db, body)
    audit.record(db, admin, "OPERATOR_CREATED", row.name)
    return row


@router.patch("/operators/{operator_id}", response_model=m.OperatorRow)
def update_operator(operator_id: UUID, body: m.OperatorUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    row = manage.update_operator(db, operator_id, body)
    audit.record(db, admin, "OPERATOR_EDITED", row.name, body.model_dump(exclude_unset=True))
    return row


@router.delete("/operators/{operator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_operator(operator_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Only an operator with no stations can be deleted (409 OPERATOR_IN_USE otherwise)."""
    audit.record(db, admin, "OPERATOR_DELETED", manage.delete_operator(db, operator_id))


@router.get("/stations", response_model=s.StationRows)
def stations(
    q: str | None = Query(None, max_length=100, description="Part of a station, city or operator name"),
    sort: str = Query("name", description="name, city, operator, source, chargers or status"),
    direction: Literal["asc", "desc"] = "asc",
    active: bool | None = Query(None, description="Only active (true) or inactive (false) stations"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.list_stations(db, q, sort, direction, active, page, page_size)


@router.get("/stations/{station_id}", response_model=s.AdminStation)
def get_station(station_id: UUID, db: Session = Depends(get_db)):
    return service.get_station(db, station_id)


@router.patch("/stations/{station_id}", response_model=s.AdminStation)
def update_station(station_id: UUID, body: s.StationUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Edit a station. Taking it off the map while it has future bookings needs `cancel_bookings = true` (409 HAS_FUTURE_BOOKINGS otherwise)."""
    out = service.update_station(db, station_id, body, _now())
    audit.record(db, admin, "STATION_EDITED", out.name, body.model_dump(exclude_unset=True, mode="json"))
    return out


@router.post("/stations/{station_id}/chargers", response_model=s.AdminStation, status_code=status.HTTP_201_CREATED)
def create_charger(station_id: UUID, body: s.ChargerCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    out = service.create_charger(db, station_id, body)
    audit.record(db, admin, "CHARGER_ADDED", f"{out.name} / {body.label}")
    return out


@router.patch("/chargers/{charger_id}", response_model=s.AdminStation)
def update_charger(charger_id: UUID, body: s.ChargerUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Edit a charger. Entering a power or price makes the value real: it loses its Approximate tag."""
    out = service.update_charger(db, charger_id, body)
    charger = next(c for c in out.chargers if c.charger_id == charger_id)
    audit.record(db, admin, "CHARGER_EDITED", f"{out.name} / {charger.label}", body.model_dump(exclude_unset=True, mode="json"))
    return out


@router.get("/chargers/{charger_id}/affected", response_model=s.AffectedOut)
def affected_by_out_of_service(charger_id: UUID, db: Session = Depends(get_db)):
    """What taking this charger out of service would break: the future bookings, and whether someone is charging."""
    return service.affected_by_out_of_service(db, charger_id, _now())


@router.post("/chargers/{charger_id}/out-of-service", response_model=s.OutOfServiceResult)
def out_of_service(charger_id: UUID, body: s.OutOfServiceRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Take a charger out of service. With future bookings it needs `cancel_bookings = true` (409 HAS_FUTURE_BOOKINGS otherwise);
    each is then cancelled with a full refund of what was paid."""
    out = service.set_out_of_service(db, charger_id, body.cancel_bookings, _now())
    audit.record(db, admin, "CHARGER_OUT_OF_SERVICE", _charger_name(db, charger_id), {"cancelled": out.cancelled, "refunded": out.refunded_total, "session_ended": out.session_ended})
    return out


@router.post("/chargers/{charger_id}/restore", response_model=s.OutOfServiceResult)
def restore(charger_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Put an out-of-service charger back in use."""
    out = service.restore_charger(db, charger_id, _now())
    audit.record(db, admin, "CHARGER_RESTORED", _charger_name(db, charger_id))
    return out


@router.get("/chargers/{charger_id}/events", response_model=list[s.ChargerEventOut])
def charger_events(charger_id: UUID, limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db)):
    """The newest charger events first (the simulator live log)."""
    return service.charger_events(db, charger_id, limit)


# ---- bookings

@router.get("/bookings", response_model=s.BookingRows)
def bookings(
    station_id: UUID | None = None,
    status: str | None = Query(None, pattern="^(HELD|CONFIRMED|ACTIVE|COMPLETED|EXPIRED|CANCELLED|NO_SHOW)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Bookings by slot start (India-time days), newest first."""
    return service.list_bookings(db, station_id, status, date_from, date_to, page, page_size)


@router.get("/bookings/{booking_id}/events", response_model=list[s.BookingEventOut])
def booking_events(booking_id: UUID, db: Session = Depends(get_db)):
    """The booking history: every status change, who made it and why."""
    return service.booking_events(db, booking_id)


# ---- kiosks and alerts

@router.get("/devices", response_model=list[s.DeviceRow])
def devices(db: Session = Depends(get_db)):
    return service.list_devices(db)


@router.get("/alerts", response_model=list[s.AlertOut])
def alerts(include_seen: bool = False, db: Session = Depends(get_db)):
    return service.list_alerts(db, include_seen)


@router.post("/alerts/{alert_id}/seen", response_model=s.AlertOut)
def alert_seen(alert_id: UUID, db: Session = Depends(get_db)):
    return service.mark_alert_seen(db, alert_id, _now())


# ---- people and money

@router.get("/users", response_model=m.UserRows)
def users(
    q: str | None = Query(None, max_length=100, description="Part of an email or name"),
    role: Literal["USER", "ADMIN"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return manage.list_users(db, q, role, page, page_size, admin.user_id)


@router.patch("/users/{user_id}/role", response_model=m.UserRow)
def change_role(user_id: UUID, body: m.RoleChange, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Make an account an admin, or an ordinary driver again. You cannot change your own role, and the last admin cannot be removed."""
    user, before = manage.change_role(db, admin, user_id, body.role)
    if before != body.role:
        audit.record(db, admin, "USER_ROLE_CHANGED", user.email, {"from": before, "to": body.role})
    return manage.user_row(db, user_id, admin.user_id)


@router.get("/payments", response_model=m.PaymentRows)
def payments(
    purpose: Literal["BOOKING_FEE", "ENERGY", "WALKIN_PREPAID"] | None = None,
    status: Literal["CREATED", "CAPTURED", "FAILED", "REFUNDED", "PARTIALLY_REFUNDED"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Every payment, newest first, with its refunds and the totals of what matches."""
    return manage.list_payments(db, purpose, status, page, page_size)


@router.get("/activity", response_model=m.ActivityRows)
def activity(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """What admins changed, newest first."""
    return manage.list_activity(db, page, page_size)


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def rename_device(device_id: UUID, body: m.DeviceRename, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    device = manage.rename_device(db, device_id, body.name)
    audit.record(db, admin, "KIOSK_RENAMED", device.name)
    return device


@router.post("/devices/{device_id}/rotate", response_model=DeviceCreated, status_code=status.HTTP_201_CREATED)
def rotate_device(device_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """A new key for the same tablet and station. The old key stops working at once; the new one is in this answer only."""
    new, key, old = manage.rotate_device(db, device_id)
    audit.record(db, admin, "KIOSK_KEY_ROTATED", new.name, {"old_prefix": old.key_prefix, "new_prefix": new.key_prefix})
    return DeviceCreated(**DeviceOut.model_validate(new, from_attributes=True).model_dump(), key=key)
