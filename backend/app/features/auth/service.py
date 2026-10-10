"""Account rules shared by the login routes."""

import uuid

from sqlalchemy.orm import Session

from app.features.auth.models import User
from app.features.auth.tokens import create_access_token


def find_or_create_google_user(db: Session, google_sub: str, email: str, name: str) -> User:
    """Find the user by Google ID, else link an existing account with the same email, else create one."""
    # 1. Check if user exists by google_user_id (sub)
    user = db.query(User).filter(User.google_user_id == google_sub).first()
    if user:
        return user

    # 2. Check if user exists by email (link accounts)
    user = db.query(User).filter(User.email == email.lower()).first()
    if user:
        user.google_user_id = google_sub
        if not user.full_name and name:
            user.full_name = name
        db.commit()
        db.refresh(user)
        return user

    # 3. Create new user record
    user = User(
        user_id=uuid.uuid4(),
        google_user_id=google_sub,
        email=email.lower(),
        full_name=name or email.split("@")[0],
        password_hash=None,
        phone=None,
        role="USER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def token_response(user: User) -> dict:
    """The body returned by every successful login: our JWT plus the user's profile."""
    token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": user}
