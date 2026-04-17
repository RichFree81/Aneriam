"""add_security_tables

D-2: Add the revoked_token table for persistent JWT revocation storage.

The in-memory blacklist in security.py is lost on server restart, making
previously logged-out tokens valid again. This table persists revoked JTIs.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-03-01
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'revoked_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti', name='revoked_token_jti_uc'),
    )
    op.create_index('ix_revoked_token_jti', 'revoked_token', ['jti'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_revoked_token_jti', table_name='revoked_token')
    op.drop_table('revoked_token')
