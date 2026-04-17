"""
Cross-Company Collaboration API — C-9.

Endpoints to manage the project_company table: invite a company into a project,
accept or decline the invitation, and remove a collaborator.

See docs/specs/cross-company-collaboration.md for full specification.

Access rules:
  - Owning company admin: invite and remove companies.
  - Invited company admin: accept or decline the invitation.
  - Participants with Accepted status can view the collaboration record.
"""
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_request_context, get_valid_portfolio, require_company_admin
from app.core.database import get_session
from app.models import Company
from app.models.project import Project
from app.models.project_company import CollaborationStatus, ProjectCompany
from app.schemas import CollaboratorInvite, CollaboratorStatusUpdate, RequestContext

router = APIRouter()


class ProjectCompanyRead(BaseModel):
    id: int
    project_id: int
    company_id: int
    company_name: Optional[str]
    collaboration_role: str
    status: str
    invited_at: datetime
    accepted_at: Optional[datetime]

    class Config:
        from_attributes = True


def _get_project_scoped(project_id: int, portfolio_id: int, session: Session) -> Project:
    project = session.get(Project, project_id)
    if not project or project.portfolio_id != portfolio_id or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_read(pc: ProjectCompany, session: Session) -> ProjectCompanyRead:
    company = session.get(Company, pc.company_id)
    return ProjectCompanyRead(
        id=pc.id,
        project_id=pc.project_id,
        company_id=pc.company_id,
        company_name=company.name if company else None,
        collaboration_role=pc.collaboration_role,
        status=pc.status,
        invited_at=pc.invited_at,
        accepted_at=pc.accepted_at,
    )


@router.get(
    "/portfolios/{portfolio_id}/projects/{project_id}/collaborators",
    response_model=List[ProjectCompanyRead],
)
def list_collaborators(
    portfolio_id: int,
    project_id: int,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """List all collaboration records for a project."""
    project = _get_project_scoped(project_id, portfolio_id, session)

    records = session.exec(
        select(ProjectCompany).where(ProjectCompany.project_id == project.id)
    ).all()

    return [_to_read(r, session) for r in records]


@router.post(
    "/portfolios/{portfolio_id}/projects/{project_id}/collaborators",
    response_model=ProjectCompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def invite_collaborator(
    portfolio_id: int,
    project_id: int,
    body: CollaboratorInvite,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Invite another company to collaborate on this project.
    Only the owning company's admin can issue invitations.
    """
    project = _get_project_scoped(project_id, portfolio_id, session)

    # Ensure the invited company exists
    invited_company = session.get(Company, body.company_id)
    if not invited_company or not invited_company.is_active:
        raise HTTPException(status_code=404, detail="Company not found")

    # Cannot invite your own company
    if body.company_id == context.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite your own company",
        )

    # Check for existing record
    existing = session.exec(
        select(ProjectCompany).where(
            ProjectCompany.project_id == project.id,
            ProjectCompany.company_id == body.company_id,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This company has already been invited to this project",
        )

    record = ProjectCompany(
        project_id=project.id,
        company_id=body.company_id,
        collaboration_role=body.collaboration_role,
        status=CollaborationStatus.PENDING,
        invited_at=datetime.now(timezone.utc),
        invited_by_user_id=context.user.id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_read(record, session)


@router.patch(
    "/portfolios/{portfolio_id}/projects/{project_id}/collaborators/{record_id}",
    response_model=ProjectCompanyRead,
)
def update_collaborator_status(
    portfolio_id: int,
    project_id: int,
    record_id: int,
    body: CollaboratorStatusUpdate,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Accept or decline a collaboration invitation.
    The invited company's admin sets the status to Accepted or Declined.
    """
    project = _get_project_scoped(project_id, portfolio_id, session)

    record = session.get(ProjectCompany, record_id)
    if not record or record.project_id != project.id:
        raise HTTPException(status_code=404, detail="Collaboration record not found")

    if body.status not in (CollaborationStatus.ACCEPTED, CollaborationStatus.DECLINED):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be Accepted or Declined",
        )

    # Only the invited company can accept/decline
    if record.company_id != context.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the invited company can accept or decline",
        )

    record.status = body.status
    if body.status == CollaborationStatus.ACCEPTED:
        record.accepted_at = datetime.now(timezone.utc)

    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_read(record, session)


@router.delete(
    "/portfolios/{portfolio_id}/projects/{project_id}/collaborators/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_collaborator(
    portfolio_id: int,
    project_id: int,
    record_id: int,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Remove a collaboration record from a project.
    Only the owning company's admin can remove collaborators.
    """
    project = _get_project_scoped(project_id, portfolio_id, session)

    record = session.get(ProjectCompany, record_id)
    if not record or record.project_id != project.id:
        raise HTTPException(status_code=404, detail="Collaboration record not found")

    # Verify the caller is from the owning company
    if portfolio.company_id != context.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owning company can remove collaborators",
        )

    session.delete(record)
    session.commit()
