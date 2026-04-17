"""
Revoked Token — persistent JWT revocation store.

D-2: The in-memory blacklist in security.py is lost on server restart, meaning
explicitly logged-out tokens become valid again. This model persists revoked JTIs
to the database so they survive restarts.

Expired tokens are automatically ignored by the JWT library's expiry check, so we do
not need to purge this table proactively — but a background task could periodically
delete rows where revoked_at + token_expiry < now to keep the table small.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class RevokedToken(SQLModel, table=True):
    __tablename__ = "revoked_token"

    id: Optional[int] = Field(default=None, primary_key=True)
    jti: str = Field(unique=True, index=True)
    revoked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
