import sqlalchemy as sa
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, UniqueConstraint
from app.models.enums import PortfolioRole

class PortfolioUser(SQLModel, table=True):
    __tablename__ = "portfolio_user"
    __table_args__ = (UniqueConstraint("user_id", "portfolio_id", name="_user_portfolio_uc"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(index=True) # Denormalized for easier queries
    portfolio_id: int = Field(foreign_key="portfolio.id")
    user_id: int = Field(foreign_key="user.id")
    role: PortfolioRole = Field(
        sa_column=sa.Column(
            sa.Enum(PortfolioRole, name="portfoliorole", values_callable=lambda x: [e.value for e in x])
        )
    )
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # A-3: Soft delete — records are never permanently deleted; deleted_at is set instead.
    deleted_at: Optional[datetime] = Field(default=None)
