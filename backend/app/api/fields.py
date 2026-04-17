"""
Field Library API — C-2.

Endpoints for managing field definitions and their assignment to projects.
See docs/specs/field-library.md for full specification.

Access rules:
  - Any authenticated user in the company can read field definitions.
  - Company admins can create/update company-owned field definitions.
  - System admins can manage system/module-level definitions (company_id = NULL).
  - Project admins (any company admin) can manage field assignments on their projects.
"""
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.api.deps import get_request_context, get_valid_portfolio, require_company_admin
from app.core.database import get_session
from app.models.field_assignment import FieldAssignment
from app.models.field_definition import FieldDefinition
from app.models.project import Project
from app.schemas import RequestContext

router = APIRouter()

VALID_FIELD_TYPES = {"text", "number", "date", "dropdown", "boolean"}


# ── Pydantic schemas (local to this module) ──────────────────────────────────

class FieldDefinitionCreate(BaseModel):
    module_key: str
    name: str = PydanticField(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = PydanticField(min_length=1, max_length=255)
    field_type: str
    options: Optional[List[str]] = None
    is_required: bool = False
    sort_order: int = 0


class FieldDefinitionUpdate(BaseModel):
    label: Optional[str] = PydanticField(default=None, min_length=1, max_length=255)
    options: Optional[List[str]] = None
    is_required: Optional[bool] = None
    is_deprecated: Optional[bool] = None
    sort_order: Optional[int] = None


class FieldDefinitionRead(BaseModel):
    id: int
    company_id: Optional[int]
    module_key: str
    name: str
    label: str
    field_type: str
    options: Optional[List[str]]
    is_required: bool
    is_deprecated: bool
    sort_order: int

    class Config:
        from_attributes = True


class FieldAssignmentCreate(BaseModel):
    field_definition_id: int
    required_override: Optional[bool] = None


class FieldAssignmentRead(BaseModel):
    id: int
    project_id: int
    field_definition_id: int
    required_override: Optional[bool]
    field_name: str
    field_label: str
    field_type: str

    class Config:
        from_attributes = True


class FieldValuesUpdate(BaseModel):
    field_values: dict  # keyed by field_definition.name


# ── Helpers ──────────────────────────────────────────────────────────────────

def _field_def_to_read(fd: FieldDefinition) -> FieldDefinitionRead:
    parsed_options = None
    if fd.options:
        try:
            parsed_options = json.loads(fd.options)
        except (json.JSONDecodeError, TypeError):
            parsed_options = []
    return FieldDefinitionRead(
        id=fd.id,
        company_id=fd.company_id,
        module_key=fd.module_key,
        name=fd.name,
        label=fd.label,
        field_type=fd.field_type,
        options=parsed_options,
        is_required=fd.is_required,
        is_deprecated=fd.is_deprecated,
        sort_order=fd.sort_order,
    )


def _get_project_scoped(project_id: int, portfolio_id: int, session: Session) -> Project:
    project = session.get(Project, project_id)
    if not project or project.portfolio_id != portfolio_id or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Field Definition endpoints ────────────────────────────────────────────────

@router.get("/field-definitions", response_model=List[FieldDefinitionRead])
def list_field_definitions(
    module_key: str,
    include_deprecated: bool = False,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    List available field definitions for the current company.
    Returns system/module-level fields plus company-owned fields.
    Deprecated fields are excluded by default.
    """
    stmt = select(FieldDefinition).where(
        FieldDefinition.module_key == module_key,
        FieldDefinition.company_id.in_([None, context.company_id]),
    )
    if not include_deprecated:
        stmt = stmt.where(FieldDefinition.is_deprecated == False)

    definitions = session.exec(stmt).all()
    return [_field_def_to_read(fd) for fd in definitions]


@router.post("/field-definitions", response_model=FieldDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_field_definition(
    body: FieldDefinitionCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Create a company-owned field definition.
    Company admin only. System admins can create system-level fields via this endpoint too
    (company_id will be set to the caller's company; use admin tools for system-level).
    """
    if body.field_type not in VALID_FIELD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"field_type must be one of: {', '.join(VALID_FIELD_TYPES)}",
        )
    if body.field_type == "dropdown" and not body.options:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dropdown fields must have at least one option",
        )

    options_json = json.dumps(body.options) if body.options else None

    fd = FieldDefinition(
        company_id=context.company_id,
        module_key=body.module_key,
        name=body.name,
        label=body.label,
        field_type=body.field_type,
        options=options_json,
        is_required=body.is_required,
        is_deprecated=False,
        sort_order=body.sort_order,
        created_at=datetime.now(timezone.utc),
    )
    session.add(fd)
    session.commit()
    session.refresh(fd)
    return _field_def_to_read(fd)


@router.patch("/field-definitions/{field_id}", response_model=FieldDefinitionRead)
def update_field_definition(
    field_id: int,
    body: FieldDefinitionUpdate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Update a field definition's label, options, sort order, or deprecation status.
    Company admins can only update their own company's definitions.
    The name (internal key) is immutable once set.
    """
    fd = session.get(FieldDefinition, field_id)
    if not fd:
        raise HTTPException(status_code=404, detail="Field definition not found")

    # Company admins cannot modify system-level (NULL company_id) definitions
    if fd.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cannot modify this field definition")

    if body.label is not None:
        fd.label = body.label
    if body.options is not None:
        fd.options = json.dumps(body.options)
    if body.is_required is not None:
        fd.is_required = body.is_required
    if body.is_deprecated is not None:
        fd.is_deprecated = body.is_deprecated
    if body.sort_order is not None:
        fd.sort_order = body.sort_order

    session.add(fd)
    session.commit()
    session.refresh(fd)
    return _field_def_to_read(fd)


# ── Field Assignment endpoints ─────────────────────────────────────────────────

@router.get(
    "/portfolios/{portfolio_id}/projects/{project_id}/field-assignments",
    response_model=List[FieldAssignmentRead],
)
def list_field_assignments(
    portfolio_id: int,
    project_id: int,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """List all field assignments for a project."""
    project = _get_project_scoped(project_id, portfolio_id, session)

    assignments = session.exec(
        select(FieldAssignment).where(FieldAssignment.project_id == project.id)
    ).all()

    result = []
    for a in assignments:
        fd = session.get(FieldDefinition, a.field_definition_id)
        result.append(FieldAssignmentRead(
            id=a.id,
            project_id=a.project_id,
            field_definition_id=a.field_definition_id,
            required_override=a.required_override,
            field_name=fd.name if fd else "",
            field_label=fd.label if fd else "",
            field_type=fd.field_type if fd else "",
        ))
    return result


@router.post(
    "/portfolios/{portfolio_id}/projects/{project_id}/field-assignments",
    response_model=FieldAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_field(
    portfolio_id: int,
    project_id: int,
    body: FieldAssignmentCreate,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """Assign a field definition to a project. Company admin only."""
    project = _get_project_scoped(project_id, portfolio_id, session)

    fd = session.get(FieldDefinition, body.field_definition_id)
    if not fd:
        raise HTTPException(status_code=404, detail="Field definition not found")

    # Verify the field is accessible to this company
    if fd.company_id is not None and fd.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Field definition not accessible")

    assignment = FieldAssignment(
        project_id=project.id,
        field_definition_id=fd.id,
        required_override=body.required_override,
        created_at=datetime.now(timezone.utc),
    )
    session.add(assignment)
    session.commit()
    session.refresh(assignment)

    return FieldAssignmentRead(
        id=assignment.id,
        project_id=assignment.project_id,
        field_definition_id=assignment.field_definition_id,
        required_override=assignment.required_override,
        field_name=fd.name,
        field_label=fd.label,
        field_type=fd.field_type,
    )


@router.delete(
    "/portfolios/{portfolio_id}/projects/{project_id}/field-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_field_assignment(
    portfolio_id: int,
    project_id: int,
    assignment_id: int,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """Remove a field assignment from a project. Company admin only."""
    project = _get_project_scoped(project_id, portfolio_id, session)
    assignment = session.get(FieldAssignment, assignment_id)
    if not assignment or assignment.project_id != project.id:
        raise HTTPException(status_code=404, detail="Field assignment not found")

    session.delete(assignment)
    session.commit()


@router.patch(
    "/portfolios/{portfolio_id}/projects/{project_id}/field-values",
    response_model=Project,
)
def update_field_values(
    portfolio_id: int,
    project_id: int,
    body: FieldValuesUpdate,
    session: Session = Depends(get_session),
    portfolio=Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Update the JSON field values object on a project.
    Keys must correspond to assigned field_definition.name values.
    """
    project = _get_project_scoped(project_id, portfolio_id, session)

    existing = {}
    if project.field_values:
        try:
            existing = json.loads(project.field_values)
        except (json.JSONDecodeError, TypeError):
            existing = {}

    existing.update(body.field_values)
    project.field_values = json.dumps(existing)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
