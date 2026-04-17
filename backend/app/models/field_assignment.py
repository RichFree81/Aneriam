"""
Field Library — FieldAssignment model.

A-1: A FieldAssignment records that a specific FieldDefinition has been assigned
to a specific project. Project admins pick from the module + company library;
this table captures which fields are active on a project and any per-project overrides.

Field values themselves are stored as JSON in project.field_values (keyed by
field_definition.name) — not as separate database rows.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


class FieldAssignment(SQLModel, table=True):
    __tablename__ = "field_assignment"
    __table_args__ = (
        # A field definition can only be assigned once per project.
        UniqueConstraint("project_id", "field_definition_id", name="_field_assign_project_field_uc"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    field_definition_id: int = Field(foreign_key="field_definition.id", index=True)

    # Per-project override for the field's required flag.
    # NULL = inherit from field_definition.is_required.
    required_override: Optional[bool] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
