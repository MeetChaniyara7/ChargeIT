"""Payment endpoints: create the order, verify the result, receive Razorpay's webhook."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.payments import service
from app.features.payments.gateway import Gateway, get_gateway
from app.features.payments.schemas import OrderOut, OrderRequest, VerifyOut, VerifyRequest, WebhookAck

router = APIRouter(prefix="/api/payments", tags=["Payments"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/orders", response_model=OrderOut)
def create_order(
    body: OrderRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db), gateway: Gateway = Depends(get_gateway)
):
    """The ₹199 booking-fee order for a held booking (the same order again if you ask twice)."""
    return service.create_order(db, user.user_id, body.booking_id, gateway, _now())


@router.post("/verify", response_model=VerifyOut)
def verify_payment(body: VerifyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check Razorpay's signature, confirm the booking and return the one-time code (once)."""
    return service.verify(db, user.user_id, body, _now())


@router.post("/webhook", response_model=WebhookAck)
async def webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    x_razorpay_event_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Called by Razorpay, not by the browser. The signature covers the raw body, so read it untouched."""
    body = await request.body()
    return WebhookAck(status=service.handle_webhook(db, body, x_razorpay_signature, x_razorpay_event_id, _now()))
