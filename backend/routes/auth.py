import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth.password import hash_password, verify_password
from auth.jwt import create_access_token, get_current_user
from auth.google import get_google_auth_url, exchange_code_for_google_user, verify_google_id_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
api_router = APIRouter(prefix="/api/auth", tags=["Authentication API"])

def find_or_create_google_user(db: Session, google_sub: str, email: str, name: str) -> models.UserProfile:
    """Helper function to find existing user by google_user_id or email, or create a new user safely."""
    # 1. Check if user exists by google_user_id (sub)
    user = db.query(models.UserProfile).filter(models.UserProfile.google_user_id == google_sub).first()
    if user:
        return user

    # 2. Check if user exists by email (link accounts)
    user = db.query(models.UserProfile).filter(models.UserProfile.email == email.lower()).first()
    if user:
        user.google_user_id = google_sub
        if not user.full_name and name:
            user.full_name = name
        db.commit()
        db.refresh(user)
        return user

    # 3. Create new user record
    user = models.UserProfile(
        user_id=uuid.uuid4(),
        google_user_id=google_sub,
        email=email.lower(),
        full_name=name or email.split("@")[0],
        password_hash=None,
        phone=None,
        role="USER"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- 1. EMAIL REGISTER ---
@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    email_clean = payload.email.lower().strip()
    existing_user = db.query(models.UserProfile).filter(models.UserProfile.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    hashed_pw = hash_password(payload.password)
    user = models.UserProfile(
        user_id=uuid.uuid4(),
        email=email_clean,
        full_name=payload.full_name.strip(),
        password_hash=hashed_pw,
        role="USER"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": user}


# --- 2. EMAIL LOGIN ---
@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    email_clean = payload.email.lower().strip()
    user = db.query(models.UserProfile).filter(models.UserProfile.email == email_clean).first()
    
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": user}


# --- 3. GOOGLE OAUTH REDIRECT FLOW ---
@router.get("/google/login")
@api_router.get("/google/login")
def google_login_redirect():
    url = get_google_auth_url()
    return RedirectResponse(url=url)


@router.get("/google/callback")
@api_router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    google_profile = await exchange_code_for_google_user(code)
    
    google_sub = google_profile.get("sub")
    email = google_profile.get("email")
    name = google_profile.get("name") or google_profile.get("given_name") or email.split("@")[0]

    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Google authentication profile missing required fields.")

    user = find_or_create_google_user(db, google_sub, email, name)
    token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role})

    # Redirect to React frontend with application JWT token
    frontend_url = f"http://localhost:5173/login#token={token}"
    return RedirectResponse(url=frontend_url)


# --- 4. GOOGLE IDENTITY SERVICES ID TOKEN CREDENTIAL FLOW ---
@router.post("/google", response_model=schemas.TokenResponse)
@api_router.post("/google", response_model=schemas.TokenResponse)
def google_id_token_login(payload: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    id_info = verify_google_id_token(payload.credential)

    google_sub = id_info.get("sub")
    email = id_info.get("email")
    name = id_info.get("name") or id_info.get("given_name") or email.split("@")[0]

    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Google ID token missing sub or email claims.")

    user = find_or_create_google_user(db, google_sub, email, name)
    token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role})

    return {"access_token": token, "token_type": "bearer", "user": user}


# --- 5. GET AUTHENTICATED USER ME ---
@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.UserProfile = Depends(get_current_user)):
    return current_user
