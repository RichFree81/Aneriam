from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from costcontrol.startup import repair_package_cost_nodes_workstream_fk


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
