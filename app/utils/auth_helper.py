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
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_hostel(current_user, session: Session):
    # user lookup for getting hostel preference
    if current_user:
        user = session.exec(
            select(User).where(User.id == current_user["sub"])
        ).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user.hostel

    return None
