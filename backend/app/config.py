"""All settings for the ChargeSpot API, in one place.

Two kinds of values live here:
1. Settings: read from environment variables (the .env file locally). Secrets are
   never hard-coded. If a required one is missing, the API refuses to start, so a
   misconfigured server fails loudly instead of running with an unsafe default.
2. Business rules: the numbers agreed in docs/architecture.md section 15 (slot length,
   fees, time windows, refund tiers). Keeping them here means a rule can be tuned
   without touching business logic.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

APP_NAME = "ChargeSpot API"
APP_VERSION = "0.1.0"

REQUIRED_SETTINGS = ("DATABASE_URL", "JWT_SECRET_KEY", "GOOGLE_CLIENT_ID", "FRONTEND_URL")


class MissingSettingError(RuntimeError):
    """Raised at startup when a required environment variable is not set."""


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    google_client_id: str
    google_client_secret: str | None
    google_redirect_uri: str | None
    frontend_url: str
    cors_origins: tuple[str, ...]

    @property
    def cookies_secure(self) -> bool:
        # Cookies are marked Secure whenever the site itself is served over HTTPS.
        return self.frontend_url.startswith("https://")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        def get(name: str) -> str | None:
            value = env.get(name, "").strip().strip("\"'")
            return value or None

        missing = [name for name in REQUIRED_SETTINGS if not get(name)]
        if missing:
            raise MissingSettingError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Copy backend/.env.example to backend/.env and fill them in."
            )

        frontend_url = get("FRONTEND_URL").rstrip("/")
        cors = get("CORS_ORIGINS")
        cors_origins = tuple(o.strip().rstrip("/") for o in cors.split(",") if o.strip()) if cors else (frontend_url,)

        return cls(
            database_url=get("DATABASE_URL"),
            jwt_secret_key=get("JWT_SECRET_KEY"),
            jwt_algorithm=get("JWT_ALGORITHM") or "HS256",
            jwt_expire_minutes=int(get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES") or 1440),
            google_client_id=get("GOOGLE_CLIENT_ID"),
            google_client_secret=get("GOOGLE_CLIENT_SECRET"),
            google_redirect_uri=get("GOOGLE_REDIRECT_URI"),
            frontend_url=frontend_url,
            cors_origins=cors_origins,
        )


@lru_cache
def get_settings() -> Settings:
    """Load settings once. The .env file never overrides real environment variables."""
    load_dotenv()
    return Settings.from_env()


@dataclass(frozen=True)
class RefundTier:
    """Refund for cancelling at least `min_minutes_before` minutes before the slot starts."""

    min_minutes_before: int
    percent: int


@dataclass(frozen=True)
class BookingRules:
    """Business rules from docs/architecture.md section 15. All durations are minutes."""

    slot_minutes: int = 30
    min_blocks_per_booking: int = 1
    max_blocks_per_booking: int = 4
    max_days_ahead: int = 7
    payment_hold_minutes: int = 5
    walkin_qr_hold_minutes: int = 3
    booking_fee_inr: int = 199
    otp_valid_before_start: int = 15
    otp_valid_after_start: int = 10
    reservation_lock_before_start: int = 15
    no_show_after_start: int = 10
    end_of_slot_warning: int = 5
    buffer_before_next_booking: int = 5
    instant_booking_max_minutes: int = 120
    walkin_amounts_inr: tuple[int, ...] = (100, 200, 500)
    # Checked top to bottom: the first tier the cancellation qualifies for wins.
    refund_tiers: tuple[RefundTier, ...] = (
        RefundTier(min_minutes_before=120, percent=100),
        RefundTier(min_minutes_before=30, percent=75),
        RefundTier(min_minutes_before=15, percent=50),
        RefundTier(min_minutes_before=0, percent=0),
    )
    kiosk_wrong_otp_limit: int = 5
    kiosk_cooldown_minutes: int = 2
    kiosk_alert_threshold: int = 20
    kiosk_alert_window_minutes: int = 10
    kiosk_idle_reset_seconds: int = 30
    recommendation_radius_km: float = 15.0
    duplicate_station_distance_m: float = 50.0
    display_timezone: str = "Asia/Kolkata"


BOOKING_RULES = BookingRules()
