import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, select

from app.db.db import get_session
from app.models.item import Item
from app.models.notification import Notification
from app.models.resolution import Resolution
from app.utils.auth_helper import get_current_user_required, get_db_user


router = APIRouter()
    
class ResolutionCreateRequest(BaseModel):
    found_item_id: uuid.UUID
    claim_description: str = Field(min_length=20)

@router.post("/create")
def create_resolution(
    payload: ResolutionCreateRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    # Fetch found item
    found_item = session.get(Item, payload.found_item_id)
    if not found_item:
        raise HTTPException(status_code=404, detail="Item not found")

    if found_item.type != "found":
        raise HTTPException(status_code=400, detail="Item is not a found item")

    # Prevent self-claim
    if found_item.user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot claim your own item")

    # Block claims if already resolved
    approved = session.exec(
        select(Resolution)
        .where(Resolution.found_item_id == found_item.id)
        .where(Resolution.status == "approved")
    ).first()

    if approved:
        raise HTTPException(
            status_code=400,
            detail="This item has already been resolved",
        )

    # Prevent duplicate claim by same user
    existing = session.exec(
        select(Resolution)
        .where(Resolution.found_item_id == found_item.id)
        .where(Resolution.claimant_id == user.id)
        .where(Resolution.status == "pending")
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have a pending claim for this item",
        )

    # Create resolution
    resolution = Resolution(
        found_item_id=found_item.id,
        claimant_id=user.id,
        claim_description=payload.claim_description,
    )

    session.add(resolution)
    session.commit()
    session.refresh(resolution)

    # Notify finder
    notification = Notification(
        user_id=found_item.user_id,
        type="claim_created",
        title="New claim received",
        message=f"A user has submitted a claim for your found item '{found_item.title}'.",
        item_id=found_item.id,
    )

    session.add(notification)
    session.commit()

    return {
        "ok": True,
        "resolution_id": str(resolution.id),
    }
