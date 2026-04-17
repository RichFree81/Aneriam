"""add_description_logo_updated_at_to_portfolio

Resolves the Portfolio frontend/backend contract mismatch (BACKEND_AUDIT.md §5 #1–#3):
the frontend type expects description, logo, and updated_at on Portfolio but the backend
table does not provide them. This migration adds the three columns.

updated_at is added following the three-step pattern used elsewhere in the chain
(see b2c3d4e5f607_add_company_id_to_project.py):
    1. add the column nullable
    2. backfill UPDATE portfolio SET updated_at = created_at WHERE updated_at IS NULL
    3. ALTER COLUMN updated_at SET NOT NULL with a server default of NOW()

description and logo are added as nullable TEXT, no backfill needed.

Revision ID: b90fbd5c01d5
Revises: f3a4b5c6d7e8
Create Date: 2026-04-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b90fbd5c01d5'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add description, logo, updated_at to portfolio."""
    # description and logo are straightforward: nullable TEXT.
    op.add_column('portfolio', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('portfolio', sa.Column('logo', sa.Text(), nullable=True))

    # updated_at: three-step to end up with NOT NULL + server default NOW().
    # Step 1: add the column nullable so existing rows are accepted.
    op.add_column(
        'portfolio',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Step 2: backfill — existing rows have never been updated, so seed updated_at
    # to created_at so the invariant updated_at >= created_at holds from the start.
    op.execute("UPDATE portfolio SET updated_at = created_at WHERE updated_at IS NULL")

    # Step 3: make NOT NULL and give it a server-side default so future INSERTs that
    # forget to set it (e.g. a raw SQL script) still end up with a valid value.
    op.alter_column(
        'portfolio',
        'updated_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    """Downgrade schema: drop updated_at, logo, description from portfolio (reverse order)."""
    op.drop_column('portfolio', 'updated_at')
    op.drop_column('portfolio', 'logo')
    op.drop_column('portfolio', 'description')
