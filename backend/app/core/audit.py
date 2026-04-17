from datetime import datetime, timezone
from typing import Any

def apply_audit_create(obj: Any, user_id: int):
    """
    Sets creation audit fields.
    """
    if hasattr(obj, "created_by_user_id"):
        obj.created_by_user_id = user_id
    if hasattr(obj, "created_at"):
        obj.created_at = datetime.now(timezone.utc)
    
    # Also set updated fields on create
    apply_audit_update(obj, user_id)

def apply_audit_update(obj: Any, user_id: int):
    """
    Sets update audit fields.
    """
    if hasattr(obj, "updated_by_user_id"):
        obj.updated_by_user_id = user_id
    if hasattr(obj, "updated_at"):
        obj.updated_at = datetime.now(timezone.utc)
