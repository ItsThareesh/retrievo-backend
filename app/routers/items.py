import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select
from datetime import datetime

from app.db.db import get_session
from app.models.item import Item
from app.models.resolution import Resolution
from app.models.user import User
from app.utils.auth_helper import get_current_user_optional, get_current_user_required, get_db_user, get_user_hostel
from app.utils.s3_service import compress_image, delete_s3_object, generate_signed_url, get_all_urls, upload_to_s3


router = APIRouter()

MAX_UPLOAD_SIZE_MB = 5
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
    # user lookup
    user = get_db_user(session, current_user)

    # parse date
    try:
        parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except:
        raise HTTPException(400, "Date not parseable")

    # read image into memory and upload
    raw_bytes = await image.read()

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"Image exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    buffer, ext = compress_image(raw_bytes)
    s3_key = upload_to_s3(buffer, ext, image.filename)

    # check for valid types
    if item_type not in ["lost", "found"]:
        raise HTTPException(400, "Invalid item type")
    
    if visibility not in ["public", "boys", "girls"]:
        raise HTTPException(400, "Invalid visibility option")

    if category not in [ "electronics", "clothing", "bags", "keys-wallets", "documents", "others"]:
        raise HTTPException(400, "Invalid category option")

    # clean strings
    title = title.strip()
    description = description.strip()
    location = location.strip()

    # create DB item
    db_item = Item(
        user_id=user.id,
        title=title,
        description=description,
        category=category,
        date=parsed_date,
        location=location,
        type=item_type,
        visibility=visibility,
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
    query = select(Item).order_by(Item.created_at.desc())

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


@router.patch("/{item_id}")
async def update_item(
    item_id: str,
    updates: dict,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    item = session.exec(
        select(Item).where(Item.id == item_id)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # ownership check
    user = get_db_user(session, current_user)
    
    if not user or item.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to edit this item",
        )

    ALLOWED_FIELDS = {
        "title",
        "location",
        "description",
        "category",
        "visibility",
        "date",
    }

    for field, value in updates.items():
        if field not in ALLOWED_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Field '{field}' cannot be updated",
            )

        if field == "date":
            try:
                value = datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Date not parseable",
                )
        else:
            value = value.strip()

        setattr(item, field, value)

    session.add(item)
    session.commit()
    session.refresh(item)

    return item.id

@router.delete("/{item_id}")
async def delete_item(
    item_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_required),
):
    item = session.exec(
        select(Item).where(Item.id == item_id)
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

    return True
