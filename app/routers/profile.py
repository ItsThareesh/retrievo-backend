from fastapi import APIRouter
from fastapi.params import Depends
from sqlmodel import Session, select, func

from app.db.db import get_session
from app.models.item import Item
from app.models.notification import Notification
from app.utils.auth_helper import get_current_user_optional, get_current_user_required, get_db_user, get_user_hostel
from app.utils.s3_service import get_all_urls


router = APIRouter()


@router.post("/set-hostel/{hostel}")
async def set_hostel(
    hostel: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

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
    return get_db_user(session, current_user)


@router.get("/items")
async def get_my_items(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    items = session.exec(
        select(Item)
        .where(Item.user_id == user.id)
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


@router.get("/{public_id}")
async def get_profile(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = get_user_hostel(session, current_user)

    # Fetch user from ID
    user = get_db_user(session, current_user)

    query = select(Item).where(Item.user_id == user.id)

    # Apply visibility filters based on user's hostel
    if hostel:
        query = query.where((Item.visibility == hostel) | (Item.visibility == 'public'))
    else:
        query = query.where(Item.visibility == 'public')

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


@router.get("/notifications/count")
async def get_unread_notifications_count(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    count = session.exec(
        select(func.count())
        .select(Notification)
        .where(Notification.user_id == user.id)
        .where(Notification.is_read == False)
    ).one()

    return { "unread_count": count }

@router.get("/notifications")
async def get_my_notifications(
    limit: int = 20,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    notifications = session.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .where(Notification.is_read == False)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()

    return { "notifications": notifications }
