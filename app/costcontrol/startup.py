"""Database startup and seed orchestration for the Cost Control app."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import REGISTER_DIR
from .database import Base, SessionLocal, engine
from .packages_ingest import seed_packages
from .seed import seed_control_accounts, seed_cost_control_master_data, seed_projects


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
    (
        "CREATE TABLE IF NOT EXISTS package_cost_sheets ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE, "
        "sheet_number VARCHAR(30) NOT NULL, "
        "title TEXT NOT NULL, "
        "sheet_type VARCHAR(20) NOT NULL DEFAULT 'Original', "
        "status VARCHAR(30) NOT NULL DEFAULT 'Draft', "
        "description TEXT NOT NULL DEFAULT '', "
        "source_sheet_id INTEGER REFERENCES package_cost_sheets(id), "
        "locked_at DATETIME, "
        "display_order INTEGER NOT NULL DEFAULT 0, "
        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "UNIQUE(package_id, sheet_number))"
    ),
    "ALTER TABLE package_cost_nodes ADD COLUMN cost_sheet_id INTEGER REFERENCES package_cost_sheets(id) ON DELETE CASCADE",
    "ALTER TABLE package_cost_sheets ADD COLUMN source_sheet_id INTEGER REFERENCES package_cost_sheets(id)",
    "ALTER TABLE package_cost_sheets ADD COLUMN locked_at DATETIME",
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
    # WBS/PBS/CBS rebuild.
    "ALTER TABLE package_deliverables RENAME TO package_documents",
    "ALTER TABLE packages ADD COLUMN package_source TEXT NOT NULL DEFAULT 'Internal'",
    "ALTER TABLE packages ADD COLUMN pricing_basis TEXT NOT NULL DEFAULT 'LS'",
    "ALTER TABLE packages ADD COLUMN planned_value NUMERIC(18,2) NOT NULL DEFAULT 0",
    "UPDATE packages SET package_source = CASE WHEN is_external = 1 THEN 'External' ELSE 'Internal' END",
)


def _is_expected_sqlite_migration_error(exc: Exception) -> bool:
    message = str(exc).lower()
    expected_fragments = (
        "duplicate column name",
        "no such column",
        "unknown column",
        "there is already another table",
        "no such table",
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


def _table_exists(db: Session, table_name: str) -> bool:
    return db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :name"),
        {"name": table_name},
    ).first() is not None


def _column_exists(db: Session, table_name: str, column_name: str) -> bool:
    if not _table_exists(db, table_name):
        return False
    return column_name in [row[1] for row in db.execute(text(f"PRAGMA table_info({table_name})")).fetchall()]


def migrate_cost_component_schema(db: Session) -> None:
    """Rename the old direct Level 2 schema to Cost Component terminology.

    This runs before SQLAlchemy creates missing tables. Existing user databases
    therefore keep their data while moving from the old table/column names onto
    the new Cost Component names.
    """
    if not any(
        _table_exists(db, table)
        for table in ("deliverables", "deliverable_plant_areas", "cost_item_codes")
    ):
        return

    logger.info("Migrating direct Level 2 schema to Cost Component naming")
    db.commit()
    db.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        if _table_exists(db, "deliverables") and not _table_exists(db, "cost_components"):
            db.execute(text("ALTER TABLE deliverables RENAME TO cost_components"))

        if _table_exists(db, "deliverable_plant_areas") and not _table_exists(db, "cost_component_plant_areas"):
            db.execute(text("ALTER TABLE deliverable_plant_areas RENAME TO cost_component_plant_areas"))

        if _column_exists(db, "cost_component_plant_areas", "deliverable_id"):
            db.execute(text(
                "ALTER TABLE cost_component_plant_areas "
                "RENAME COLUMN deliverable_id TO cost_component_id"
            ))

        if _column_exists(db, "cost_item_codes", "deliverable_id"):
            db.execute(text(
                "ALTER TABLE cost_item_codes "
                "RENAME COLUMN deliverable_id TO cost_component_id"
            ))

        if _table_exists(db, "cost_components"):
            db.execute(text("""
                UPDATE cost_components
                SET description = replace(replace(description, 'Deliverable', 'Cost Component'), 'deliverable', 'cost component')
                WHERE description LIKE '%Deliverable%' OR description LIKE '%deliverable%'
            """))

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to migrate Cost Component schema")
        raise
    finally:
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.commit()


def repair_package_cost_nodes_workstream_fk(db: Session) -> None:
    """Remove stale workstream_id/FK left by older SQLite schemas.

    SQLite cannot reliably drop a column that participates in a foreign key.
    Older cost-control databases can therefore retain a `workstream_id`
    reference to the removed `workstreams` table, causing inserts into
    `package_cost_nodes` to fail with "no such table: main.workstreams".
    """
    columns = [row[1] for row in db.execute(text("PRAGMA table_info(package_cost_nodes)")).fetchall()]
    foreign_keys = db.execute(text("PRAGMA foreign_key_list(package_cost_nodes)")).fetchall()
    has_stale_workstream = "workstream_id" in columns or any(row[2] == "workstreams" for row in foreign_keys)
    if not has_stale_workstream:
        return

    logger.info("Rebuilding package_cost_nodes to remove stale workstream foreign key")
    db.commit()
    db.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        db.execute(text("DROP TABLE IF EXISTS package_cost_nodes_rebuild"))
        db.execute(text("""
            CREATE TABLE package_cost_nodes_rebuild (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                cost_sheet_id INTEGER REFERENCES package_cost_sheets(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES package_cost_nodes(id) ON DELETE CASCADE,
                code VARCHAR(30) NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                is_item BOOLEAN NOT NULL DEFAULT 0,
                cc_code VARCHAR(3) REFERENCES control_accounts(code),
                unit VARCHAR(20) NOT NULL DEFAULT 'Sum',
                qty NUMERIC(18,4),
                rate NUMERIC(18,2),
                baseline_amount NUMERIC(18,2),
                pre_award_unit VARCHAR(20) NOT NULL DEFAULT 'Sum',
                pre_award_qty NUMERIC(18,4),
                pre_award_rate NUMERIC(18,2),
                pre_award_amount NUMERIC(18,2),
                contract_unit VARCHAR(20) NOT NULL DEFAULT 'Sum',
                contract_qty NUMERIC(18,4),
                contract_rate NUMERIC(18,2),
                contract_amount NUMERIC(18,2),
                display_order INTEGER NOT NULL DEFAULT 0
            )
        """))
        cost_sheet_select = "cost_sheet_id" if "cost_sheet_id" in columns else "NULL"
        db.execute(text(f"""
            INSERT INTO package_cost_nodes_rebuild (
                id, package_id, cost_sheet_id, parent_id, code, description, is_item, cc_code,
                unit, qty, rate, baseline_amount,
                pre_award_unit, pre_award_qty, pre_award_rate, pre_award_amount,
                contract_unit, contract_qty, contract_rate, contract_amount,
                display_order
            )
            SELECT
                id, package_id,
                {cost_sheet_select},
                parent_id, code, description, is_item, cc_code,
                unit, qty, rate, baseline_amount,
                COALESCE(pre_award_unit, 'Sum'), pre_award_qty, pre_award_rate, pre_award_amount,
                COALESCE(contract_unit, 'Sum'), contract_qty, contract_rate, contract_amount,
                display_order
            FROM package_cost_nodes
        """))
        db.execute(text("DROP TABLE package_cost_nodes"))
        db.execute(text("ALTER TABLE package_cost_nodes_rebuild RENAME TO package_cost_nodes"))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to rebuild package_cost_nodes")
        raise
    finally:
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.commit()


def repair_auto_cbs_cost_node_hierarchy(db: Session) -> None:
    """Flatten package cost rows created by the former CBS auto-hierarchy.

    Cost Component and Cost Item Account are CBS metadata on a cost line. They
    should not be persisted as worksheet grouping rows unless the user creates
    their own worksheet groupings.
    """
    required_tables = ("package_cost_nodes", "cost_item_codes", "cost_components")
    if not all(_table_exists(db, table) for table in required_tables):
        return

    rows = db.execute(text("""
        SELECT
            account.id AS account_node_id,
            component.id AS component_node_id
        FROM package_cost_nodes AS account
        JOIN package_cost_nodes AS component
          ON component.id = account.parent_id
        JOIN cost_item_codes AS cost_code
          ON cost_code.code = account.code
         AND cost_code.name = account.description
        JOIN cost_components AS cost_component
          ON cost_component.id = cost_code.cost_component_id
         AND cost_component.description = component.description
        WHERE account.is_item = 0
          AND component.is_item = 0
          AND component.parent_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM package_cost_nodes AS line
              WHERE line.parent_id = account.id
                AND line.is_item = 1
          )
    """)).mappings().all()
    if not rows:
        return

    logger.info("Flattening %s auto-created CBS worksheet hierarchy rows", len(rows))
    try:
        for row in rows:
            db.execute(text("""
                UPDATE package_cost_nodes
                SET parent_id = NULL
                WHERE parent_id = :account_node_id
                  AND is_item = 1
            """), {"account_node_id": row["account_node_id"]})
            db.execute(text("""
                DELETE FROM package_cost_nodes
                WHERE id = :account_node_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM package_cost_nodes AS child
                      WHERE child.parent_id = :account_node_id
                  )
            """), {"account_node_id": row["account_node_id"]})
            db.execute(text("""
                DELETE FROM package_cost_nodes
                WHERE id = :component_node_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM package_cost_nodes AS child
                      WHERE child.parent_id = :component_node_id
                  )
            """), {"component_node_id": row["component_node_id"]})
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to flatten auto-created CBS worksheet hierarchy")
        raise


def ensure_package_cost_sheets(db: Session) -> None:
    """Create original cost sheets and attach legacy package cost rows."""
    if not all(_table_exists(db, table) for table in ("packages", "package_cost_sheets", "package_cost_nodes")):
        return
    if not _column_exists(db, "package_cost_nodes", "cost_sheet_id"):
        return

    packages = db.execute(text("SELECT id FROM packages ORDER BY id")).fetchall()
    if not packages:
        return

    try:
        for (package_id,) in packages:
            original = db.execute(text("""
                SELECT id
                FROM package_cost_sheets
                WHERE package_id = :package_id AND sheet_type IN ('Original', 'Working Estimate')
                ORDER BY display_order, id
                LIMIT 1
            """), {"package_id": package_id}).first()
            if original is None:
                db.execute(text("""
                    INSERT INTO package_cost_sheets (
                        package_id, sheet_number, title, sheet_type, status,
                        description, display_order, created_at
                    )
                    VALUES (
                        :package_id, 'ORIGINAL', 'Package Base Cost', 'Working Estimate',
                        'Working', '', 0, CURRENT_TIMESTAMP
                    )
                """), {"package_id": package_id})
                original_id = db.execute(text("SELECT last_insert_rowid()")).scalar_one()
            else:
                original_id = original.id
                db.execute(text("""
                    UPDATE package_cost_sheets
                    SET title = 'Package Base Cost',
                        sheet_type = CASE WHEN sheet_type = 'Original' THEN 'Working Estimate' ELSE sheet_type END,
                        status = CASE WHEN status = 'Draft' THEN 'Working' ELSE status END
                    WHERE id = :original_id
                      AND (
                        title = 'Original Cost Sheet'
                        OR sheet_type = 'Original'
                        OR status = 'Draft'
                      )
                """), {"original_id": original_id})
            db.execute(text("""
                UPDATE package_cost_nodes
                SET cost_sheet_id = :original_id
                WHERE package_id = :package_id
                  AND cost_sheet_id IS NULL
            """), {"original_id": original_id, "package_id": package_id})
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to ensure package cost sheets")
        raise


def initialise_database() -> None:
    db = SessionLocal()
    try:
        migrate_cost_component_schema(db)
    finally:
        db.close()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_startup_migrations(db)
        repair_package_cost_nodes_workstream_fk(db)
        repair_auto_cbs_cost_node_hierarchy(db)
        ensure_package_cost_sheets(db)
        seed_control_accounts(db)
        seed_cost_control_master_data(db)
        seed_projects(db)
        seed_packages(db, REGISTER_DIR)
    finally:
        db.close()
