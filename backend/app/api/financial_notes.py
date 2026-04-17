"""
Financial Note API — C-6.

Full CRUD + workflow transition endpoints for FinancialNote records.
The model exists; this file provides the API surface.

Workflow: DRAFT → SUBMITTED → APPROVED → LOCKED
              ↑_________|          (re-draft from SUBMITTED only)
                                   CANCELLED (from any non-LOCKED state)

Access rules:
  - Any authorised company user can create and edit DRAFT notes in their portfolio.
  - SUBMITTED / APPROVED transitions require company admin.
  - LOCKED notes cannot be modified by anyone.
  - Soft-delete is admin-only.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_request_context, get_valid_portfolio, require_company_admin
from app.core import audit as audit_helper
from app.core import workflow as wf
from app.core.database import get_session
from app.models import User
from app.models.enums import WorkflowStatus
from app.models.financial_note import FinancialNote
from app.models.portfolio import Portfolio
from app.schemas import RequestContext

router = APIRouter()

VALID_TRANSITIONS = {
    WorkflowStatus.DRAFT: {WorkflowStatus.SUBMITTED, WorkflowStatus.CANCELLED},
    WorkflowStatus.SUBMITTED: {WorkflowStatus.APPROVED, WorkflowStatus.DRAFT, WorkflowStatus.CANCELLED},
    WorkflowStatus.APPROVED: {WorkflowStatus.LOCKED, WorkflowStatus.CANCELLED},
    WorkflowStatus.LOCKED: set(),
    WorkflowStatus.CANCELLED: set(),
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class FinancialNoteCreate(BaseModel):
    content: str
    amount: str  # Sent as a decimal string; validated by Money type
    portfolio_id: int
    project_id: Optional[int] = None


class FinancialNoteUpdate(BaseModel):
    content: Optional[str] = None
    amount: Optional[str] = None  # Decimal string


class WorkflowTransition(BaseModel):
    status: WorkflowStatus


class FinancialNoteRead(BaseModel):
    id: int
    content: str
    amount: str
    company_id: int
    portfolio_id: int
    project_id: Optional[int]
    status: WorkflowStatus
    locked_at: Optional[datetime]
    locked_by_user_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    created_by_user_id: Optional[int]
    updated_by_user_id: Optional[int]
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _note_to_read(note: FinancialNote) -> FinancialNoteRead:
    return FinancialNoteRead(
        id=note.id,
        content=note.content,
        amount=str(note.amount),
        company_id=note.company_id,
        portfolio_id=note.portfolio_id,
        project_id=note.project_id,
        status=note.status,
        locked_at=note.locked_at,
        locked_by_user_id=note.locked_by_user_id,
        created_at=note.created_at,
        updated_at=note.updated_at,
        created_by_user_id=note.created_by_user_id,
        updated_by_user_id=note.updated_by_user_id,
        deleted_at=note.deleted_at,
    )


def _get_note(note_id: int, portfolio_id: int, session: Session) -> FinancialNote:
    note = session.get(FinancialNote, note_id)
    if not note or note.portfolio_id != portfolio_id or note.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Financial note not found")
    return note


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/portfolios/{portfolio_id}/financial-notes",
    response_model=List[FinancialNoteRead],
)
def list_financial_notes(
    portfolio_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """List all non-deleted financial notes for a portfolio."""
    notes = session.exec(
        select(FinancialNote).where(
            FinancialNote.portfolio_id == portfolio_id,
            FinancialNote.deleted_at.is_(None),
        )
    ).all()
    return [_note_to_read(n) for n in notes]


@router.post(
    "/portfolios/{portfolio_id}/financial-notes",
    response_model=FinancialNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_financial_note(
    portfolio_id: int,
    body: FinancialNoteCreate,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """Create a financial note in DRAFT status."""
    note = FinancialNote(
        content=body.content,
        amount=Decimal(body.amount),
        company_id=portfolio.company_id,
        portfolio_id=portfolio_id,
        project_id=body.project_id,
        status=WorkflowStatus.DRAFT,
    )
    audit_helper.apply_audit_create(note, current_user.id)
    session.add(note)
    session.commit()
    session.refresh(note)
    return _note_to_read(note)


@router.get(
    "/portfolios/{portfolio_id}/financial-notes/{note_id}",
    response_model=FinancialNoteRead,
)
def get_financial_note(
    portfolio_id: int,
    note_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """Get a specific financial note."""
    return _note_to_read(_get_note(note_id, portfolio_id, session))


@router.patch(
    "/portfolios/{portfolio_id}/financial-notes/{note_id}",
    response_model=FinancialNoteRead,
)
def update_financial_note(
    portfolio_id: int,
    note_id: int,
    body: FinancialNoteUpdate,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Update a financial note's content or amount.
    Only DRAFT or SUBMITTED notes can be edited (A-3 / workflow immutability).
    """
    note = _get_note(note_id, portfolio_id, session)
    wf.assert_mutable(note)

    if body.content is not None:
        note.content = body.content
    if body.amount is not None:
        note.amount = Decimal(body.amount)

    audit_helper.apply_audit_update(note, current_user.id)
    session.add(note)
    session.commit()
    session.refresh(note)
    return _note_to_read(note)


@router.post(
    "/portfolios/{portfolio_id}/financial-notes/{note_id}/transition",
    response_model=FinancialNoteRead,
)
def transition_financial_note(
    portfolio_id: int,
    note_id: int,
    body: WorkflowTransition,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context),
) -> Any:
    """
    Transition a financial note through its workflow.
    Only company admins can approve or lock notes.
    """
    note = _get_note(note_id, portfolio_id, session)

    allowed_next = VALID_TRANSITIONS.get(note.status, set())
    if body.status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from {note.status.value} to {body.status.value}",
        )

    # APPROVED and LOCKED transitions require company admin
    if body.status in (WorkflowStatus.APPROVED, WorkflowStatus.LOCKED):
        if not context.is_company_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admin access required for this transition",
            )

    wf.set_status(note, body.status, current_user.id)
    audit_helper.apply_audit_update(note, current_user.id)
    session.add(note)
    session.commit()
    session.refresh(note)
    return _note_to_read(note)


@router.delete(
    "/portfolios/{portfolio_id}/financial-notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_financial_note(
    portfolio_id: int,
    note_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Soft-delete a financial note. A-3: records are never permanently deleted.
    LOCKED notes cannot be deleted. Company admin only.
    """
    note = _get_note(note_id, portfolio_id, session)

    if note.status == WorkflowStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="LOCKED notes cannot be deleted",
        )

    note.deleted_at = datetime.now(timezone.utc)
    audit_helper.apply_audit_update(note, current_user.id)
    session.add(note)
    session.commit()
