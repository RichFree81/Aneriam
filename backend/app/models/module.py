from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

class Module(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    name: str
    description: Optional[str] = None
    enabled: bool = Field(default=False)
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
