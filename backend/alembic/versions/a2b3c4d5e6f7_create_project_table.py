"""create_project_table

Restores the project table creation that was accidentally removed when migrations
32d7cd9ae5ab and 5618a8603e02 were renamed on this branch. Without this migration
the entire main chain fails because every downstream migration ALTER/ADD-COLUMNs the
project table that was never created.

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE projectstatus AS ENUM ('ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$;"
    )

    op.create_table(
        'project',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column(
            'status',
            postgresql.ENUM(
                'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED',
                name='projectstatus',
                create_type=False,
            ),
            nullable=False,
            server_default='ACTIVE',
        ),
        sa.Column('value', sa.Numeric(14, 2), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolio.id'], name='project_portfolio_id_fkey'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_project_portfolio_id', 'project', ['portfolio_id'])
    op.create_index('ix_project_name', 'project', ['name'])


def downgrade() -> None:
    op.drop_index('ix_project_name', table_name='project')
    op.drop_index('ix_project_portfolio_id', table_name='project')
    op.drop_table('project')
    op.execute('DROP TYPE IF EXISTS projectstatus')
