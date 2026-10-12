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
    # Phase 4. Optional at startup so the rest of the API runs without them; the code that
    # needs one asks for it with require_setting() and answers 503 if it is missing.
    otp_secret: str | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

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
            otp_secret=get("OTP_SECRET"),
            razorpay_key_id=get("RAZORPAY_KEY_ID"),
            razorpay_key_secret=get("RAZORPAY_KEY_SECRET"),
            razorpay_webhook_secret=get("RAZORPAY_WEBHOOK_SECRET"),
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
    instant_min_minutes: int = 15  # "Charge now" needs at least this much free time before the next booking
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
    max_vehicles_per_user: int = 10
    # How far either side of a requested start we look for other free times on the same charger.
    alternative_search_hours: int = 3
    max_alternatives_per_group: int = 3


BOOKING_RULES = BookingRules()


@dataclass(frozen=True)
class RecommendationWeights:
    """How much each factor counts in the "best station" score. They add up to 1.

    Change a number here to change what "best" means; nothing else needs to change.
    """

    travel_time: float = 0.30  # nearer in time is better
    availability: float = 0.30  # more compatible chargers free in the window is better
    power: float = 0.15  # faster charging is better
    price: float = 0.10  # cheaper is better
    rating: float = 0.10  # better rated is better
    data_quality: float = 0.05  # real data beats estimated data


@dataclass(frozen=True)
class RecommendationRules:
    """Reference values that turn raw numbers (minutes, kW, rupees) into 0-1 scores."""

    max_results: int = 5
    candidate_pool: int = 10  # nearest stations (straight line) sent to OSRM for real drive times
    drive_speed_kmh: float = 25.0  # straight-line fallback speed when OSRM is unreachable
    slow_travel_minutes: float = 30.0  # a drive this long scores 0 for travel time
    full_availability_chargers: int = 3  # this many free chargers scores 1 for availability
    fast_power_kw: float = 120.0  # this power scores 1
    cheap_price_inr: float = 10.0  # at or below this price scores 1
    expensive_price_inr: float = 30.0  # at or above this price scores 0
    unknown_rating_score: float = 0.5  # neutral, so unrated stations are neither rewarded nor punished
    estimated_data_score: float = 0.5  # data_quality score of a station with estimated values
    min_duration_minutes: int = 30
    max_duration_minutes: int = 240


@dataclass(frozen=True)
class ExternalServices:
    """Free public services (no keys). Limits follow their usage policies."""

    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = 3.0
    osrm_cache_seconds: int = 60
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_min_interval_seconds: float = 1.1  # policy: at most 1 request per second
    nominatim_cache_days: int = 30
    nominatim_timeout_seconds: float = 8.0
    nominatim_max_wait_seconds: float = 5.0  # if the 1-per-second queue is longer than this, answer "busy"
    # Prefer places inside Gujarat (left,top,right,bottom). A preference only: other states still appear.
    nominatim_viewbox: str = "68.0,24.8,74.6,20.0"
    user_agent: str = "ChargeSpot/0.1 (college final-year project)"


@dataclass(frozen=True)
class SearchRules:
    """The Explore search box: suggestions while typing come only from our own database."""

    min_query_length: int = 2
    max_query_length: int = 80
    max_stations: int = 5
    max_operators: int = 3
    max_cities: int = 3
    # pg_trgm word similarity (0-1) a name needs to count as a match when it does not
    # contain the typed text. "tata powr" vs "Tata Power" scores about 0.8.
    match_similarity: float = 0.5
    # A close-but-not-exact match at least this similar becomes "Did you mean ...?".
    did_you_mean_similarity: float = 0.5
    # "cheap" in a search means at most this price per kWh. Mirrored in
    # frontend/shared/src/constants.ts (CHEAP_MAX_PRICE_INR).
    cheap_max_price_inr: float = 15.0


RECOMMENDATION_WEIGHTS = RecommendationWeights()
RECOMMENDATION_RULES = RecommendationRules()
EXTERNAL_SERVICES = ExternalServices()
SEARCH_RULES = SearchRules()


def require_setting(name: str) -> str:
    """A Phase 4 secret (OTP_SECRET, RAZORPAY_*), or a clear 503 if it was never set."""
    from app.core.errors import AppError  # imported here: errors.py must stay free of config

    value = getattr(get_settings(), name.lower())
    if not value:
        raise AppError(503, "SETTING_MISSING", f"The server is missing {name.upper()}. Set it in backend/.env.")
    return value
