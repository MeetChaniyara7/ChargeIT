"""Who is calling a kiosk endpoint: the device named by the X-Device-Key header.

A device belongs to exactly one station and every kiosk query is limited to that station, so a stolen
or misconfigured tablet cannot see or start another station's chargers.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db import get_db
from app.features.kiosk import keys
from app.features.kiosk.models import StationDevice

LAST_SEEN_EVERY = timedelta(seconds=30)  # no need to write to the database on every poll


def get_current_device(x_device_key: str = Header(default=""), db: Session = Depends(get_db)) -> StationDevice:
    prefix = keys.prefix_of(x_device_key) if x_device_key else None
    device = db.scalar(select(StationDevice).where(StationDevice.key_prefix == prefix)) if prefix else None
    if device is None or not keys.matches(x_device_key, device.api_key_hash):
        raise AppError(401, "INVALID_DEVICE_KEY", "This kiosk key is not valid.")
    if not device.is_active:
        raise AppError(403, "DEVICE_DISABLED", "This kiosk has been switched off.")
    now = datetime.now(timezone.utc)
    if device.last_seen_at is None or now - device.last_seen_at >= LAST_SEEN_EVERY:
        device.last_seen_at = now
        db.commit()
    return device
