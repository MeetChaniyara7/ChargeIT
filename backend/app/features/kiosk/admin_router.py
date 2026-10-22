"""Admin: create and manage the kiosk keys. (The admin pages that use these are Phase 7.)"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db import get_db
from app.features.auth.dependencies import require_admin
from app.features.kiosk import keys
from app.features.kiosk.models import StationDevice
from app.features.kiosk.schemas import DeviceCreate, DeviceCreated, DeviceOut
from app.features.stations.models import Station

router = APIRouter(prefix="/api/admin", tags=["Admin: kiosks"], dependencies=[Depends(require_admin)])


def create_device(db: Session, station_id: UUID, name: str) -> tuple[StationDevice, str]:
    """Make a kiosk for a station. Returns the row and the key, which exists in plain form only here."""
    if db.get(Station, station_id) is None:
        raise AppError(404, "STATION_NOT_FOUND", "Station not found.")
    key, prefix, digest = keys.generate()
    device = StationDevice(station_id=station_id, name=name.strip(), key_prefix=prefix, api_key_hash=digest)
    db.add(device)
    db.commit()
    return device, key


@router.post("/stations/{station_id}/devices", response_model=DeviceCreated, status_code=201)
def new_device(station_id: UUID, body: DeviceCreate, db: Session = Depends(get_db)):
    """Create a kiosk key for a station. The key is in this response only; copy it to the tablet now."""
    device, key = create_device(db, station_id, body.name)
    return DeviceCreated(**DeviceOut.model_validate(device, from_attributes=True).model_dump(), key=key)


@router.get("/stations/{station_id}/devices", response_model=list[DeviceOut])
def list_devices(station_id: UUID, db: Session = Depends(get_db)):
    return db.scalars(select(StationDevice).where(StationDevice.station_id == station_id).order_by(StationDevice.created_at)).all()


@router.post("/devices/{device_id}/disable", response_model=DeviceOut)
def disable_device(device_id: UUID, db: Session = Depends(get_db)):
    """Switch a kiosk off (a lost tablet). Its key stops working at once."""
    device = db.get(StationDevice, device_id)
    if device is None:
        raise AppError(404, "DEVICE_NOT_FOUND", "Kiosk not found.")
    device.is_active = False
    db.commit()
    return device
