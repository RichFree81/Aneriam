from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from app.models.enums import WorkflowStatus

class WorkflowMixin(SQLModel):
    """
    Mixin to add workflow status and locking fields.
    """
    status: WorkflowStatus = Field(default=WorkflowStatus.DRAFT, index=True)
    locked_at: Optional[datetime] = Field(default=None)
    locked_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True)
