from datetime import datetime, timezone
from typing import Any, Set
from fastapi import HTTPException
from app.models.enums import WorkflowStatus

MUTABLE_STATUSES = {WorkflowStatus.DRAFT, WorkflowStatus.SUBMITTED}

def assert_mutable(entity: Any):
    """
    Raises HTTPException if entity is not in a mutable state.
    """
    if entity.status not in MUTABLE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Entity is {entity.status.value} and cannot be modified.")

def set_status(entity: Any, status: WorkflowStatus, user_id: int):
    """
    Updates status and handles locking logic.
    """
    entity.status = status
    if status == WorkflowStatus.LOCKED:
        entity.locked_at = datetime.now(timezone.utc)
        entity.locked_by_user_id = user_id
    elif status == WorkflowStatus.DRAFT:
        # Reset locks if moving back to draft (e.g. from Submitted/Rejected)
        entity.locked_at = None
        entity.locked_by_user_id = None
