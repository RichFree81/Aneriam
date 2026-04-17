"""
Audit Log Query API — C-10.

Read-only endpoints to retrieve audit log entries.
Logs are append-only (per A-3); no write endpoints exist here.

Filters:
  - entity_type: filter by record type (e.g. "project", "financial_note")
  - entity_id: filter by specific record ID
  - actor_user_id: filter by who performed the action
  - from_date / to_date: date range filter
  - limit / offset: pagination

Access: company admins see all entries for their company. Regular users see only
entries they created (actor_user_id = current_user.id). System admins see all.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_request_context
from app.core.database import get_session
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.schemas import RequestContext

router = APIRouter()


class AuditLogRead(BaseModel):
    id: int
    company_id: int
    portfolio_id: Optional[int]
    actor_user_id: int
    entity_type: str
    entity_id: str
    action: str
    before_json: Optional[Dict[str, Any]]
    after_json: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[AuditLogRead])
def list_audit_logs(
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type, e.g. 'project'"),
    entity_id: Optional[str] = Query(default=None, description="Filter by entity ID"),
    actor_user_id: Optional[int] = Query(default=None, description="Filter by user who performed the action"),
    from_date: Optional[datetime] = Query(default=None, description="Earliest created_at (inclusive)"),
    to_date: Optional[datetime] = Query(default=None, description="Latest created_at (inclusive)"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Query the audit log. Audit entries are read-only and append-only (A-3).
    Results are scoped to the current user's company.
    """
    stmt = select(AuditLog).where(AuditLog.company_id == context.company_id)

    # Non-admin users can only see their own actions
    if context.user.role not in (UserRole.ADMIN, UserRole.COMPANY_ADMIN):
        stmt = stmt.where(AuditLog.actor_user_id == context.user.id)
    elif actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)

    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if from_date is not None:
        stmt = stmt.where(AuditLog.created_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(AuditLog.created_at <= to_date)

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)

    entries = session.exec(stmt).all()
    return entries
