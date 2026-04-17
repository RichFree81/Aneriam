"""add_project_id_to_financial_note

M-3 fix: FinancialNote had no FK relationship to Project, leaving its intended scope
ambiguous. It belonged to a portfolio but not necessarily to a specific project, making
queries and access control harder to reason about.

This migration adds an optional project_id FK. Nullable so that existing notes (and
future portfolio-level notes) are still valid without a project assignment.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f607
Create Date: 2026-02-27
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('financial_note', sa.Column('project_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_financial_note_project_id'), 'financial_note', ['project_id'], unique=False)
    op.create_foreign_key(
        'financial_note_project_id_fkey',
        'financial_note', 'project',
        ['project_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('financial_note_project_id_fkey', 'financial_note', type_='foreignkey')
    op.drop_index(op.f('ix_financial_note_project_id'), table_name='financial_note')
    op.drop_column('financial_note', 'project_id')
