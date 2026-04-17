"""add_company_id_to_financial_note

Revision ID: c41d24b0c3dc
Revises: d7e8839e4050
Create Date: 2026-02-12 22:20:28.108460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41d24b0c3dc'
down_revision: Union[str, Sequence[str], None] = 'd7e8839e4050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade: Add company_id to financial_note and backfill data."""
    # 1. Add column as nullable first
    op.add_column('financial_note', sa.Column('company_id', sa.Integer(), nullable=True))
    
    # 2. Backfill company_id from linked portfolio
    op.execute("""
        UPDATE financial_note 
        SET company_id = portfolio.company_id 
        FROM portfolio 
        WHERE financial_note.portfolio_id = portfolio.id
    """)

    # 3. Handle any orphaned notes (if any remain without portfolio, though valid FK prevents this)
    # Just in case, set to a default or delete. Assuming integrity holds.

    # 4. Alter column to NOT NULL
    op.alter_column('financial_note', 'company_id', nullable=False)

    # 5. Create index and Foreign Key
    op.create_index(op.f('ix_financial_note_company_id'), 'financial_note', ['company_id'], unique=False)
    op.create_foreign_key(None, 'financial_note', 'company', ['company_id'], ['id'])


def downgrade() -> None:
    """Downgrade: Drop company_id from financial_note."""
    op.drop_constraint(None, 'financial_note', type_='foreignkey')
    op.drop_index(op.f('ix_financial_note_company_id'), table_name='financial_note')
    op.drop_column('financial_note', 'company_id')
