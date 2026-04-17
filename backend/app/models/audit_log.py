from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(index=True)
    portfolio_id: Optional[int] = Field(default=None, index=True)
    actor_user_id: int = Field(index=True)
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    action: str = Field() # CREATE, UPDATE, DELETE, STATUS_CHANGE
    before_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    after_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
