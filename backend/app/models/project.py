from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
import sqlalchemy as sa

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolio.id", index=True)
    # M-2: company_id denormalised for efficient tenant-scoped queries without a portfolio JOIN.
    # Must always equal portfolio.company_id; enforced at write time.
    company_id: Optional[int] = Field(default=None, foreign_key="company.id", index=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # A-1: Field values stored as JSON keyed by FieldDefinition.name.
    # e.g. {"priority": "High", "budget_code": "CAPEX-001"}
    field_values: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    # A-3: Soft delete — records are never permanently deleted; deleted_at is set instead.
    deleted_at: Optional[datetime] = Field(default=None)
