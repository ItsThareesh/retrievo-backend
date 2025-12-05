from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.found_item import FoundItem
from app.models.lost_item import LostItem
from app.utils.auth_helper import get_current_user


router = APIRouter()


@router.get("/my-items")
async def get_my_items(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    found_items = session.exec(
        select(FoundItem)
        .where(FoundItem.user_id == current_user["sub"])
        .order_by(FoundItem.created_at.desc())
    ).all()

    lost_items = session.exec(
        select(LostItem)
        .where(LostItem.user_id == current_user["sub"])
        .order_by(LostItem.created_at.desc())
    ).all()

    return {
        "found_items": found_items,
        "lost_items": lost_items,
    }


@router.get("/found-items")
async def get_my_found_items_by_cat(
    category: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    query = (
        select(FoundItem)
        .where(FoundItem.user_id == current_user["sub"])
        .where(FoundItem.category == category)
        .order_by(FoundItem.created_at.desc())
    )

    items = session.exec(query).all()

    return items
