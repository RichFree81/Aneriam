from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint

class Portfolio(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    name: str
    code: str = Field(index=True)  # unique per company handled by logic or composite index? User said "unique per company if feasible".
    description: Optional[str] = None
    logo: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Follows the Project model convention: default_factory sets the initial value; route
    # handlers must set updated_at = datetime.now(timezone.utc) on every write path.
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # A-3: Soft delete — records are never permanently deleted; deleted_at is set instead.
    deleted_at: Optional[datetime] = Field(default=None)

    __table_args__ = (UniqueConstraint("company_id", "code", name="_company_portfolio_code_uc"),)
