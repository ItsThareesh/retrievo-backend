from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.db.db import get_session
from app.models.notification import Notification
from app.utils.auth_helper import get_current_user_required, get_db_user


router = APIRouter()

@router.get("/")
async def get_my_notifications(
    limit: int = 20,
    unread_only: bool = False,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    query = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )

    if unread_only:
        query = query.where(Notification.is_read == False)

    notifications = session.exec(query).all()

    print(notifications)

    return {"notifications": notifications}

@router.get("/count")
async def get_unread_notifications_count(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    count = session.exec(
        select(func.count(Notification.id))
        .where(Notification.user_id == user.id)
        .where(Notification.is_read == False)
    ).one()

    return { "count": count }

@router.post("/{id}/mark-read")
async def mark_notification_read(
    id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    notif = session.exec(
        select(Notification)
        .where(Notification.id == id)
        .where(Notification.user_id == user.id)
    ).first()

    if not notif:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    notif.is_read = True
    session.add(notif)
    session.commit()

    return {"ok": True}

@router.post("/mark-all-read")
async def mark_all_notifications_read(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    notifications = session.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .where(Notification.is_read == False)
    ).all()

    for notif in notifications:
        notif.is_read = True
        session.add(notif)

    session.commit()

    return {"ok": True}
