"""
User Management API — C-3.

Endpoints to list, create, update, and deactivate users.
Currently only the seed script can create users; these endpoints fix that.

Access rules:
  - System admin (UserRole.ADMIN / is_superuser): full control over all users.
  - Company admin: create/manage users within their own company only.
  - Regular users: read their own profile only.
"""
from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, get_request_context, require_company_admin
from app.core import security
from app.core.database import get_session
from app.models import User
from app.models.enums import UserRole
from app.schemas import RequestContext, UserCreate, UserRead, UserUpdate

router = APIRouter()


def _to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        company_id=user.company_id,
    )


@router.get("/me", response_model=UserRead)
def get_current_user_profile(current_user: User = Depends(get_current_user)) -> Any:
    """Return the currently authenticated user's profile."""
    return _to_user_read(current_user)


@router.get("", response_model=List[UserRead])
def list_users(
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    List users within the current company.
    Company admin only. System admins see all users.
    """
    if context.user.role == UserRole.ADMIN:
        # System admin: return all users
        users = session.exec(select(User)).all()
    else:
        # Company admin: return only users in their company
        users = session.exec(
            select(User).where(User.company_id == context.company_id)
        ).all()

    return [_to_user_read(u) for u in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Create a new user.
    Company admins can only create users within their own company.
    System admins can assign any company_id.
    """
    # Company admins cannot create system admins or users for other companies.
    if context.user.role != UserRole.ADMIN:
        if body.role == UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only system admins can create admin users",
            )
        # Force the new user into the company admin's company
        effective_company_id = context.company_id
    else:
        effective_company_id = body.company_id

    # Check for duplicate email
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        password_hash=security.get_password_hash(body.password),
        full_name=body.full_name,
        role=body.role,
        is_active=True,
        company_id=effective_company_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_user_read(user)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Get a specific user.
    Company admins can only view users within their own company.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Company admins cannot view users from other companies
    if context.user.role != UserRole.ADMIN and user.company_id != context.company_id:
        raise HTTPException(status_code=404, detail="User not found")

    return _to_user_read(user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> Any:
    """
    Update a user's profile, role, or status.
    Company admins can only update users within their own company.
    Company admins cannot promote users to system admin.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Company admins: scope check
    if context.user.role != UserRole.ADMIN:
        if user.company_id != context.company_id:
            raise HTTPException(status_code=404, detail="User not found")
        if body.role == UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only system admins can assign admin role",
            )
        if body.company_id is not None and body.company_id != context.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot move users to another company",
            )

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.company_id is not None:
        user.company_id = body.company_id

    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_user_read(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    session: Session = Depends(get_session),
    context: RequestContext = Depends(require_company_admin),
) -> None:
    """
    Deactivate a user (soft disable — is_active = False).
    Company admins can only deactivate users in their own company.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if context.user.role != UserRole.ADMIN and user.company_id != context.company_id:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deactivation
    if user.id == context.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user.is_active = False
    session.add(user)
    session.commit()
