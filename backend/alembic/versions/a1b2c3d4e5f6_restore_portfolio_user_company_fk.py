"""restore_portfolio_user_company_fk

H-1 fix: The FK from portfolio_user.company_id → company.id was silently removed in
migration 4a20343b5408 with a comment "Denormalized for easier queries" but without
documented justification or a compensating control. Without this constraint the database
cannot prevent portfolio_user rows from referencing non-existent companies, which breaks
multi-tenant data integrity guarantees.

Rationale for re-adding:
- company_id on portfolio_user is used in query filters (get_request_context in deps.py);
  invalid values would cause silent data corruption or incorrect access-control decisions.
- The portfolio.company_id FK still exists, so the denormalisation argument is weak:
  we CAN enforce the FK without a performance cost.

Revision ID: a1b2c3d4e5f6
Revises: 4a20343b5408
Create Date: 2026-02-27
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4a20343b5408'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Re-add the FK that was dropped in 4a20343b5408.
    # Before adding, clean up any orphaned rows (company_id values with no matching company).
    op.execute("""
        DELETE FROM portfolio_user
        WHERE company_id NOT IN (SELECT id FROM company)
    """)
    op.create_foreign_key(
        'portfolio_user_company_id_fkey',
        'portfolio_user', 'company',
        ['company_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('portfolio_user_company_id_fkey', 'portfolio_user', type_='foreignkey')
