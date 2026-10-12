"""Request and response shapes for payments."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.features.bookings.schemas import BookingOut


class OrderRequest(BaseModel):
    booking_id: UUID


class OrderOut(BaseModel):
    """Everything Razorpay Checkout needs. The amount comes from the server, never from the browser."""

    booking_id: UUID
    order_id: str
    amount: float
    amount_paise: int
    currency: str
    key_id: str  # the public test key; the secret never leaves the server
    hold_expires_at: datetime
    # How long Checkout may stay open: a little less than what is left of the hold.
    checkout_timeout_seconds: int


class VerifyRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=64)
    razorpay_payment_id: str = Field(min_length=1, max_length=64)
    razorpay_signature: str = Field(min_length=1, max_length=256)


class VerifyOut(BaseModel):
    # CONFIRMED = booked. ALREADY_CONFIRMED = this payment was processed before (e.g. by the webhook).
    # REFUNDED_LATE = it arrived after the hold ran out and the slot was gone: the fee is refunded.
    outcome: str
    booking: BookingOut
    otp: str | None = Field(default=None, description="Shown ONCE. Null when the code was already issued or the booking was refunded.")
    refund_amount: float = 0
    message: str


class WebhookAck(BaseModel):
    status: str  # processed | duplicate | ignored
