from typing import Optional
import uuid
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

class Resolution(SQLModel, table=True):
    __tablename__ = "resolutions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Claimant
    claimant_id: int = Field(foreign_key="users.id", index=True) # for sending notifications

    # Linked reports
    found_item_id: uuid.UUID = Field(foreign_key="items.id", index=True)

    status: str = Field(default="pending", index=True) # values: "pending", "approved", "rejected"

    # Content
    claim_description: str
    rejection_reason: Optional[str] = None

    decided_at: Optional[datetime] = None
