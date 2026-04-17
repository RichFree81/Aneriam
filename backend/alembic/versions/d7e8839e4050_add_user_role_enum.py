"""add_user_role_enum

Revision ID: d7e8839e4050
Revises: 4a20343b5408
Create Date: 2026-02-12 21:50:13.598540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd7e8839e4050'
down_revision: Union[str, Sequence[str], None] = '4a20343b5408'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the enum type
userrole_enum = sa.Enum('Admin', 'CompanyAdmin', 'User', name='userrole')


def upgrade() -> None:
    """Upgrade schema: convert user.role from VARCHAR to userrole enum."""
    # 1. Create the enum type
    userrole_enum.create(op.get_bind(), checkfirst=True)

    # 2. Map existing string values to new enum values
    op.execute("UPDATE \"user\" SET role = 'CompanyAdmin' WHERE role = 'admin'")
    op.execute("UPDATE \"user\" SET role = 'User' WHERE role = 'user'")
    op.execute("UPDATE \"user\" SET role = 'Admin' WHERE role = 'Admin'")  # no-op, already correct
    # Catch-all: any unrecognized role becomes 'User'
    op.execute("UPDATE \"user\" SET role = 'User' WHERE role NOT IN ('Admin', 'CompanyAdmin', 'User')")

    # 3. Alter column type
    op.execute(
        'ALTER TABLE "user" ALTER COLUMN role TYPE userrole USING role::userrole'
    )
    op.execute(
        'ALTER TABLE "user" ALTER COLUMN role SET NOT NULL'
    )
    op.execute(
        "ALTER TABLE \"user\" ALTER COLUMN role SET DEFAULT 'User'"
    )


def downgrade() -> None:
    """Downgrade schema: revert user.role from userrole enum to VARCHAR."""
    # 1. Convert back to VARCHAR
    op.execute(
        'ALTER TABLE "user" ALTER COLUMN role TYPE VARCHAR USING role::text'
    )
    op.execute(
        "ALTER TABLE \"user\" ALTER COLUMN role SET DEFAULT 'user'"
    )

    # 2. Map enum values back to old strings
    op.execute("UPDATE \"user\" SET role = 'admin' WHERE role = 'CompanyAdmin'")
    op.execute("UPDATE \"user\" SET role = 'admin' WHERE role = 'Admin'")
    op.execute("UPDATE \"user\" SET role = 'user' WHERE role = 'User'")

    # 3. Drop the enum type
    userrole_enum.drop(op.get_bind(), checkfirst=True)
