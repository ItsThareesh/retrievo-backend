from typing import Optional
import uuid
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Ownership
    user_id: int = Field(foreign_key="users.id")

    # Notification fields
    type: str = Field(index=True) # values: "claim_created", "claim_approved", "claim_rejected"

    title: str
    message: str
    
    item_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="items.id",
        index=True
    )
    
    is_read: bool = Field(default=False)