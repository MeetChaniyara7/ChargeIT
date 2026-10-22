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

    def create_payment_link(self, amount_paise: int, reference_id: str, description: str, notes: dict[str, str]) -> tuple[str, str]:
        """Create a payment link (what the kiosk shows as a QR) and return (link id, URL)."""

    def payment_link_status(self, link_id: str) -> tuple[str, str | None]:
        """Ask Razorpay about a link: (status, id of the captured payment or None). Status is created, paid, cancelled or expired."""


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

    def create_payment_link(self, amount_paise: int, reference_id: str, description: str, notes: dict[str, str]) -> tuple[str, str]:
        import razorpay

        client = razorpay.Client(auth=(require_setting("razorpay_key_id"), require_setting("razorpay_key_secret")))
        try:
            link = client.payment_link.create(
                {
                    "amount": amount_paise, "currency": "INR", "accept_partial": False, "reference_id": reference_id,
                    "description": description, "notes": notes, "reminder_enable": False,
                }
            )
        except Exception as exc:
            logger.exception("Razorpay payment link creation failed")
            raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment service is not responding. Please try again.") from exc
        return link["id"], link["short_url"]

    def payment_link_status(self, link_id: str) -> tuple[str, str | None]:
        import razorpay

        client = razorpay.Client(auth=(require_setting("razorpay_key_id"), require_setting("razorpay_key_secret")))
        try:
            link = client.payment_link.fetch(link_id)
        except Exception as exc:
            logger.exception("Razorpay payment link lookup failed")
            raise AppError(502, "PAYMENT_PROVIDER_ERROR", "The payment service is not responding. Please try again.") from exc
        captured = next((p.get("payment_id") for p in link.get("payments") or [] if p.get("status") == "captured"), None)
        return link.get("status", "created"), captured


def get_gateway() -> Gateway:
    """FastAPI dependency (overridden in tests)."""
    return RazorpayGateway()
