"""
Authentication API.

D-1: Login endpoint now tracks failed attempts per IP and returns 429 Too Many
     Requests once the threshold is exceeded.
D-2: Token revocation now writes to the database so JTI blacklists survive restarts.
D-3: Password change (authenticated) and admin-set-password endpoints added.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_admin
from app.core import security
from app.core.database import get_session
from app.models import Company, User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    UserRead,
)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _build_user_read(user: User, session: Session) -> UserRead:
    """Construct a UserRead, including a company name lookup."""
    company_name: Optional[str] = None
    if user.company_id:
        company = session.get(Company, user.company_id)
        company_name = company.name if company else None

    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        company_id=user.company_id,
        company_name=company_name,
    )


def _client_ip(request: Request) -> str:
    """Extract the real client IP, honouring X-Forwarded-For if present."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    body: LoginRequest,
    session: Session = Depends(get_session),
) -> Any:
    client_ip = _client_ip(request)

    # D-1: Reject if IP is already over the rate limit
    if security.is_ip_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait before trying again.",
        )

    # 1. Check user exists
    statement = select(User).where(User.email == body.username)
    user = session.exec(statement).first()

    # 2. Verify password
    if not user or not security.verify_password(body.password, user.password_hash):
        # D-1: Record the failed attempt
        security.record_login_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # 3. Check active — H-2: use 403 Forbidden, not 400 Bad Request
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    # D-1: Clear the attempt counter on successful login
    security.reset_login_attempts(client_ip)

    # 4. Issue tokens
    access_token = security.create_access_token(subject=user.id)
    refresh_token = security.create_refresh_token(subject=user.id)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=_build_user_read(user, session),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> None:
    """
    Revoke the current access token by blacklisting its JTI.
    D-2: Revocation is now written to the database so it survives restarts.
    The client must also discard its locally-stored refresh token.
    """
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        jti: Optional[str] = payload.get("jti")
        if jti:
            security.revoke_token(jti, session=session)
    except JWTError:
        # Token is already invalid; nothing to revoke.
        pass


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    request_body: RefreshRequest,
    session: Session = Depends(get_session),
) -> Any:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is revoked after use (token rotation).
    D-2: Revocation is now written to the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            request_body.refresh_token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
    except JWTError:
        raise credentials_exception

    # Validate token type and JTI
    if payload.get("type") != "refresh":
        raise credentials_exception

    jti: Optional[str] = payload.get("jti")
    if jti is None or security.is_token_revoked(jti, session=session):
        raise credentials_exception

    # Look up user
    try:
        user_id = int(payload.get("sub", ""))
    except (ValueError, TypeError):
        raise credentials_exception

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    # Rotate: revoke the used refresh token, issue a new pair
    security.revoke_token(jti, session=session)
    new_access_token = security.create_access_token(subject=user.id)
    new_refresh_token = security.create_refresh_token(subject=user.id)

    return LoginResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=_build_user_read(user, session),
    )


# ── D-3: Password management ──────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminSetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    D-3: Allow an authenticated user to change their own password.
    Requires the current password for verification.
    """
    if not security.verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password",
        )

    current_user.password_hash = security.get_password_hash(body.new_password)
    session.add(current_user)
    session.commit()


@router.post("/admin/reset-password/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_reset_password(
    user_id: int,
    body: AdminSetPasswordRequest,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_admin),
) -> None:
    """
    D-3: Allow a system admin to set a new password for any user.
    Use this when a user cannot access their account. A full email-based
    self-service reset requires an email service (not yet configured).
    System admin only.
    """
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.password_hash = security.get_password_hash(body.new_password)
    session.add(target_user)
    session.commit()
