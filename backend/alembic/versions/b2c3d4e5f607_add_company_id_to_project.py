"""add_company_id_to_project

M-2 fix: Add company_id to the project table, denormalised from portfolio.company_id.
This avoids a JOIN through portfolio for every tenant-scoped project query and makes the
access pattern consistent with financial_note (which already carries company_id).

Backfill: existing projects are updated by following the portfolio → company chain.

Revision ID: b2c3d4e5f607
Revises: a2b3c4d5e6f7
Create Date: 2026-02-27
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f607'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_project_company_id'), 'project', ['company_id'], unique=False)

    # Backfill: set company_id from the parent portfolio
    op.execute("""
        UPDATE project
        SET company_id = portfolio.company_id
        FROM portfolio
        WHERE project.portfolio_id = portfolio.id
    """)

    op.create_foreign_key(
        'project_company_id_fkey',
        'project', 'company',
        ['company_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('project_company_id_fkey', 'project', type_='foreignkey')
    op.drop_index(op.f('ix_project_company_id'), table_name='project')
    op.drop_column('project', 'company_id')
