"""add_soft_delete_columns

B-4: Add deleted_at (nullable datetime) to Project, Portfolio, FinancialNote,
and PortfolioUser tables.

Records in this system are never permanently deleted. Setting deleted_at marks a
record as soft-deleted; all list queries must filter WHERE deleted_at IS NULL.

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-03-01
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('portfolio', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('financial_note', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('portfolio_user', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('portfolio_user', 'deleted_at')
    op.drop_column('financial_note', 'deleted_at')
    op.drop_column('portfolio', 'deleted_at')
    op.drop_column('project', 'deleted_at')
