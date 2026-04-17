"""add_foundation_tables

Phase 1 architectural foundations:
  A-1: field_definition + field_assignment tables for the field library.
       Also adds field_values (JSON text) to the project table.
  A-2: project_company table for cross-company collaboration.
  A-4: module_settings table for per-company module configuration.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-03-01
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ A-1
    # field_definition: hierarchical library of field definitions.
    # company_id IS NULL = system/module-level; NOT NULL = company-owned.
    op.create_table(
        'field_definition',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('module_key', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('field_type', sa.String(), nullable=False),
        sa.Column('options', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_deprecated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], name='field_definition_company_id_fkey'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'module_key', 'name', name='_field_def_company_module_name_uc'),
    )
    op.create_index('ix_field_definition_company_id', 'field_definition', ['company_id'])
    op.create_index('ix_field_definition_module_key', 'field_definition', ['module_key'])

    # field_assignment: which field definitions are active on a specific project.
    op.create_table(
        'field_assignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('field_definition_id', sa.Integer(), nullable=False),
        sa.Column('required_override', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['field_definition_id'], ['field_definition.id'],
                                name='field_assignment_field_definition_id_fkey'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'],
                                name='field_assignment_project_id_fkey'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'field_definition_id', name='_field_assign_project_field_uc'),
    )
    op.create_index('ix_field_assignment_project_id', 'field_assignment', ['project_id'])
    op.create_index('ix_field_assignment_field_definition_id', 'field_assignment', ['field_definition_id'])

    # Add field_values JSON column to project.
    op.add_column('project', sa.Column('field_values', sa.Text(), nullable=True))

    # ------------------------------------------------------------------ A-2
    # project_company: cross-company collaboration on a project.
    op.create_table(
        'project_company',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('collaboration_role', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='Pending'),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invited_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'],
                                name='project_company_company_id_fkey'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['user.id'],
                                name='project_company_invited_by_user_id_fkey'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'],
                                name='project_company_project_id_fkey'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'company_id', name='_project_company_uc'),
    )
    op.create_index('ix_project_company_project_id', 'project_company', ['project_id'])
    op.create_index('ix_project_company_company_id', 'project_company', ['company_id'])

    # ------------------------------------------------------------------ A-4
    # module_settings: per-company, per-module key-value configuration.
    op.create_table(
        'module_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('module_key', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'],
                                name='module_settings_company_id_fkey'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'module_key', 'key', name='_module_settings_uc'),
    )
    op.create_index('ix_module_settings_company_id', 'module_settings', ['company_id'])
    op.create_index('ix_module_settings_module_key', 'module_settings', ['module_key'])


def downgrade() -> None:
    op.drop_index('ix_module_settings_module_key', table_name='module_settings')
    op.drop_index('ix_module_settings_company_id', table_name='module_settings')
    op.drop_table('module_settings')

    op.drop_index('ix_project_company_company_id', table_name='project_company')
    op.drop_index('ix_project_company_project_id', table_name='project_company')
    op.drop_table('project_company')

    op.drop_column('project', 'field_values')

    op.drop_index('ix_field_assignment_field_definition_id', table_name='field_assignment')
    op.drop_index('ix_field_assignment_project_id', table_name='field_assignment')
    op.drop_table('field_assignment')

    op.drop_index('ix_field_definition_module_key', table_name='field_definition')
    op.drop_index('ix_field_definition_company_id', table_name='field_definition')
    op.drop_table('field_definition')
