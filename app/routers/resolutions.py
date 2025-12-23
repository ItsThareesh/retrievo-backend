import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, Session, select

from app.db.db import get_session
from app.models.item import Item
from app.models.notification import Notification
from app.models.resolution import Resolution
from app.utils.auth_helper import get_current_user_required, get_db_user
from app.utils.s3_service import generate_signed_url
from app.models.user import User


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
            status_code=409,
            detail="Already a pending claim for this item exists",
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
        resolution_id=resolution.id,
    )

    session.add(notification)
    session.commit()

    return {
        "ok": True,
        "resolution_id": str(resolution.id),
    }

class ResolutionRejectRequest(BaseModel):
    resolutionID: uuid.UUID
    rejection_reason: str = Field(min_length=20, max_length=280)

@router.post("/reject")
def reject_resolution(
    payload: ResolutionRejectRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    # Fetch resolution
    resolution = session.get(Resolution, payload.resolutionID)
    if not resolution:
        raise HTTPException(status_code=404, detail="Resolution not found")

    # Fetch found item
    found_item = session.get(Item, resolution.found_item_id)
    if not found_item:
        raise HTTPException(status_code=404, detail="Found item not found")

    # Ensure user is the finder of the item
    if found_item.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to reject this resolution")

    # Update resolution status
    resolution.status = "rejected"
    resolution.rejection_reason = payload.rejection_reason
    resolution.decided_at = datetime.now(timezone.utc)
    
    session.add(resolution)
    session.commit()
    session.refresh(resolution)

    # Notify claimant
    notification = Notification(
        user_id=resolution.claimant_id,
        type="claim_rejected",
        title="Your claim has been rejected",
        message=f"Your claim for the item '{found_item.title}' has been rejected by the finder. Reason: {payload.rejection_reason}",
        item_id=found_item.id,
        resolution_id=resolution.id,
    )

    session.add(notification)
    session.commit()

    return { "ok": True }

@router.get("/{resolution_id}")
def get_resolution_status(
    resolution_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    """
    Get resolution by ID - accessible only by claimant.
    """
    user = get_db_user(session, current_user)

    # Fetch resolution
    stmt = (
        select(Resolution, Item)
        .join(Item, Resolution.found_item_id == Item.id)
        .where(Resolution.id == resolution_id)
    )

    result = session.exec(stmt).first()
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    resolution, found_item = result

    if resolution.claimant_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this resolution")
    
    item_data = found_item.model_dump(exclude={"type", "created_at", "visibility", "user_id"})
    item_data["image"] = generate_signed_url(item_data["image"])
    
    if not resolution:
        raise HTTPException(status_code=404, detail="Resolution not found")

    # Ensure user is the claimant
    if resolution.claimant_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this resolution")
    
    if resolution.status == "approved":
        finder = session.get(User, found_item.user_id)

        finder_contact = {
            "name": finder.name,
            "email": finder.email,
        }

        return {
            "resolution": resolution,
            "item": item_data,
            "finder_contact": finder_contact,
        }

    return { 
        "resolution": resolution,
        "item": item_data
    }

@router.get("/item/{item_id}")
def get_resolution_for_review(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    """
    Review resolution - accessible by finder.
    """
    user = get_db_user(session, current_user)

    # Fetch resolution and join with found item
    query = (
        select(Resolution, Item)
        .join(Item, Resolution.found_item_id == Item.id)
        .where(Resolution.found_item_id == item_id)
        .where(Resolution.status == "pending")
    )

    result = session.exec(query).first()
    if not result:
        raise HTTPException(status_code=404, detail="No claim found for this item")
    
    resolution, found_item = result

    if found_item.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to review this claim")

    item_data = found_item.model_dump(exclude={"type", "created_at", "visibility", "user_id", "category"})

    if found_item.image:
        item_data["image"] = generate_signed_url(found_item.image)

    return {
        "item": item_data,
        "resolution": resolution,
    }

@router.post("/{resolution_id}/approve")
def approve_resolution(
    resolution_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    user = get_db_user(session, current_user)

    # Fetch resolution
    resolution = session.get(Resolution, resolution_id)
    if not resolution:
        raise HTTPException(status_code=404, detail="Resolution not found")

    # Fetch found item
    found_item = session.get(Item, resolution.found_item_id)
    if not found_item:
        raise HTTPException(status_code=404, detail="Found item not found")

    # Ensure user is the finder of the item
    if found_item.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to approve this resolution")

    # Update resolution status
    resolution.status = "approved"
    resolution.decided_at = datetime.now(timezone.utc)
    
    session.add(resolution)
    session.commit()
    session.refresh(resolution)

    # Notify claimant
    notification = Notification(
        user_id=resolution.claimant_id,
        type="claim_approved",
        title="Your claim has been approved",
        message=f"Your claim for the item '{found_item.title}' has been approved by the finder.",
        item_id=found_item.id,
        resolution_id=resolution.id,
    )

    session.add(notification)
    session.commit()

    return { "ok": True }