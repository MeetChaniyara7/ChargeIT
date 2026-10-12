"""Talking to Razorpay (test mode), and checking that what comes back is genuine.

Two kinds of signatures are checked here, both plain HMAC-SHA256 so they are easy to test:
- the browser's payment result:  HMAC(key_secret, "<order_id>|<payment_id>")
- a webhook:                     HMAC(webhook_secret, <raw request body>)
The browser can be lied to; a payment is only believed when its signature checks out.
"""

import hashlib
import hmac
import logging
from typing import Protocol

from app.config import require_setting
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_payment_signature(order_id: str, payment_id: str, signature: str, key_secret: str) -> bool:
    expected = _sign(key_secret, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(body: bytes, signature: str, webhook_secret: str) -> bool:
    return hmac.compare_digest(_sign(webhook_secret, body), signature or "")


class Gateway(Protocol):
    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, str]) -> str:
        """Create an order and return Razorpay's order id."""


class RazorpayGateway:
    """The real thing. It talks to Razorpay over the network, so tests swap it for a fake."""

    def create_order(self, amount_paise: int, receipt: str, notes: dict[str, str]) -> str:
        import razorpay

        client = razorpay.Client(auth=(require_setting("razorpay_key_id"), require_setting("razorpay_key_secret")))
        try:
            order = client.order.create(
                {"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes, "payment_capture": 1}
            )
        except Exception as exc:  # the SDK raises several kinds of errors; to the driver they are all "try again"
            logger.exception("Razorpay order creation failed")
            raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment service is not responding. Please try again.") from exc
        return order["id"]


def get_gateway() -> Gateway:
    """FastAPI dependency (overridden in tests)."""
    return RazorpayGateway()
