from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select
from datetime import datetime

from app.db.db import get_session
from app.models.found_item import FoundItem
from app.models.lost_item import LostItem
from app.models.user import User
from app.utils.auth_helper import get_current_user_optional, get_user_hostel
from app.utils.s3_service import compress_image, generate_signed_url, get_all_urls, upload_to_s3


router = APIRouter()

MAX_UPLOAD_SIZE_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/")
async def add_item(
    item_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # user lookup
    user = session.exec(
        select(User).where(User.public_id == current_user["public_id"])
    ).first()

    if not user:
        raise HTTPException(404, "Reporter not found")

    # parse date
    try:
        parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except:
        raise HTTPException(400, "Date not parseable")

    # read image into memory and upload
    raw_bytes = await image.read()

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"Image exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    buffer, ext, mime = compress_image(raw_bytes)
    s3_key = upload_to_s3(buffer, ext, mime, image.filename)

    # check for valid types
    if item_type not in ["lost", "found"]:
        raise HTTPException(400, "Invalid item type")

    model_type = LostItem if item_type == "lost" else FoundItem

    # clean strings
    title = title.strip()
    description = description.strip()
    category = category.strip()
    location = location.strip()

    # create DB item
    db_item = model_type(
        user_id=user.id,
        reporter_public_id=user.public_id,
        reporter_name=user.name,
        title=title,
        description=description,
        category=category,
        date=parsed_date,
        location=location,
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
    hostel = get_user_hostel(current_user, session)

    lost_query = select(LostItem).order_by(LostItem.created_at.desc())
    found_query = select(FoundItem).order_by(FoundItem.created_at.desc())

    # apply visibility filters based on user's hostel
    if hostel:
        lost_query = lost_query.where((LostItem.visibility == hostel) | (LostItem.visibility == 'public'))
        found_query = found_query.where((FoundItem.visibility == hostel) | (FoundItem.visibility == 'public'))

    # fetch items
    lost_items = session.exec(lost_query).all()
    found_items = session.exec(found_query).all()

    # get urls
    lost_items_response = get_all_urls(lost_items)
    found_items_response = get_all_urls(found_items)

    return {
        "lost_items": lost_items_response,
        "found_items": found_items_response,
    }


@router.get("/{item_id}/{item_type}")
async def get_item(
    item_id: str,
    item_type: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user_optional),
):
    # Get user's hostel if logged in
    hostel = get_user_hostel(current_user, session)

    # check for valid types
    if item_type not in ["lost", "found"]:
        raise HTTPException(400, "Invalid item type")

    # decide type based on item_type
    Type = LostItem if item_type == "lost" else FoundItem

    query = (
        select(Type, User)
        .join(User, User.id == Type.user_id)
        .where(Type.id == item_id)
    )

    result = session.exec(query).first()
    if not result:
        raise HTTPException(404, f"{item_type.capitalize()} item not found")

    item, user = result

    # check visibility rules
    if item.visibility != "public" and item.visibility != hostel:
        raise HTTPException(403, f"Unauthorized to view this {item_type} item")

    item_dict = item.model_dump()
    item_dict["image"] = generate_signed_url(item.image)

    return {
        "item": item_dict,
        "reporter": {
            "image": user.image,
        }
    }
