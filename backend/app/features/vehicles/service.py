"""A user's vehicles: list, add, change, delete. Each user sees only their own."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import BOOKING_RULES
from app.core.errors import AppError
from app.features.vehicles.models import Vehicle
from app.features.vehicles.schemas import VehicleIn, VehicleOut, VehicleUpdate


def _out(vehicle: Vehicle) -> VehicleOut:
    return VehicleOut(
        vehicle_id=vehicle.vehicle_id, nickname=vehicle.nickname, connector_type=vehicle.connector_type,
        battery_kwh=float(vehicle.battery_kwh), is_default=vehicle.is_default, created_at=vehicle.created_at,
    )


def _mine(db: Session, user_id: UUID) -> list[Vehicle]:
    return list(db.scalars(select(Vehicle).where(Vehicle.user_id == user_id).order_by(Vehicle.created_at, Vehicle.vehicle_id)))


def get_owned(db: Session, user_id: UUID, vehicle_id: UUID) -> Vehicle:
    vehicle = db.scalar(select(Vehicle).where(Vehicle.vehicle_id == vehicle_id, Vehicle.user_id == user_id))
    if not vehicle:
        raise AppError(404, "VEHICLE_NOT_FOUND", "Vehicle not found.")
    return vehicle


def _make_default(db: Session, user_id: UUID, vehicle: Vehicle) -> None:
    # The database allows ONE default per user, so clear the others first.
    db.execute(update(Vehicle).where(Vehicle.user_id == user_id, Vehicle.vehicle_id != vehicle.vehicle_id).values(is_default=False))
    vehicle.is_default = True
    db.flush()


def list_vehicles(db: Session, user_id: UUID) -> list[VehicleOut]:
    # The default first, then oldest first.
    return [_out(v) for v in sorted(_mine(db, user_id), key=lambda v: not v.is_default)]


def create(db: Session, user_id: UUID, data: VehicleIn) -> VehicleOut:
    existing = _mine(db, user_id)
    if len(existing) >= BOOKING_RULES.max_vehicles_per_user:
        raise AppError(409, "TOO_MANY_VEHICLES", f"You can save up to {BOOKING_RULES.max_vehicles_per_user} vehicles.")
    vehicle = Vehicle(
        user_id=user_id, nickname=data.nickname.strip(), connector_type=data.connector_type,
        battery_kwh=data.battery_kwh, is_default=False,
    )
    db.add(vehicle)
    db.flush()
    if data.is_default or not existing:  # the first vehicle is the default
        _make_default(db, user_id, vehicle)
    db.commit()
    return _out(vehicle)


def update_vehicle(db: Session, user_id: UUID, vehicle_id: UUID, data: VehicleUpdate) -> VehicleOut:
    vehicle = get_owned(db, user_id, vehicle_id)
    changes = data.model_dump(exclude_unset=True)
    if "nickname" in changes and changes["nickname"] is not None:
        vehicle.nickname = changes["nickname"].strip()
    if changes.get("connector_type") is not None:
        vehicle.connector_type = changes["connector_type"]
    if changes.get("battery_kwh") is not None:
        vehicle.battery_kwh = changes["battery_kwh"]
    if changes.get("is_default") is True:
        _make_default(db, user_id, vehicle)
    elif changes.get("is_default") is False and vehicle.is_default:
        raise AppError(409, "DEFAULT_REQUIRED", "Pick another vehicle as the default instead.")
    db.commit()
    return _out(vehicle)


def delete(db: Session, user_id: UUID, vehicle_id: UUID) -> None:
    vehicle = get_owned(db, user_id, vehicle_id)
    was_default = vehicle.is_default
    db.delete(vehicle)
    db.flush()
    if was_default:  # keep a default whenever the user still has vehicles
        remaining = _mine(db, user_id)
        if remaining:
            _make_default(db, user_id, remaining[0])
    db.commit()
