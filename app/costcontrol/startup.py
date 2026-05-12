"""Database startup and seed orchestration for the Cost Control app."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import REGISTER_DIR
from .database import Base, SessionLocal, engine
from .packages_ingest import seed_packages
from .seed import seed_control_accounts, seed_projects


logger = logging.getLogger(__name__)


STARTUP_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE projects ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE projects ADD COLUMN current_budget NUMERIC(18,2)",
    "ALTER TABLE projects ADD COLUMN approved_capex NUMERIC(18,2)",
    "ALTER TABLE projects ADD COLUMN planned_fy2027 NUMERIC(18,2)",
    "ALTER TABLE transactions ADD COLUMN vendor_name TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE transactions ADD COLUMN po_number TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE transactions ADD COLUMN po_description TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE po_lines ADD COLUMN name TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE po_lines ADD COLUMN actual_amount NUMERIC(18,2) NOT NULL DEFAULT 0",
    "ALTER TABLE packages ADD COLUMN is_contracted BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE package_cost_nodes ADD COLUMN unit TEXT NOT NULL DEFAULT 'Sum'",
    "ALTER TABLE package_cost_nodes ADD COLUMN qty NUMERIC(18,4)",
    "ALTER TABLE package_cost_nodes ADD COLUMN rate NUMERIC(18,2)",
    "ALTER TABLE package_cost_nodes ADD COLUMN pre_award_unit TEXT NOT NULL DEFAULT 'Sum'",
    "ALTER TABLE package_cost_nodes ADD COLUMN pre_award_qty NUMERIC(18,4)",
    "ALTER TABLE package_cost_nodes ADD COLUMN pre_award_rate NUMERIC(18,2)",
    "ALTER TABLE package_cost_nodes ADD COLUMN contract_unit TEXT NOT NULL DEFAULT 'Sum'",
    "ALTER TABLE package_cost_nodes ADD COLUMN contract_qty NUMERIC(18,4)",
    "ALTER TABLE package_cost_nodes ADD COLUMN contract_rate NUMERIC(18,2)",
    (
        "CREATE TABLE IF NOT EXISTS cost_node_audit_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "cost_node_id INTEGER NOT NULL REFERENCES package_cost_nodes(id) ON DELETE CASCADE, "
        "action TEXT NOT NULL, "
        "changed_at DATETIME NOT NULL, "
        "snapshot TEXT NOT NULL)"
    ),
    # C-1: PMO 18-column additions on transactions.
    "ALTER TABLE transactions ADD COLUMN account_full_name TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE transactions ADD COLUMN fiscal_year TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE transactions ADD COLUMN fiscal_quarter TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE transactions ADD COLUMN transaction_date_created DATE",
    "ALTER TABLE transactions ADD COLUMN transaction_date_closed DATE",
    # C-2: PO Detailed columns.
    "ALTER TABLE po_lines ADD COLUMN internal_id INTEGER",
    "ALTER TABLE po_lines ADD COLUMN remaining NUMERIC(18,2) NOT NULL DEFAULT 0",
    "ALTER TABLE po_lines ADD COLUMN actual NUMERIC(18,2) NOT NULL DEFAULT 0",
    "ALTER TABLE po_lines ADD COLUMN vendor TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE po_lines ADD COLUMN date DATE",
    "ALTER TABLE po_lines ADD COLUMN voided BOOLEAN NOT NULL DEFAULT 0",
    # C-3: Project Tasks hierarchy metadata.
    "ALTER TABLE project_tasks ADD COLUMN project_status TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE project_tasks ADD COLUMN parent_task_id INTEGER",
    "ALTER TABLE project_tasks ADD COLUMN date_created DATETIME",
    "ALTER TABLE project_tasks ADD COLUMN last_modified DATETIME",
    # Slice A: internal/external package distinction and award fields.
    "ALTER TABLE packages ADD COLUMN is_external BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE packages ADD COLUMN awarded_vendor_name TEXT",
    "ALTER TABLE packages ADD COLUMN awarded_amount NUMERIC(18,2)",
    "ALTER TABLE packages ADD COLUMN awarded_date DATE",
    "ALTER TABLE packages ADD COLUMN procurement_stage TEXT NOT NULL DEFAULT 'Pre-Tender'",
    # Slice E: first linked PO is Original; later links are Variations.
    "ALTER TABLE po_rto_links ADD COLUMN is_original BOOLEAN NOT NULL DEFAULT 0",
    (
        "UPDATE po_rto_links SET is_original = 1 "
        "WHERE id IN ("
        " SELECT MIN(id) FROM po_rto_links GROUP BY rto_id"
        ") AND is_original = 0"
    ),
    "UPDATE packages SET package_stage = 'Procurement' WHERE package_stage = 'Planned'",
    "UPDATE packages SET package_stage = 'Close-out'   WHERE package_stage IN ('Closeout', 'Complete')",
    # 2026-05-05: Workstreams removed from the package model.
    "ALTER TABLE package_cost_nodes DROP COLUMN workstream_id",
    "ALTER TABLE package_deliverables DROP COLUMN workstream_id",
    "DROP TABLE IF EXISTS workstreams",
    (
        "UPDATE packages SET is_external = 1 "
        "WHERE is_external = 0 "
        "AND package_type IN ("
        " 'Construction Package Labour & Materials',"
        " 'Engineering Construction Package',"
        " 'Supply Package')"
    ),
)


def _is_expected_sqlite_migration_error(exc: Exception) -> bool:
    message = str(exc).lower()
    expected_fragments = (
        "duplicate column name",
        "no such column",
    )
    return any(fragment in message for fragment in expected_fragments)


def run_startup_migrations(db: Session) -> None:
    """Run append-only SQLite startup migrations.

    Each statement is intentionally isolated because several are expected to
    fail harmlessly after they have already been applied.
    """
    for migration in STARTUP_MIGRATIONS:
        try:
            db.execute(text(migration))
            db.commit()
        except Exception as exc:
            db.rollback()
            if _is_expected_sqlite_migration_error(exc):
                logger.debug("Skipping already-applied startup migration: %s", migration)
            else:
                logger.warning(
                    "Startup migration failed and was skipped: %s",
                    migration,
                    exc_info=True,
                )


def initialise_database() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_startup_migrations(db)
        seed_control_accounts(db)
        seed_projects(db)
        seed_packages(db, REGISTER_DIR)
    finally:
        db.close()
