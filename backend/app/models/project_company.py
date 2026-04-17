"""
Cross-company collaboration — ProjectCompany model.

A-2: A project is owned by exactly one company. Other companies can be invited as
participants with a defined role. This table records the invitation and its status.

Rules:
  - Only the owning company's admins can invite other companies.
  - Participating companies can view what the owning company permits based on their role.
  - Only the owning company controls field definitions on the project.
  - status tracks the lifecycle: Pending → Accepted | Declined.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint


class CollaborationStatus:
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    DECLINED = "Declined"


class ProjectCompany(SQLModel, table=True):
    __tablename__ = "project_company"
    __table_args__ = (
        # A company can only have one active collaboration record per project.
        UniqueConstraint("project_id", "company_id", name="_project_company_uc"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)

    # The invited (participating) company — NOT the owning company.
    company_id: int = Field(foreign_key="company.id", index=True)

    # Role of the participating company, e.g. Contractor, Consultant, Subcontractor, Client.
    collaboration_role: str

    # One of: Pending | Accepted | Declined
    status: str = Field(default=CollaborationStatus.PENDING)

    invited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: Optional[datetime] = Field(default=None)

    # Which user from the owning company sent the invitation.
    invited_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
