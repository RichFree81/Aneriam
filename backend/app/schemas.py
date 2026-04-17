from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.enums import UserRole, PortfolioRole


class LoginRequest(BaseModel):
    username: EmailStr  # Named 'username' for OAuth2 compatibility; must be a valid email address.
    password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    company_id: Optional[int] = None
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserRead


class RequestContext(BaseModel):
    user: UserRead
    company_id: Optional[int]
    allowed_portfolio_ids: list[int]
    roles: dict[int, str]
    is_company_admin: bool


class ProjectCreate(BaseModel):
    """Schema for creating a project. Excludes auto-managed fields (id, timestamps)."""
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True


class ProjectUpdate(BaseModel):
    """Schema for updating a project. All fields optional."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


# ── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    logo: Optional[str] = None


class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    description: Optional[str] = None
    logo: Optional[str] = None


# ── User Management ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: UserRole = UserRole.USER
    company_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    company_id: Optional[int] = None


# ── Settings ─────────────────────────────────────────────────────────────────

class SettingsWrite(BaseModel):
    """Map of key → value pairs to write for a module."""
    settings: Dict[str, str]


class SettingsRead(BaseModel):
    """Resolved settings: company overrides merged with application defaults."""
    module_key: str
    settings: Dict[str, str]


# ── Portfolio Access ──────────────────────────────────────────────────────────

class PortfolioAccessGrant(BaseModel):
    user_id: int
    role: PortfolioRole


class PortfolioAccessUpdate(BaseModel):
    role: PortfolioRole


class PortfolioAccessRead(BaseModel):
    id: int
    user_id: int
    portfolio_id: int
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ── Cross-Company Collaboration ───────────────────────────────────────────────

class CollaboratorInvite(BaseModel):
    company_id: int
    collaboration_role: str = Field(min_length=1, max_length=100)


class CollaboratorStatusUpdate(BaseModel):
    status: str  # Accepted | Declined
