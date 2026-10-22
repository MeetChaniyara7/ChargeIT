"""Kiosk device keys: ks_<prefix>_<secret>.

The key is shown once, when the device is created. The database keeps only the prefix (to find the row)
and a SHA-256 hash of the whole key. The secret part is 192 random bits, so a plain fast hash is enough
(unlike a 6-digit code, it cannot be guessed or cracked).
"""

import hashlib
import hmac
import secrets

KEY_MARK = "ks_"


def generate() -> tuple[str, str, str]:
    """(the full key, its prefix, its hash)."""
    prefix = secrets.token_hex(4)
    key = f"{KEY_MARK}{prefix}_{secrets.token_urlsafe(24)}"
    return key, prefix, hash_key(key)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def prefix_of(key: str) -> str | None:
    """The prefix inside a key, or None when the text is not shaped like a key."""
    parts = key.strip().split("_", 2)
    if len(parts) != 3 or parts[0] + "_" != KEY_MARK or not parts[1] or not parts[2]:
        return None
    return parts[1]


def matches(key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_key(key.strip()), stored_hash)
