from typing import Literal, Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, func, select
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.db.db import get_session
from app.models.item import Item
from app.models.resolution import Resolution
from app.models.user import User
from app.utils.auth_helper import get_current_user_optional, get_current_user_required, get_db_user, get_user_hostel
from app.utils.s3_service import compress_image, delete_s3_object, generate_signed_url, get_all_urls, upload_to_s3
from app.models.report import Report
from app.models.notification import Notification
from app.utils.form_validator import validate_create_item_form


router = APIRouter()

MAX_UPLOAD_SIZE_MB = 3
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/create")
async def add_item(
    item_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    visibility: str = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    data = validate_create_item_form(
        item_type=item_type,
        title=title,
        description=description,
        category=category,
        date=date,
        location=location,
        visibility=visibility,
    )

    # read image into memory and upload
    raw_bytes = await image.read()

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"Image exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    buffer, ext = compress_image(raw_bytes)
    s3_key = upload_to_s3(buffer, ext, image.filename)

    # user lookup
    user = get_db_user(session, current_user)

    # create DB item
    db_item = Item(
        user_id=user.id,
        title=data.title,
        description=data.description,
        category=data.category,
        date=data.date,
        location=data.location,
        type=data.item_type,
        visibility=data.visibility,
        image=s3_key,
    )

    session.add(db_item)
    session.commit()
    session.refresh(db_item)

    return db_item.id


@router.get("/all")
async def get_all_items(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = get_user_hostel(session, current_user)

    # Query all items
    query = select(Item).where(Item.is_hidden == False).order_by(Item.created_at.desc())

    # apply visibility filters based on user's hostel
    if hostel:
        query = query.where((Item.visibility == hostel) | (Item.visibility == 'public'))
    else:
        query = query.where(Item.visibility == 'public')

    # fetch items
    items = session.exec(query).all()

    items_response = get_all_urls(items)

    return {
        "items": items_response,
    }


@router.get("/{item_id}")
async def get_item(
    item_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = get_user_hostel(session, current_user)

    query = (
        select(Item, User)
        .join(User, User.id == Item.user_id)
        .where(Item.id == item_id)
        .where(Item.is_hidden == False)
    )

    result = session.exec(query).first()
    if not result:
        raise HTTPException(404, "Item not found")

    item, user = result

    # check visibility rules
    if item.visibility != "public" and item.visibility != hostel:
        raise HTTPException(403, "Unauthorized to view this item")

    # check for existing claim
    claim_status = "none"

    claim = session.exec(
        select(Resolution)
        .where(Resolution.found_item_id == item.id)
        .where((Resolution.status == "pending") | (Resolution.status == "approved")) # don't send rejection info
    ).first()

    if claim:
        claim_status = claim.status

    item_dict = item.model_dump()
    item_dict["image"] = generate_signed_url(item.image)

    return {
        "item": item_dict,
        "reporter": {
            "public_id": user.public_id,
            "name": user.name,
            "image": user.image,
        },
        "claim_status": claim_status,
    }

class ItemUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=30)
    location: Optional[str] = Field(None, min_length=3, max_length=30)
    description: Optional[str] = Field(None, min_length=20, max_length=280)
    category: Optional[Literal["electronics", "clothing", "bags", "keys-wallets", "documents", "others"]] = None
    visibility: Optional[Literal["public", "boys", "girls"]] = None
    date: Optional[datetime] = None

    @field_validator("title", "location", "description", "category", "visibility", mode="before")
    @classmethod
    def strip_and_validate_strings(cls, v):
        if v is None:
            return v

        if not isinstance(v, str):
            raise ValueError("Must be a string")

        v = v.strip()

        if v == "":
            raise ValueError("Field cannot be empty")

        return v


@router.patch("/{item_id}")
async def update_item(
    item_id: uuid.UUID,
    updates: ItemUpdateSchema,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    item = session.exec(
        select(Item)
        .where(Item.id == item_id)
        .where(Item.is_hidden == False)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # get resolution status
    # if item is claimed and resolution is pending/approved, block updates
    resolution = session.exec(
        select(Resolution)
        .where(
            (Resolution.found_item_id == item.id) &
            ((Resolution.status == "pending") | (Resolution.status == "approved"))
        )
    ).first()

    if resolution:
        raise HTTPException(
            status_code=400,
            detail="Cannot update item while it has a pending or approved claim",
        )

    user = get_db_user(session, current_user)
    if not user or item.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    update_data = updates.model_dump(exclude_unset=True) # only get provided fields (skip None fields)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update",
        )

    for field, value in update_data.items():
        setattr(item, field, value)

    session.add(item)
    session.commit()
    session.refresh(item)

    return {"id": item.id}

@router.delete("/{item_id}")
async def delete_item(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    item = session.exec(
        select(Item)
        .where(Item.id == item_id)
        .where(Item.is_hidden is False)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # ownership check
    user = get_db_user(session, current_user)

    if not user or item.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete this item",
        )
    
    delete_s3_object(item.image)

    session.delete(item)
    session.commit()

    return {
    "ok": True
}

class ReportCreateSchema(BaseModel):
    reason: Literal['spam', 'inappropriate', 'harassment', 'fake', 'other']

@router.post("/{id}/report")
async def report_item(
    id: uuid.UUID,
    payload: ReportCreateSchema,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):  
    item = session.exec(
        select(Item).where(Item.id == id)
    ).first()

    if not item or item.is_hidden: # hidden items cannot be reported
        raise HTTPException(status_code=404, detail="Item not found")

    # Only logged in users can report
    user = get_db_user(session, current_user)
    
    if not user:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # prevent self-reporting
    if item.user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot report your own item")

    # Create report
    report = Report(
        user_id=user.id,
        item_id=item.id,
        reason=payload.reason,
    )

    session.add(report)

    try:
        session.commit()
        session.refresh(report)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="You have already reported this item")

    # Moderation Logic

    report_count = session.exec(
        select(func.count(Report.id))
        .where(Report.item_id == item.id)
    ).first()

    session.refresh(item) # refresh to get latest state

    if report_count >= 5:
        item.is_hidden = True
        item.hidden_reason = "auto_report_threshold"

        # Notify owner about hiding
        notification = Notification(
            user_id=item.user_id,
            type="system_notice",
            title="Your item has been hidden",
            message=f"Your item '{item.title}' has been hidden due to multiple reports from users.",
            item_id=item.id,
        )

        session.add(item)
        session.add(notification)
        session.commit()

        # TODO: Increment warning count for user and ban if necessary

    return { "ok": True }
