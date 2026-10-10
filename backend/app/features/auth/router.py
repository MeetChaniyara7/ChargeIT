"""Login endpoints: email/password, Google redirect flow, Google ID-token flow, current user.

Two routers exist because the web app calls the Google endpoints under /api/auth and
the rest under /auth. Both paths are kept so existing front-end calls keep working.
"""

import secrets
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.features.auth import schemas
from app.features.auth.dependencies import get_current_user
from app.features.auth.google import exchange_code_for_google_user, get_google_auth_url, verify_google_id_token
from app.features.auth.models import User
from app.features.auth.passwords import hash_password, verify_password
from app.features.auth.service import find_or_create_google_user, token_response

router = APIRouter(prefix="/auth", tags=["Authentication"])
api_router = APIRouter(prefix="/api/auth", tags=["Authentication API"])

OAUTH_STATE_COOKIE = "chargespot_oauth_state"
OAUTH_STATE_MAX_AGE_SECONDS = 600


# --- 1. EMAIL REGISTER ---
@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    email_clean = payload.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    user = User(
        user_id=uuid.uuid4(),
        email=email_clean,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="USER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user)


# --- 2. EMAIL LOGIN ---
@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    email_clean = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return token_response(user)


# --- 3. GOOGLE OAUTH REDIRECT FLOW ---
@router.get("/google/login")
@api_router.get("/google/login")
def google_login_redirect():
    # CSRF protection: a fresh random `state` goes to Google and into a short-lived cookie.
    # The callback only continues if Google sends back the same value the browser holds.
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(url=get_google_auth_url(state))
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookies_secure,
    )
    return response


@router.get("/google/callback")
@api_router.get("/google/callback")
async def google_callback(
    code: str,
    state: str | None = None,
    expected_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    db: Session = Depends(get_db),
):
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Sign-in request expired or was tampered with. Please try again.")

    google_profile = await exchange_code_for_google_user(code)

    google_sub = google_profile.get("sub")
    email = google_profile.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Google authentication profile missing required fields.")
    name = google_profile.get("name") or google_profile.get("given_name") or email.split("@")[0]

    user = find_or_create_google_user(db, google_sub, email, name)
    token = token_response(user)["access_token"]

    # Hand our JWT to the web app in the URL fragment (fragments are never sent to servers).
    response = RedirectResponse(url=f"{get_settings().frontend_url}/login#token={token}")
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


# --- 4. GOOGLE IDENTITY SERVICES ID TOKEN CREDENTIAL FLOW ---
@router.post("/google", response_model=schemas.TokenResponse)
@api_router.post("/google", response_model=schemas.TokenResponse)
def google_id_token_login(payload: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    id_info = verify_google_id_token(payload.credential)

    google_sub = id_info.get("sub")
    email = id_info.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Google ID token missing sub or email claims.")
    name = id_info.get("name") or id_info.get("given_name") or email.split("@")[0]

    user = find_or_create_google_user(db, google_sub, email, name)
    return token_response(user)


# --- 5. GET AUTHENTICATED USER ME ---
@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
