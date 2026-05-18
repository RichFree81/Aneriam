from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from costcontrol.startup import (
    migrate_cost_component_schema,
    ensure_package_cost_sheets,
    repair_auto_cbs_cost_node_hierarchy,
    repair_package_cost_nodes_workstream_fk,
)


def test_migrate_cost_component_schema_renames_legacy_direct_l2_tables():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with Session(engine) as session:
        session.execute(text("PRAGMA foreign_keys=OFF"))
        session.execute(text("""
            CREATE TABLE deliverables (
                id INTEGER PRIMARY KEY,
                project_number TEXT NOT NULL,
                scope_item_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                commodity_code TEXT NOT NULL,
                cbs_l2_code TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                state TEXT NOT NULL,
                type_discriminator TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE deliverable_plant_areas (
                id INTEGER PRIMARY KEY,
                deliverable_id INTEGER NOT NULL,
                plant_area_id INTEGER NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE cost_item_codes (
                id INTEGER PRIMARY KEY,
                project_number TEXT NOT NULL,
                deliverable_id INTEGER,
                indirect_l2_code TEXT,
                code TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                name TEXT NOT NULL,
                source TEXT NOT NULL
            )
        """))
        session.execute(text("""
            INSERT INTO deliverables (
                id, project_number, scope_item_id, description, commodity_code,
                cbs_l2_code, sequence, state, type_discriminator
            ) VALUES (1, '5006', 10, 'Foundation', '205', '205.01', 1, 'Provisional', 'Asset')
        """))
        session.execute(text("""
            INSERT INTO deliverable_plant_areas (id, deliverable_id, plant_area_id)
            VALUES (1, 1, 99)
        """))
        session.execute(text("""
            INSERT INTO cost_item_codes (
                id, project_number, deliverable_id, indirect_l2_code, code, sequence, name, source
            ) VALUES (1, '5006', 1, NULL, '205.01.01', 1, 'Civil works', 'library')
        """))
        session.commit()

        migrate_cost_component_schema(session)

        tables = {
            row[0]
            for row in session.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).fetchall()
        }
        assert "cost_components" in tables
        assert "cost_component_plant_areas" in tables
        assert "deliverables" not in tables
        assert "deliverable_plant_areas" not in tables

        component_area_columns = [
            row[1]
            for row in session.execute(text("PRAGMA table_info(cost_component_plant_areas)")).fetchall()
        ]
        cost_code_columns = [
            row[1]
            for row in session.execute(text("PRAGMA table_info(cost_item_codes)")).fetchall()
        ]
        assert "cost_component_id" in component_area_columns
        assert "cost_component_id" in cost_code_columns
        assert "deliverable_id" not in component_area_columns
        assert "deliverable_id" not in cost_code_columns

        migrated_component = session.execute(text("SELECT description FROM cost_components WHERE id = 1")).scalar_one()
        migrated_code_parent = session.execute(text("SELECT cost_component_id FROM cost_item_codes WHERE id = 1")).scalar_one()
        assert migrated_component == "Foundation"
        assert migrated_code_parent == 1


def test_repair_package_cost_nodes_removes_stale_workstream_fk():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with Session(engine) as session:
        session.execute(text("PRAGMA foreign_keys=OFF"))
        session.execute(text("""
            CREATE TABLE packages (
                id INTEGER PRIMARY KEY,
                package_number TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE control_accounts (
                code VARCHAR(3) PRIMARY KEY,
                name TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE package_cost_nodes (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES package_cost_nodes(id) ON DELETE CASCADE,
                code VARCHAR(30) NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                is_item BOOLEAN NOT NULL DEFAULT 0,
                cc_code VARCHAR(3) REFERENCES control_accounts(code),
                workstream_id INTEGER REFERENCES workstreams(id) ON DELETE SET NULL,
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
        session.execute(text("INSERT INTO packages (id, package_number) VALUES (1, 'PKG')"))
        session.execute(text("INSERT INTO package_cost_nodes (package_id, code, description, is_item) VALUES (1, '01', 'Group', 0)"))
        session.commit()


def test_repair_auto_cbs_cost_node_hierarchy_flattens_old_generated_rows():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with Session(engine) as session:
        session.execute(text("PRAGMA foreign_keys=OFF"))
        session.execute(text("""
            CREATE TABLE packages (
                id INTEGER PRIMARY KEY,
                package_number TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE cost_components (
                id INTEGER PRIMARY KEY,
                project_number TEXT NOT NULL,
                description TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE cost_item_codes (
                id INTEGER PRIMARY KEY,
                project_number TEXT NOT NULL,
                cost_component_id INTEGER,
                code TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                name TEXT NOT NULL,
                source TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE package_cost_nodes (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES package_cost_nodes(id) ON DELETE CASCADE,
                code VARCHAR(30) NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                is_item BOOLEAN NOT NULL DEFAULT 0,
                cc_code VARCHAR(3),
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
        session.execute(text("INSERT INTO packages (id, package_number) VALUES (1, 'PKG')"))
        session.execute(text("""
            INSERT INTO cost_components (id, project_number, description)
            VALUES (10, '5009', 'Test Cost Component')
        """))
        session.execute(text("""
            INSERT INTO cost_item_codes (
                id, project_number, cost_component_id, code, sequence, name, source
            ) VALUES (20, '5009', 10, '201.01.01', 1, 'Supply', 'library')
        """))
        session.execute(text("""
            INSERT INTO package_cost_nodes (
                id, package_id, parent_id, code, description, is_item, display_order
            ) VALUES (100, 1, NULL, '1', 'Test Cost Component', 0, 0)
        """))
        session.execute(text("""
            INSERT INTO package_cost_nodes (
                id, package_id, parent_id, code, description, is_item, display_order
            ) VALUES (101, 1, 100, '201.01.01', 'Supply', 0, 0)
        """))
        session.execute(text("""
            INSERT INTO package_cost_nodes (
                id, package_id, parent_id, code, description, is_item, cc_code,
                baseline_amount, display_order
            ) VALUES (102, 1, 101, '201.01.01', 'Pump supply', 1, '201', 123, 0)
        """))
        session.commit()

        repair_auto_cbs_cost_node_hierarchy(session)

        line = session.execute(text("""
            SELECT parent_id, code, description, cc_code, baseline_amount
            FROM package_cost_nodes
            WHERE id = 102
        """)).mappings().one()
        assert line["parent_id"] is None
        assert line["code"] == "201.01.01"
        assert line["description"] == "Pump supply"
        assert line["cc_code"] == "201"
        assert line["baseline_amount"] == 123

        remaining_group_count = session.execute(text("""
            SELECT COUNT(*)
            FROM package_cost_nodes
            WHERE id IN (100, 101)
        """)).scalar_one()
        assert remaining_group_count == 0


def test_ensure_package_cost_sheets_creates_original_and_assigns_legacy_nodes():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with Session(engine) as session:
        session.execute(text("PRAGMA foreign_keys=OFF"))
        session.execute(text("""
            CREATE TABLE packages (
                id INTEGER PRIMARY KEY,
                package_number TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE package_cost_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL,
                sheet_number VARCHAR(30) NOT NULL,
                title TEXT NOT NULL,
                sheet_type VARCHAR(20) NOT NULL DEFAULT 'Original',
                status VARCHAR(30) NOT NULL DEFAULT 'Draft',
                description TEXT NOT NULL DEFAULT '',
                display_order INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(package_id, sheet_number)
            )
        """))
        session.execute(text("""
            CREATE TABLE package_cost_nodes (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL,
                cost_sheet_id INTEGER,
                parent_id INTEGER,
                code VARCHAR(30) NOT NULL DEFAULT '',
                description TEXT NOT NULL,
                is_item BOOLEAN NOT NULL DEFAULT 0,
                cc_code VARCHAR(3),
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
        session.execute(text("INSERT INTO packages (id, package_number) VALUES (1, 'PKG')"))
        session.execute(text("""
            INSERT INTO package_cost_sheets (
                package_id, sheet_number, title, sheet_type, status, description, display_order
            )
            VALUES (1, 'ORIGINAL', 'Original Cost Sheet', 'Original', 'Draft', '', 0)
        """))
        session.execute(text("""
            INSERT INTO package_cost_nodes (id, package_id, description, is_item)
            VALUES (10, 1, 'Legacy line', 1)
        """))
        session.commit()

        ensure_package_cost_sheets(session)

        sheet = session.execute(text("""
            SELECT id, sheet_number, title, sheet_type
            FROM package_cost_sheets
            WHERE package_id = 1
        """)).mappings().one()
        assert sheet["sheet_number"] == "ORIGINAL"
        assert sheet["title"] == "Package Base Cost"
        assert sheet["sheet_type"] == "Working Estimate"

        node_sheet_id = session.execute(text("""
            SELECT cost_sheet_id
            FROM package_cost_nodes
            WHERE id = 10
        """)).scalar_one()
        assert node_sheet_id == sheet["id"]

        repair_package_cost_nodes_workstream_fk(session)

        columns = [row[1] for row in session.execute(text("PRAGMA table_info(package_cost_nodes)")).fetchall()]
        foreign_tables = [row[2] for row in session.execute(text("PRAGMA foreign_key_list(package_cost_nodes)")).fetchall()]
        assert "workstream_id" not in columns
        assert "workstreams" not in foreign_tables

        session.execute(text("""
            INSERT INTO package_cost_nodes (package_id, code, description, is_item)
            VALUES (1, '02', 'New Group', 0)
        """))
        session.commit()
