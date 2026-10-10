"""The API must refuse to start without its required secrets (no unsafe defaults)."""

import pytest

from app.config import BOOKING_RULES, MissingSettingError, Settings

VALID_ENV = {
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/db",
    "JWT_SECRET_KEY": "secret",
    "GOOGLE_CLIENT_ID": "client-id",
    "FRONTEND_URL": "http://localhost:5173/",
}


@pytest.mark.parametrize("missing", ["DATABASE_URL", "JWT_SECRET_KEY", "GOOGLE_CLIENT_ID", "FRONTEND_URL"])
def test_refuses_to_start_without_required_setting(missing):
    env = {k: v for k, v in VALID_ENV.items() if k != missing}
    with pytest.raises(MissingSettingError, match=missing):
        Settings.from_env(env)


def test_blank_value_counts_as_missing():
    with pytest.raises(MissingSettingError, match="JWT_SECRET_KEY"):
        Settings.from_env({**VALID_ENV, "JWT_SECRET_KEY": "   "})


def test_defaults_and_cors_fallback():
    settings = Settings.from_env(VALID_ENV)
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_expire_minutes == 1440
    assert settings.frontend_url == "http://localhost:5173"  # trailing slash removed
    assert settings.cors_origins == ("http://localhost:5173",)  # defaults to the web app
    assert settings.cookies_secure is False


def test_cors_origins_list_is_parsed():
    settings = Settings.from_env({**VALID_ENV, "CORS_ORIGINS": "http://a.test, http://b.test/"})
    assert settings.cors_origins == ("http://a.test", "http://b.test")


def test_refund_tiers_match_architecture_doc():
    tiers = [(t.min_minutes_before, t.percent) for t in BOOKING_RULES.refund_tiers]
    assert tiers == [(120, 100), (30, 75), (15, 50), (0, 0)]
