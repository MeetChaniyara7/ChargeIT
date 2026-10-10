"""Google sign-in: the redirect flow and the ID-token ("Sign in with Google" button) flow.

Either way, Google's answer is verified on the server before we trust it.
"""

import urllib.parse

import httpx
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _redirect_flow_settings() -> tuple[str, str | None, str]:
    """Client ID, secret and redirect URI for the redirect flow (the last two are optional settings)."""
    settings = get_settings()
    if not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google redirect sign-in is not configured (GOOGLE_REDIRECT_URI missing).",
        )
    return settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri


def get_google_auth_url(state: str) -> str:
    """Generate official Google OAuth 2.0 authorization URL.

    `state` must be a fresh random value that the callback checks (CSRF protection).
    """
    client_id, _, redirect_uri = _redirect_flow_settings()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account"
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

async def exchange_code_for_google_user(code: str) -> dict:
    """Exchange OAuth authorization code for Google access token and fetch verified user profile."""
    client_id, client_secret, redirect_uri = _redirect_flow_settings()
    if not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google redirect sign-in is not configured (GOOGLE_CLIENT_SECRET missing).",
        )

    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to authenticate with Google. Invalid authorization code."
            )
        
        tokens = token_resp.json()
        google_access_token = tokens.get("access_token")

        if not google_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth response did not contain an access token."
            )

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve Google user profile info."
            )

        return userinfo_resp.json()

def verify_google_id_token(token: str) -> dict:
    """Verify Google ID token (credential) from Google Identity Services JS SDK."""
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            get_settings().google_client_id,
        )
        return id_info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google ID token credential: {str(e)}"
        )
