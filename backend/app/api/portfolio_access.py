"""
Portfolio Access Management API — C-8.

Endpoints to assign users to portfolios (creating/updating PortfolioUser records)
and to remove their access (soft-delete).

Access rules:
  - Company admin only: grant and revoke portfolio access.
  - Any authorised user can view their own access (via the portfolios list).
"""
from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_request_context, get_valid_portfolio, require_company_admin
from app.core.database import get_session
from app.models import Portfolio, PortfolioUser, User
from app.schemas import (
    PortfolioAccessGrant,
    PortfolioAccessRead,
    PortfolioAccessUpdate,
    RequestContext,
)

router = APIRouter()


@router.get("/{portfolio_id}/access", response_model=List[PortfolioAccessRead])
def list_portfolio_access(
    portfolio_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    List all user access grants for a portfolio.
    Only non-soft-deleted grants are returned.
    Company admin only.
    """
    grants = session.exec(
        select(PortfolioUser).where(
            PortfolioUser.portfolio_id == portfolio_id,
            PortfolioUser.deleted_at.is_(None),
        )
    ).all()
    return grants


@router.post("/{portfolio_id}/access", response_model=PortfolioAccessRead, status_code=status.HTTP_201_CREATED)
def grant_portfolio_access(
    portfolio_id: int,
    body: PortfolioAccessGrant,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Grant a user access to a portfolio.
    If the user already has access (including a soft-deleted grant), it is restored/updated.
    Company admin only.
    """
    # Verify the user exists and belongs to this company
    user = session.get(User, body.user_id)
    if not user or user.company_id != context.company_id:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for an existing grant (including soft-deleted)
    existing = session.exec(
        select(PortfolioUser).where(
            PortfolioUser.portfolio_id == portfolio_id,
            PortfolioUser.user_id == body.user_id,
        )
    ).first()

    if existing:
        existing.role = body.role
        existing.is_active = True
        existing.deleted_at = None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    grant = PortfolioUser(
        company_id=context.company_id,
        portfolio_id=portfolio_id,
        user_id=body.user_id,
        role=body.role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(grant)
    session.commit()
    session.refresh(grant)
    return grant


@router.patch("/{portfolio_id}/access/{grant_id}", response_model=PortfolioAccessRead)
def update_portfolio_access(
    portfolio_id: int,
    grant_id: int,
    body: PortfolioAccessUpdate,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """Update the role on an existing portfolio access grant. Company admin only."""
    grant = session.get(PortfolioUser, grant_id)
    if not grant or grant.portfolio_id != portfolio_id or grant.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Access grant not found")

    grant.role = body.role
    session.add(grant)
    session.commit()
    session.refresh(grant)
    return grant


@router.delete("/{portfolio_id}/access/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_portfolio_access(
    portfolio_id: int,
    grant_id: int,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Soft-delete a portfolio access grant, revoking the user's access.
    A-3: records are never permanently deleted.
    Company admin only.
    """
    grant = session.get(PortfolioUser, grant_id)
    if not grant or grant.portfolio_id != portfolio_id or grant.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Access grant not found")

    grant.deleted_at = datetime.now(timezone.utc)
    grant.is_active = False
    session.add(grant)
    session.commit()
