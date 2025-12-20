import os
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlmodel import Session, select

from app.models.user import User

bearer_scheme_optional = HTTPBearer(auto_error=False)


def get_current_user_optional(token: HTTPAuthorizationCredentials = Depends(bearer_scheme_optional)):
    if not token:
        return None

    try:
        payload = jwt.decode(token.credentials, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except JWTError:
        return None
    
bearer_scheme_required = HTTPBearer(auto_error=True)

def get_current_user_required(token: HTTPAuthorizationCredentials = Depends(bearer_scheme_required)):
    try:
        payload = jwt.decode(
            token.credentials,
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"],
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_hostel(session: Session, current_user):
    # user lookup for getting hostel preference
    if current_user:
        user = session.exec(
            select(User).where(User.public_id == current_user["sub"])
        ).first()

        if user:
            return user.hostel

    return None

def get_db_user(session: Session, current_user):
    user = session.exec(
        select(User).where(User.public_id == current_user["sub"])
    ).first()

    print(user)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user