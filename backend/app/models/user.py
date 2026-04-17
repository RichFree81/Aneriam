from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone
import sqlalchemy as sa
from app.models.enums import UserRole

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    full_name: Optional[str] = None
    role: UserRole = Field(
        default=UserRole.USER,
        sa_column=sa.Column(
            sa.Enum(UserRole, name="userrole", values_callable=lambda x: [e.value for e in x]),
            nullable=False,
            default=UserRole.USER.value
        )
    )
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    company_id: Optional[int] = Field(default=None, foreign_key="company.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
