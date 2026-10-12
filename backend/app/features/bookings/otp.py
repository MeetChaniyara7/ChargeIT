"""One-time codes: the 6 digits a driver types at the kiosk.

- Only an HMAC-SHA256 of the code is stored (with the server secret OTP_SECRET), never the
  code itself. A plain hash of 6 digits could be cracked in a second; the secret prevents that.
- A code is valid from 15 minutes before the slot starts to 10 minutes after, once.
- Among bookings that could be at the same station in overlapping windows, codes are unique,
  so a code typed at the kiosk identifies exactly one booking.
"""

import hashlib
import hmac
import secrets
from collections.abc import Iterable
from datetime import datetime, timedelta

from app.config import BOOKING_RULES, require_setting
from app.core.errors import AppError
from app.core.slots import as_utc

CODE_DIGITS = 6
MAX_TRIES = 25


def hash_code(code: str, secret: str | None = None) -> str:
    secret = secret or require_setting("otp_secret")
    return hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def matches(code: str, stored_hash: str | None, secret: str | None = None) -> bool:
    """Constant-time comparison, so response timing reveals nothing about the code."""
    if not stored_hash or len(code) != CODE_DIGITS or not code.isdigit():
        return False
    return hmac.compare_digest(hash_code(code, secret), stored_hash)


def window(start: datetime) -> tuple[datetime, datetime]:
    """When a booking starting at `start` accepts its code."""
    s = as_utc(start)
    return (
        s - timedelta(minutes=BOOKING_RULES.otp_valid_before_start),
        s + timedelta(minutes=BOOKING_RULES.otp_valid_after_start),
    )


def is_valid_now(start: datetime, now: datetime, used_at: datetime | None) -> bool:
    if used_at is not None:
        return False
    opens, closes = window(start)
    return opens <= as_utc(now) <= closes


def windows_overlap(a_start: datetime, b_start: datetime) -> bool:
    a_open, a_close = window(a_start)
    b_open, b_close = window(b_start)
    return a_open < b_close and b_open < a_close


def generate(taken_hashes: Iterable[str], secret: str | None = None) -> tuple[str, str]:
    """A fresh code and its hash, different from every hash in `taken_hashes`.

    `taken_hashes` are the stored hashes of the other bookings at the same station whose
    code windows overlap this one (the caller looks them up).
    """
    taken = set(taken_hashes)
    for _ in range(MAX_TRIES):
        code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        digest = hash_code(code, secret)
        if digest not in taken:
            return code, digest
    raise AppError(503, "OTP_UNAVAILABLE", "Couldn't create a unique code. Please try again.")
