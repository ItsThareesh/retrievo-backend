import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from jose import jwt
from sqlmodel import Session, select
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from app.db.db import get_session
from app.models.users import User

router = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET", 'your_really_long_secret_key')
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

if not CLIENT_ID or not SECRET_KEY:
    raise ValueError("Environment variables not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 1 day


class GoogleIDToken(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    user_id: str


@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleIDToken, session: Session = Depends(get_session)):
    try:
        idinfo = id_token.verify_oauth2_token(payload.id_token, grequests.Request(), CLIENT_ID)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    # idinfo now trusted and parsed by Google libs
    google_id = idinfo["sub"]
    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    db_user = session.exec(select(User).where(User.google_id == google_id)).first()
    if not db_user:
        db_user = User(
            google_id=google_id,
            name=name,
            profile_picture=picture,
            email=email,
            role="user",
        )
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    expiry = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    jwt_payload = {
        "sub": str(db_user.id),
        "role": db_user.role,
        "iat": datetime.now(timezone.utc),
        "exp": expiry,
    }

    token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

    return TokenResponse(
        access_token=token,
        user_id=str(db_user.id),
    )
