from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
from typing import Optional


class LostItem(SQLModel, table=True):
    __tablename__ = "lost_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str

    title: str
    category: str
    description: str
    location_lost: str
    type: str = Field(default="lost")

    date_lost: datetime
