"""
Module Settings — ModuleSettings model.

A-4: Stores per-company, per-module configuration. Values are stored as strings
(use JSON encoding for complex types). The application reads the company override
first and falls back to the application default defined in code.

Example keys per module:
  projects:   display_name, id_prefix, default_view
  portfolios: display_name, code_prefix

Access: company admins can write; all authenticated users in the company can read.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


class ModuleSettings(SQLModel, table=True):
    __tablename__ = "module_settings"
    __table_args__ = (
        # One value per key per module per company.
        UniqueConstraint("company_id", "module_key", "key", name="_module_settings_uc"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    module_key: str = Field(index=True)  # e.g. "projects", "portfolios", "contracts"
    key: str                              # e.g. "display_name", "id_prefix"
    value: str                            # stored as plain string or JSON-encoded

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
