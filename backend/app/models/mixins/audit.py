from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel

class AuditMixin(SQLModel):
    """
    Mixin to add audit columns to a model.
    """
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True)
    updated_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True)
