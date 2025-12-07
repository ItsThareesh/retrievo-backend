from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.found_item import FoundItem
from app.models.lost_item import LostItem
from app.models.user import User
from app.utils.auth_helper import get_current_user
from app.utils.s3_service import generate_signed_url


router = APIRouter()


@router.get("/me")
async def get_my_profile(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    user = session.exec(select(User).where(User.id == current_user["sub"])).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


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

    lost_items_response = []
    for item in lost_items:
        data = item.model_dump()
        data["image"] = generate_signed_url(item.image)
        lost_items_response.append(data)

    found_items_response = []
    for item in found_items:
        data = item.model_dump()
        data["image"] = generate_signed_url(item.image)
        found_items_response.append(data)

    return {
        "lost_items": lost_items_response,
        "found_items": found_items_response,
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


@router.get("/{public_id}")
async def get_profile(
    public_id: str,
    session: Session = Depends(get_session)
):
    user = session.exec(
        select(User).where(User.public_id == public_id)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Fetch items
    lost_items = session.exec(
        select(LostItem).where(LostItem.user_id == user.id)
    ).all()

    found_items = session.exec(
        select(FoundItem).where(FoundItem.user_id == user.id)
    ).all()

    return {
        "user": {
            "name": user.name,
            "email": user.email,
            "image": user.image,
            "created_at": user.created_at,
        },
        "lost_items": lost_items,
        "found_items": found_items,
    }
