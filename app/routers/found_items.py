from fastapi import APIRouter, Depends, Form
from datetime import datetime
from sqlmodel import Session, select
from app.db.db import get_session
from app.models.found_item import FoundItem

router = APIRouter()


@router.post("/")
async def add_found_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    session: Session = Depends(get_session),
):
    parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))

    db_item = FoundItem(
        title=title,
        description=description,
        category=category,
        date_found=parsed_date,
        location_found=location,
    )

    session.add(db_item)
    session.commit()
    session.refresh(db_item)

    print(f"Received Found Item: {db_item}")

    return {"status": "ok"}


@router.get("/")
async def get_found_items(session: Session = Depends(get_session)):
    items = session.exec(select(FoundItem).order_by(FoundItem.created_at.desc())).all()
    return items


@router.get("/{item_id}")
async def get_found_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(FoundItem, item_id)
    if not item:
        return {"error": "Item not found"}
    return item
