from typing import Optional, Dict, Any
from sqlmodel import Session
from app.models.audit_log import AuditLog

def log_change(
    session: Session,
    company_id: int,
    actor_user_id: int,
    entity_type: str,
    entity_id: str,
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    portfolio_id: Optional[int] = None
) -> AuditLog:
    """
    Logs a change to the audit_log table.
    """
    log = AuditLog(
        company_id=company_id,
        portfolio_id=portfolio_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_json=before,
        after_json=after
    )
    session.add(log)
    return log
