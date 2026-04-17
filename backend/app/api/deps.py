from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlmodel import Session, select
from app.core import security
from app.core.database import get_session
from app.models import User, PortfolioUser, Portfolio
from app.models.enums import UserRole
from app.schemas import TokenData, RequestContext, UserRead

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    session: Session = Depends(get_session),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Validate token type — only accept access tokens here
        if payload.get("type") != "access":
            raise credentials_exception

        # D-2: Check JTI revocation (checks in-memory cache first, then DB)
        jti: Optional[str] = payload.get("jti")
        if jti is None or security.is_token_revoked(jti, session=session):
            raise credentials_exception

        token_data = TokenData(username=username)
    except (JWTError, ValidationError):
        raise credentials_exception

    try:
        user_id = int(token_data.username)
    except ValueError:
        raise credentials_exception

    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception

    # H-2: inactive user is Forbidden (403), not a Bad Request (400)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return user


def get_request_context(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> RequestContext:
    company_id = current_user.company_id

    # Guard: reject users without a company assignment (unless superuser)
    if not company_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no company assignment"
        )

    # Get portfolio access
    stmt = select(PortfolioUser).where(PortfolioUser.user_id == current_user.id)
    # Ensure scoped to company if set (though constraints enforce it)
    if company_id:
        stmt = stmt.where(PortfolioUser.company_id == company_id)

    portfolio_users = session.exec(stmt).all()

    allowed_ids = [pu.portfolio_id for pu in portfolio_users]
    roles = {pu.portfolio_id: pu.role for pu in portfolio_users}

    is_company_admin = current_user.role in (UserRole.ADMIN, UserRole.COMPANY_ADMIN)

    return RequestContext(
        user=UserRead.model_validate(current_user),
        company_id=company_id,
        allowed_portfolio_ids=allowed_ids,
        roles=roles,
        is_company_admin=is_company_admin
    )


def require_company_admin(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Dependency: raise 403 unless the current user is a company admin or system admin."""
    if not context.is_company_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company admin access required",
        )
    return context


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: raise 403 unless the current user is a system-level admin."""
    if current_user.role != UserRole.ADMIN and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin access required",
        )
    return current_user


def get_valid_portfolio(
    portfolio_id: int,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(get_request_context)
) -> Portfolio:
    # 1. Fetch portfolio (A-3: treat soft-deleted as not found)
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio or portfolio.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # 2. Check Company Scope — always enforce when company_id is set
    if context.company_id is not None and portfolio.company_id != context.company_id:
        # Portfolio belongs to another company → 404 to hide existence
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # 3. Check User Access
    if context.is_company_admin:
        return portfolio

    if portfolio_id not in context.allowed_portfolio_ids:
        raise HTTPException(status_code=403, detail="Access denied to this portfolio")

    return portfolio
