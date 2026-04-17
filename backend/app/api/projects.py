from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_request_context, get_valid_portfolio, require_company_admin
from app.core.database import get_session
from app.models.portfolio import Portfolio
from app.models.project import Project
from app.schemas import ProjectCreate, ProjectUpdate, RequestContext

router = APIRouter()

@router.get("/portfolios/{portfolio_id}/projects", response_model=List[Project])
def read_projects(
    portfolio_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
):
    """
    Retrieve projects for a specific portfolio.
    Access is gated via get_valid_portfolio which enforces company-scoped isolation.
    """
    # A-3: Always filter soft-deleted records from list views.
    statement = select(Project).where(
        Project.portfolio_id == portfolio_id,
        Project.deleted_at.is_(None),
    )
    projects = session.exec(statement).all()
    return projects

@router.post("/portfolios/{portfolio_id}/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    portfolio_id: int,
    project_in: ProjectCreate,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Create a new project in a portfolio.
    Access is gated via get_valid_portfolio which enforces company-scoped isolation.
    """
    project = Project(
        portfolio_id=portfolio_id,
        company_id=portfolio.company_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        **project_in.model_dump(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def _get_project(project_id: int, portfolio_id: int, session: Session) -> Project:
    """Fetch a non-deleted project scoped to a portfolio, or raise 404."""
    project = session.get(Project, project_id)
    if not project or project.portfolio_id != portfolio_id or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/portfolios/{portfolio_id}/projects/{project_id}", response_model=Project)
def update_project(
    portfolio_id: int,
    project_id: int,
    body: ProjectUpdate,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Update a project's name, description, or active status.
    """
    project = _get_project(project_id, portfolio_id, session)

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.is_active is not None:
        project.is_active = body.is_active

    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.delete("/portfolios/{portfolio_id}/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    portfolio_id: int,
    project_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Soft-delete a project (sets deleted_at). A-3: records are never permanently deleted.
    Company admin only.
    """
    project = _get_project(project_id, portfolio_id, session)
    project.deleted_at = datetime.now(timezone.utc)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
