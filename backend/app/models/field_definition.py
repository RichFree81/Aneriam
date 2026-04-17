"""
Field Library — FieldDefinition model.

A-1: The field library is the single source of truth for what data fields exist on
records like projects and portfolios. Nobody types a field name directly onto a project;
they always select from the library. This enforces naming consistency.

Library layers (company_id IS NULL = system/module level; NOT NULL = company-owned):
  - NULL:    Application defaults / module library — managed by Aneriam, always available.
  - NOT NULL: Company library — managed by company admins, visible only within their company.

field_type controls how values are stored and rendered:
  text | number | date | dropdown | boolean

For dropdown types, the 'options' column holds a JSON list of allowed string values.
Values are stored as JSON on the record (project.field_values), not as separate rows.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint
import sqlalchemy as sa


class FieldDefinition(SQLModel, table=True):
    __tablename__ = "field_definition"
    __table_args__ = (
        # Prevent two entries in the same layer with the same name for the same module.
        UniqueConstraint("company_id", "module_key", "name", name="_field_def_company_module_name_uc"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # NULL = system/module-level field (available to all companies).
    # NOT NULL = company-owned field (visible only within that company).
    company_id: Optional[int] = Field(default=None, foreign_key="company.id", index=True)

    # Which module this field belongs to (e.g., "projects", "portfolios", "contracts").
    module_key: str = Field(index=True)

    # Internal snake_case identifier — used as the JSON key in field_values.
    name: str

    # Human-readable display label shown in the UI.
    label: str

    # One of: text | number | date | dropdown | boolean
    field_type: str

    # JSON-encoded list of allowed values for dropdown fields, e.g. ["Low", "Medium", "High"].
    # NULL for non-dropdown types.
    options: Optional[str] = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))

    # Whether this field is required by default when assigned to a project.
    # Project admins can override per-project via FieldAssignment.required_override.
    is_required: bool = Field(default=False)

    # Deprecated fields are hidden from new selections but retained if already in use.
    is_deprecated: bool = Field(default=False)

    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
