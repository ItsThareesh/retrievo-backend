from typing import Optional
import uuid
from sqlmodel import Field, SQLModel, UniqueConstraint
from datetime import datetime, timezone


class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Reporter info
    user_id: int = Field(foreign_key="users.id")

    item_id: uuid.UUID = Field(foreign_key="items.id", index=True, ondelete="CASCADE")

    # Report fields
    reason: str
    
    # Status
    status: str = Field(default="pending", index=True)  # "pending", "reviewed", "dismissed"
    reviewed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    reviewed_at: Optional[datetime] = Field(default=None)

    __table_args__ = (
        # Ensure a user can report the same item only once
        # This constraint prevents duplicate reports from the same user on the same item
        UniqueConstraint(
            "user_id",
            "item_id",
            name="uq_user_item_report"    
        ),
    )
