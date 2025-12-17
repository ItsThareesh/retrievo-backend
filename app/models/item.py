import uuid
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class Item(SQLModel, table=True):
    __tablename__ = "items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Reporter info
    user_id: int = Field(foreign_key="users.id")

    # Item fields
    title: str
    category: str
    description: str
    location: str
    type: str  # "lost" or "found"
    date: datetime
    image: str
    visibility: str = Field(default="public")  # public/boys/girls
