"""Login tokens and the Google redirect-flow CSRF check."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from app.features.auth.router import OAUTH_STATE_COOKIE
from app.features.auth.tokens import create_access_token, decode_access_token


def test_me_without_token_is_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_with_garbage_token_is_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_token_round_trip():
    token = create_access_token({"sub": "user-123", "role": "USER"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "USER"
    assert "exp" in payload


def test_tampered_token_is_rejected():
    token = create_access_token({"sub": "user-123"})
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(HTTPException) as exc:
        decode_access_token(tampered)
    assert exc.value.status_code == 401


def test_expired_token_is_rejected():
    token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(HTTPException):
        decode_access_token(token)


def test_google_redirect_sets_random_state(client):
    first = client.get("/auth/google/login", follow_redirects=False)
    second = client.get("/auth/google/login", follow_redirects=False)
    assert first.status_code == 307

    state_in_url = parse_qs(urlparse(first.headers["location"]).query)["state"][0]
    assert state_in_url == first.cookies[OAUTH_STATE_COOKIE]
    assert len(state_in_url) >= 32
    assert state_in_url != second.cookies[OAUTH_STATE_COOKIE]  # fresh every time


def test_google_callback_rejects_wrong_state(client):
    client.cookies.set(OAUTH_STATE_COOKIE, "the-real-state")
    response = client.get("/auth/google/callback", params={"code": "x", "state": "forged-state"})
    assert response.status_code == 400


def test_google_callback_rejects_missing_state_cookie(client):
    response = client.get("/auth/google/callback", params={"code": "x", "state": "anything"})
    assert response.status_code == 400
