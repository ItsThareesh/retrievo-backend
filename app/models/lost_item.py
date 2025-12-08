import uuid
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class LostItem(SQLModel, table=True):
    __tablename__ = "lost_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Owner info
    user_id: int = Field(foreign_key="users.id")
    reporter_public_id: str  # For URL Linking
    reporter_name: str

    # Item fields
    title: str
    category: str
    description: str
    location: str
    type: str = Field(default="lost")
    date: datetime
    image: str
    visibility: str = Field(default="public")  # public/boys/girls
