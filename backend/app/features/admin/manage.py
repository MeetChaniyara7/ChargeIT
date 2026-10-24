"""Managing people and money from the admin pages: roles, operators, payments, kiosk keys, the activity log.

Safety rules for roles (a mistake here could lock everyone out):
- an admin cannot change their own role (ask another admin);
- the last admin can never be removed.
Every change is written to the activity log by the router after it succeeds.
"""

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.features.admin import schemas_manage as m
from app.features.auth.models import User
from app.features.kiosk import keys
from app.features.kiosk.models import StationDevice
from app.features.stations.models import Operator


def _f(value) -> float:
    return float(value or 0)


# ================================================================ users and roles

def _count_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "ADMIN")) or 0


def list_users(db: Session, q: str | None, role: str | None, page: int, page_size: int, me: UUID) -> m.UserRows:
    params = {"q": f"%{q.strip()}%" if q and q.strip() else None, "role": role, "l": page_size, "o": (page - 1) * page_size}
    where = "(CAST(:q AS text) IS NULL OR u.email ILIKE :q OR u.full_name ILIKE :q) AND (CAST(:role AS text) IS NULL OR u.role = :role)"
    total = db.scalar(text(f"SELECT count(*) FROM users u WHERE {where}"), params)
    rows = db.execute(
        text(
            "SELECT u.user_id, u.email, u.full_name, u.role, u.created_at, "
            " CASE WHEN u.google_user_id IS NOT NULL AND u.password_hash IS NOT NULL THEN 'BOTH' "
            "      WHEN u.google_user_id IS NOT NULL THEN 'GOOGLE' ELSE 'PASSWORD' END AS sign_in, "
            " (SELECT count(*) FROM bookings b WHERE b.user_id = u.user_id) AS bookings "
            f"FROM users u WHERE {where} ORDER BY (u.role = 'ADMIN') DESC, lower(u.email) LIMIT :l OFFSET :o"
        ),
        params,
    ).all()
    return m.UserRows(
        items=[
            m.UserRow(user_id=r.user_id, email=r.email, full_name=r.full_name, role=r.role, sign_in=r.sign_in, bookings=r.bookings, created_at=r.created_at, is_you=r.user_id == me)
            for r in rows
        ],
        total=total, page=page, page_size=page_size, admins=_count_admins(db),
    )


def change_role(db: Session, admin: User, user_id: UUID, role: str) -> tuple[User, str]:
    """Returns the user and the role they had before. Raises if it would lock the admins out."""
    user = db.scalars(select(User).where(User.user_id == user_id).with_for_update()).first()
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "That account does not exist.")
    if user.user_id == admin.user_id:
        raise AppError(409, "CANNOT_CHANGE_OWN_ROLE", "You cannot change your own role. Ask another admin to do it.")
    before = user.role
    if before == role:
        return user, before
    if before == "ADMIN" and _count_admins(db) <= 1:
        raise AppError(409, "LAST_ADMIN", "This is the last admin, so the role cannot be removed.")
    user.role = role
    db.commit()
    return user, before


def user_row(db: Session, user_id: UUID, me: UUID) -> m.UserRow:
    rows = list_users(db, None, None, 1, 100000, me)
    return next(r for r in rows.items if r.user_id == user_id)


# ================================================================ operators

def list_operators(db: Session) -> list[m.OperatorRow]:
    rows = db.execute(
        text(
            "SELECT o.operator_id, o.name, o.website, "
            " (SELECT count(*) FROM stations s WHERE s.operator_id = o.operator_id) AS station_count "
            "FROM operators o ORDER BY lower(o.name)"
        )
    ).all()
    return [m.OperatorRow(operator_id=r.operator_id, name=r.name, website=r.website, station_count=r.station_count) for r in rows]


def _operator_row(db: Session, operator_id: UUID) -> m.OperatorRow:
    return next(o for o in list_operators(db) if o.operator_id == operator_id)


def create_operator(db: Session, data: m.OperatorIn) -> m.OperatorRow:
    operator = Operator(name=data.name.strip(), website=(data.website or "").strip() or None)
    db.add(operator)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "OPERATOR_NAME_TAKEN", "An operator with that name already exists.") from exc
    return _operator_row(db, operator.operator_id)


def update_operator(db: Session, operator_id: UUID, data: m.OperatorUpdate) -> m.OperatorRow:
    operator = db.get(Operator, operator_id)
    if operator is None:
        raise AppError(404, "OPERATOR_NOT_FOUND", "Operator not found.")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        operator.name = changes["name"].strip()
    if "website" in changes:
        operator.website = (changes["website"] or "").strip() or None
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "OPERATOR_NAME_TAKEN", "An operator with that name already exists.") from exc
    return _operator_row(db, operator_id)


def delete_operator(db: Session, operator_id: UUID) -> str:
    operator = db.get(Operator, operator_id)
    if operator is None:
        raise AppError(404, "OPERATOR_NOT_FOUND", "Operator not found.")
    stations = db.scalar(text("SELECT count(*) FROM stations WHERE operator_id = :o"), {"o": operator_id})
    if stations:
        raise AppError(
            409, "OPERATOR_IN_USE", f"{stations} station{'s' if stations != 1 else ''} still belong{'' if stations != 1 else 's'} to this operator. Move them to another operator first.",
            {"stations": stations},
        )
    name = operator.name
    db.delete(operator)
    db.commit()
    return name


# ================================================================ payments

def list_payments(db: Session, purpose: str | None, status: str | None, page: int, page_size: int) -> m.PaymentRows:
    params = {"purpose": purpose, "status": status, "l": page_size, "o": (page - 1) * page_size}
    where = "(CAST(:purpose AS text) IS NULL OR p.purpose = :purpose) AND (CAST(:status AS text) IS NULL OR p.status = :status)"
    join = (
        "FROM payments p JOIN bookings b ON b.booking_id = p.booking_id JOIN chargers c ON c.charger_id = b.charger_id "
        "JOIN stations st ON st.station_id = c.station_id LEFT JOIN users u ON u.user_id = b.user_id"
    )
    totals = db.execute(text(f"SELECT count(*), coalesce(sum(p.amount), 0), coalesce(sum(p.refunded_amount), 0) {join} WHERE {where}"), params).one()
    rows = db.execute(
        text(
            "SELECT p.payment_id, p.purpose, p.status, p.amount, p.refunded_amount, p.provider_payment_id, st.name, u.email, p.created_at "
            f"{join} WHERE {where} ORDER BY p.created_at DESC, p.payment_id LIMIT :l OFFSET :o"
        ),
        params,
    ).all()
    return m.PaymentRows(
        items=[
            m.PaymentRow(
                payment_id=r[0], purpose=r[1], status=r[2], amount=_f(r[3]), refunded_amount=_f(r[4]), provider_payment_id=r[5],
                station_name=r[6], user_email=r[7], created_at=r[8],
            )
            for r in rows
        ],
        total=totals[0], page=page, page_size=page_size, amount_total=_f(totals[1]), refunded_total=_f(totals[2]),
    )


# ================================================================ kiosk keys

def _device(db: Session, device_id: UUID) -> StationDevice:
    device = db.get(StationDevice, device_id)
    if device is None:
        raise AppError(404, "DEVICE_NOT_FOUND", "Kiosk not found.")
    return device


def rename_device(db: Session, device_id: UUID, name: str) -> StationDevice:
    device = _device(db, device_id)
    device.name = name.strip()
    db.commit()
    return device


def rotate_device(db: Session, device_id: UUID) -> tuple[StationDevice, str, StationDevice]:
    """A new key for the same tablet and station; the old key stops working at once. Returns (new row, new key, old row).

    Use it when a key may have leaked or the tablet was replaced: the owner pastes the new key on the tablet.
    """
    old = _device(db, device_id)
    if not old.is_active:
        raise AppError(409, "DEVICE_REVOKED", "This key is already revoked. Create a new key for the station instead.")
    key, prefix, digest = keys.generate()
    new = StationDevice(station_id=old.station_id, name=old.name, key_prefix=prefix, api_key_hash=digest)
    old.is_active = False
    db.add(new)
    db.commit()
    return new, key, old


# ================================================================ activity log

def list_activity(db: Session, page: int, page_size: int) -> m.ActivityRows:
    total = db.scalar(text("SELECT count(*) FROM admin_actions"))
    rows = db.execute(
        text("SELECT action_id, admin_email, action, target, details, created_at FROM admin_actions ORDER BY created_at DESC, action_id DESC LIMIT :l OFFSET :o"),
        {"l": page_size, "o": (page - 1) * page_size},
    ).all()
    return m.ActivityRows(
        items=[m.ActivityRow(action_id=r[0], admin_email=r[1], action=r[2], target=r[3], details=r[4] or {}, created_at=r[5]) for r in rows],
        total=total, page=page, page_size=page_size,
    )
