from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_request_context, get_valid_portfolio, require_company_admin
from app.core.database import get_session
from app.models import Portfolio
from app.schemas import PortfolioCreate, PortfolioUpdate, RequestContext

router = APIRouter()

@router.get("", response_model=List[Portfolio])
def get_portfolios(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context)
) -> Any:
    """
    List portfolios accessible to the current user.
    """
    if context.is_company_admin:
        # Return all non-deleted portfolios for the user's company.
        # A-3: Always filter soft-deleted records from list views.
        stmt = select(Portfolio).where(
            Portfolio.company_id == context.company_id,
            Portfolio.deleted_at.is_(None),
        )
        return session.exec(stmt).all()

    # Otherwise return only allowed portfolios
    if not context.allowed_portfolio_ids:
        return []

    # A-3: Always filter soft-deleted records from list views.
    stmt = select(Portfolio).where(
        Portfolio.id.in_(context.allowed_portfolio_ids),
        Portfolio.deleted_at.is_(None),
    )
    return session.exec(stmt).all()

@router.get("/{portfolio_id}", response_model=Portfolio)
def get_portfolio(
    portfolio: Portfolio = Depends(get_valid_portfolio)
) -> Any:
    """
    Get a specific portfolio if authorized.
    """
    return portfolio


@router.post("", response_model=Portfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    body: PortfolioCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Create a new portfolio within the current company.
    Company admin only.
    """
    if not context.company_id:
        raise HTTPException(status_code=400, detail="No company context")

    now = datetime.now(timezone.utc)
    portfolio = Portfolio(
        company_id=context.company_id,
        name=body.name,
        code=body.code,
        description=body.description,
        logo=body.logo,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


@router.patch("/{portfolio_id}", response_model=Portfolio)
def update_portfolio(
    body: PortfolioUpdate,
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Update portfolio name, active status, description, or logo.
    Company admin only.
    """
    if body.name is not None:
        portfolio.name = body.name
    if body.is_active is not None:
        portfolio.is_active = body.is_active
    if body.description is not None:
        portfolio.description = body.description
    if body.logo is not None:
        portfolio.logo = body.logo

    portfolio.updated_at = datetime.now(timezone.utc)
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    session: Session = Depends(get_session),
    portfolio: Portfolio = Depends(get_valid_portfolio),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Soft-delete a portfolio (sets deleted_at). A-3: records are never permanently deleted.
    Company admin only.
    """
    now = datetime.now(timezone.utc)
    portfolio.deleted_at = now
    portfolio.updated_at = now
    session.add(portfolio)
    session.commit()
