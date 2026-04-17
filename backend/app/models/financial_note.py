from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel
import sqlalchemy as sa
from app.core.money import Money
from app.models.mixins.audit import AuditMixin
from app.models.mixins.workflow import WorkflowMixin
from app.models.enums import WorkflowStatus

class FinancialNote(AuditMixin, WorkflowMixin, SQLModel, table=True):
    __tablename__ = "financial_note"
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    amount: Money
    company_id: int = Field(foreign_key="company.id", index=True)
    portfolio_id: int = Field(foreign_key="portfolio.id")
    # M-3: explicit FK to the project this note belongs to.
    # Nullable to allow portfolio-level notes not tied to a specific project.
    project_id: Optional[int] = Field(default=None, foreign_key="project.id", index=True)
    # Override status from mixin to enforce Enum usage in DB
    status: WorkflowStatus = Field(
        default=WorkflowStatus.DRAFT,
        sa_column=sa.Column(
            sa.Enum(WorkflowStatus, name="workflowstatus", values_callable=lambda x: [e.value for e in x]),
            nullable=False,
            default=WorkflowStatus.DRAFT.value
        )
    )
    # A-3: Soft delete — records are never permanently deleted; deleted_at is set instead.
    deleted_at: Optional[datetime] = Field(default=None)
