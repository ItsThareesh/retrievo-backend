from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlmodel import Session, select

from app.db.db import get_session
from app.models.item import Item
from app.models.user import User
from app.utils.auth_helper import get_current_user_optional, get_current_user_required, get_user_hostel
from app.utils.s3_service import get_all_urls


router = APIRouter()


@router.post("/set-hostel/{hostel}")
async def set_hostel(
    hostel: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = session.exec(select(User).where(User.id == current_user["sub"])).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hostel = hostel
    session.add(user)
    session.commit()
    session.refresh(user)

    return True


@router.get("/me")
async def get_my_profile(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = session.exec(select(User).where(User.id == current_user["sub"])).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/my-items")
async def get_my_items(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    items = session.exec(
        select(Item)
        .where(Item.user_id == current_user["sub"])
        .order_by(Item.created_at.desc())
    ).all()

    # Separate by type
    lost_items = [item for item in items if item.type == "lost"]
    found_items = [item for item in items if item.type == "found"]

    lost_items_response = get_all_urls(lost_items)
    found_items_response = get_all_urls(found_items)

    return {
        "lost_items": lost_items_response,
        "found_items": found_items_response,
    }


# @router.get("/found-items")
# async def get_my_found_items_by_cat(
#     category: str,
#     session: Session = Depends(get_session),
#     current_user=Depends(get_current_user_required),
# ):
#     query = (
#         select(Item)
#         .where(Item.user_id == current_user["sub"])
#         .where(Item.type == "found")
#         .where(Item.category == category)
#         .order_by(Item.created_at.desc())
#     )

#     items = session.exec(query).all()

#     items_response = get_all_urls(items)

#     return items_response


@router.get("/{public_id}")
async def get_profile(
    public_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = get_user_hostel(current_user, session)

    # Fetch user from ID
    user = session.exec(
        select(User).where(User.public_id == public_id)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = select(Item).where(Item.user_id == user.id)

    # Apply visibility filters based on user's hostel
    if hostel:
        query = query.where((Item.visibility == hostel) | (Item.visibility == 'public'))

    # Fetch items
    items = session.exec(query).all()

    # Separate by type
    lost_items = [item for item in items if item.type == "lost"]
    found_items = [item for item in items if item.type == "found"]

    lost_items_response = get_all_urls(lost_items)
    found_items_response = get_all_urls(found_items)

    return {
        "user": {
            "name": user.name,
            "email": user.email,
            "image": user.image,
            "created_at": user.created_at,
        },
        "lost_items": lost_items_response,
        "found_items": found_items_response,
    }
