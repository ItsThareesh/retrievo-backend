from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    public_id: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    name: str
    image: str
    email: str

    role: str = Field(default="user")  # Possible roles: user, admin
    hostel: Optional[str] = Field(default=None)  # Possible values: boys, girls
