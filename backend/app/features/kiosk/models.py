"""Kiosk tables (schema: database/migrations/005_station_devices.sql and 014_kiosk.sql)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, UUID
from sqlalchemy.sql import func

from app.db import Base


class StationDevice(Base):
    """One kiosk tablet. Only a hash of its key is stored; the key itself is shown once, when it is made."""

    __tablename__ = "station_devices"

    device_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id"), nullable=False)
    name = Column(Text, nullable=False)
    key_prefix = Column(Text, nullable=False, unique=True)
    api_key_hash = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OtpAttempt(Base):
    """A code typed at a kiosk, right or wrong: the memory behind the cooldown and the alert."""

    __tablename__ = "otp_attempts"

    attempt_id = Column(BIGINT, primary_key=True, autoincrement=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("station_devices.device_id"), nullable=False)
    success = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminAlert(Base):
    __tablename__ = "admin_alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    kind = Column(Text, nullable=False)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id"))
    device_id = Column(UUID(as_uuid=True), ForeignKey("station_devices.device_id"))
    message = Column(Text, nullable=False)
    details = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))
