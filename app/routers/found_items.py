from fastapi import APIRouter, Depends, Form
from datetime import datetime
from sqlmodel import Session, select
from app.db.db import get_session
from app.models.found_item import FoundItem
from app.utils.auth_helper import get_current_user

router = APIRouter()


@router.post("/")
async def add_found_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))

    db_item = FoundItem(
        user_id=current_user["sub"],
        reporter_public_id=current_user["public_id"],
        reporter_name=current_user["name"],
        title=title,
        description=description,
        category=category,
        date=parsed_date,
        location=location,
    )

    session.add(db_item)
    session.commit()
    session.refresh(db_item)

    return True
