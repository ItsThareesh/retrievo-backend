import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from jose import JWTError, jwt
from sqlmodel import Session, select
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from app.db.db import get_session
from app.models.user import User

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
    expires_at: int  # Unix timestamp


class RefreshTokenRequest(BaseModel):
    token: str


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

    # if email.split("@")[-1] != "nitc.ac.in":
    #     raise HTTPException(status_code=401, detail="Unauthorized domain")

    db_user = session.exec(select(User).where(User.public_id == google_id)).first()
    if not db_user:
        db_user = User(
            public_id=google_id,
            name=name,
            image=picture,
            email=email,
            role="user",        
        )
        session.add(db_user)
        session.commit()
        session.refresh(db_user)

    expiry = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    jwt_payload = {
        "sub": db_user.public_id,
        "iat": datetime.now(timezone.utc),
        "exp": expiry,
    }

    token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)

    return TokenResponse(access_token=token, expires_at=int(expiry.timestamp()))


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, session: Session = Depends(get_session)):
    """
    Refresh an existing JWT token.
    Validates the current token and issues a new one if it's still valid.
    """
    try:
        # Decode the existing token (this will fail if token is invalid or expired)
        decoded = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Get the user from the database
        google_id = decoded.get("sub")
        if not google_id:
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        db_user = session.exec(select(User).where(User.public_id == google_id)).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create a new token with fresh expiration
        expiry = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        jwt_payload = {
            "sub": db_user.public_id,
            "iat": datetime.now(timezone.utc),
            "exp": expiry,
        }
        
        new_token = jwt.encode(jwt_payload, SECRET_KEY, algorithm=ALGORITHM)
        
        return TokenResponse(access_token=new_token, expires_at=int(expiry.timestamp()))
        
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
