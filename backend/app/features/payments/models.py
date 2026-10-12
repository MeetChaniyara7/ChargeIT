"""Payments and webhook events (schema: database/migrations/007_payments.sql)."""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db import Base


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"), nullable=False)
    session_id = Column(UUID(as_uuid=True))
    purpose = Column(Text, nullable=False)  # BOOKING_FEE | ENERGY | WALKIN_PREPAID
    provider = Column(Text, nullable=False, server_default="razorpay")
    provider_order_id = Column(Text, nullable=False, unique=True)
    provider_payment_id = Column(Text, unique=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, nullable=False, server_default="INR")
    status = Column(Text, nullable=False, server_default="CREATED")
    refunded_amount = Column(Numeric(10, 2), nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    provider_event_id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
