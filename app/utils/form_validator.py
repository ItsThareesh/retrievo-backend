from datetime import datetime
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError


class ValidatedCreateItem(BaseModel):
    item_type: Literal["lost", "found"]
    title: str = Field(min_length=3, max_length=30)
    description: str = Field(min_length=20, max_length=280)
    category: Literal[
        "electronics",
        "clothing",
        "bags",
        "keys-wallets",
        "documents",
        "others",
    ]
    date: datetime
    location: str = Field(min_length=3, max_length=30)
    visibility: Literal["public", "boys", "girls"]

def validate_create_item_form(
    item_type: str,
    title: str,
    description: str,
    category: str,
    date: str,
    location: str,
    visibility: str,
) -> ValidatedCreateItem:
    try:
        parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Date not parseable")

    try:
        return ValidatedCreateItem(
            item_type=item_type,
            title=title.strip(),
            description=description.strip(),
            category=category,
            date=parsed_date,
            location=location.strip(),
            visibility=visibility,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=e.errors(),
        )