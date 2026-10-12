"""One-time codes: hashing, the validity window, and uniqueness."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import AppError
from app.features.bookings import otp

SECRET = "unit-test-secret"
START = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def draws(monkeypatch):
    """Control which numbers the code generator 'randomly' picks."""

    def use(*numbers):
        sequence = iter(numbers)
        monkeypatch.setattr(secrets, "randbelow", lambda n: next(sequence))

    return use


def test_the_hash_is_a_keyed_hmac_not_a_plain_hash():
    digest = otp.hash_code("482913", SECRET)
    assert digest != hashlib.sha256(b"482913").hexdigest()  # a plain hash of 6 digits can be cracked in a second
    assert digest == otp.hash_code("482913", SECRET)
    assert digest != otp.hash_code("482913", "another-secret")
    assert "482913" not in digest


def test_correct_and_wrong_code():
    stored = otp.hash_code("482913", SECRET)
    assert otp.matches("482913", stored, SECRET)
    assert not otp.matches("482914", stored, SECRET)
    for bad in ("", "12345", "1234567", "abcdef", "48291 "):
        assert not otp.matches(bad, stored, SECRET)
    assert not otp.matches("482913", None, SECRET)


def test_generated_codes_are_six_digits_and_do_not_store_the_code():
    code, digest = otp.generate([], SECRET)
    assert len(code) == 6 and code.isdigit()
    assert otp.matches(code, digest, SECRET) and code not in digest


def test_leading_zeros_are_kept(draws):
    draws(42)
    assert otp.generate([], SECRET)[0] == "000042"


@pytest.mark.parametrize(
    "offset_minutes, valid",
    [(-16, False), (-15.01, False), (-15, True), (-1, True), (0, True), (9.99, True), (10, True), (10.01, False), (60, False)],
)
def test_valid_from_15_minutes_before_to_10_minutes_after_start(offset_minutes, valid):
    assert otp.is_valid_now(START, START + timedelta(minutes=offset_minutes), None) is valid


def test_a_used_code_is_never_valid():
    assert not otp.is_valid_now(START, START, used_at=START)


def test_window_boundaries():
    opens, closes = otp.window(START)
    assert opens == START - timedelta(minutes=15) and closes == START + timedelta(minutes=10)


def test_windows_overlap_only_when_starts_are_close():
    assert otp.windows_overlap(START, START)
    assert otp.windows_overlap(START, START + timedelta(minutes=24))
    assert not otp.windows_overlap(START, START + timedelta(minutes=25))  # one closes exactly as the other opens
    assert not otp.windows_overlap(START, START - timedelta(hours=2))


def test_a_collision_with_a_live_code_at_the_station_is_avoided(draws):
    draws(111111, 111111, 222222)  # the first two draws collide with a code already in use
    code, _ = otp.generate([otp.hash_code("111111", SECRET)], SECRET)
    assert code == "222222"


def test_gives_up_with_a_clear_error_if_no_free_code_can_be_found(draws):
    draws(*[7] * 100)
    with pytest.raises(AppError) as error:
        otp.generate([otp.hash_code("000007", SECRET)], SECRET)
    assert error.value.code == "OTP_UNAVAILABLE"
