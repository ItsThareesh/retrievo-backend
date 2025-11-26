from fastapi import APIRouter, Depends, UploadFile, File, Form
from datetime import datetime
from sqlmodel import Session, select
from app.db.db import get_session
from app.models.lost_item import LostItem

router = APIRouter()


@router.post("/")
async def add_lost_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    session: Session = Depends(get_session),
):
    parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))

    db_item = LostItem(
        title=title,
        description=description,
        category=category,
        date_lost=parsed_date,
        location_lost=location,
    )

    session.add(db_item)
    session.commit()
    session.refresh(db_item)

    return {"status": "ok"}


@router.get("/")
async def get_lost_items(session: Session = Depends(get_session)):
    items = session.exec(select(LostItem).order_by(LostItem.created_at.desc())).all()
    return items


@router.get("/{item_id}")
async def get_lost_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(LostItem, item_id)
    if not item:
        return {"error": "Item not found"}
    return item
