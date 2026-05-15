from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from costcontrol.app import app
from costcontrol.database import Base, get_db
from costcontrol.models import Package, PackageCostNode, Project
from costcontrol.seed import seed_control_accounts, seed_cost_control_master_data


def _client_with_package():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_control_accounts(session)
    seed_cost_control_master_data(session)
    session.add(Project(project_number="5006", project_name="5006 Furnace 3", is_active=True, current_budget=100000))
    package = Package(
        package_number="5006-PKG-001",
        project_number="5006",
        description="Original package",
        package_type="Supply Package",
        package_stage="Definition",
        package_source="External",
        is_external=True,
        pricing_basis="LS",
        planned_value=25000,
        display_order=1,
    )
    session.add(package)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session, package.id


def test_package_list_uses_edit_drawer_not_inline_metadata_form():
    client, session, _ = _client_with_package()
    try:
        response = client.get("/project/5006/packages")
        assert response.status_code == 200
        assert "packageEditDrawer" in response.text
        assert "package-edit-btn" in response.text
        assert "Cost status" in response.text
        assert "Amount" in response.text
        assert "Provisional Allocation" in response.text
        assert "Planned value" not in response.text
        assert "Add Package" in response.text
        assert "/project/5006/packages/add" in response.text
        assert "Import Data" not in response.text
        assert "Refresh Package Register" not in response.text
        assert "project/5006/packages/update/" in response.text
        assert "project/5006/packages/delete/" in response.text
        assert "Package Metadata" not in response.text
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_package_list_update_route_updates_package_metadata():
    client, session, package_id = _client_with_package()
    try:
        response = client.post(
            f"/project/5006/packages/update/{package_id}",
            data={
                "description": "Updated package",
                "package_type": "Construction Package Labour & Materials",
                "package_source": "Internal",
                "pricing_basis": "BOQ",
                "package_stage": "Procurement",
                "planned_value": "30000.50",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        package = session.get(Package, package_id)
        assert package.description == "Updated package"
        assert package.package_type == "Construction Package Labour & Materials"
        assert package.package_source == "Internal"
        assert package.is_external is False
        assert package.pricing_basis == "BOQ"
        assert package.package_stage == "Procurement"
        assert package.planned_value == 30000.50
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_package_list_add_route_creates_package():
    client, session, _ = _client_with_package()
    try:
        response = client.post(
            "/project/5006/packages/add",
            data={
                "package_number": "5006-PKG-002",
                "description": "New package",
                "package_type": "Services Package",
                "package_source": "Internal",
                "pricing_basis": "TM",
                "package_stage": "Definition",
                "planned_value": "1200.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        package = session.query(Package).filter_by(package_number="5006-PKG-002").one()
        assert package.project_number == "5006"
        assert package.description == "New package"
        assert package.package_type == "Services Package"
        assert package.package_source == "Internal"
        assert package.is_external is False
        assert package.pricing_basis == "TM"
        assert package.package_stage == "Definition"
        assert package.planned_value == 1200.00
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_package_list_delete_route_deletes_package():
    client, session, package_id = _client_with_package()
    try:
        response = client.post(
            f"/project/5006/packages/delete/{package_id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(Package, package_id) is None
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_package_cost_tab_uses_hierarchical_actions_and_table():
    client, session, package_id = _client_with_package()
    try:
        group = PackageCostNode(
            package_id=package_id,
            code="01",
            description="Earthworks",
            is_item=False,
            display_order=0,
        )
        session.add(group)
        session.flush()
        item = PackageCostNode(
            package_id=package_id,
            parent_id=group.id,
            code="01.01",
            description="Bulk excavation",
            is_item=True,
            cc_code="205",
            baseline_amount=1000,
            pre_award_amount=1200,
            contract_amount=1300,
            display_order=0,
        )
        session.add(item)
        session.commit()

        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert "Add Group" in response.text
        assert "Add Cost Item" in response.text
        assert "COST_NODE_ROWS" in response.text
        assert "dataTree: true" in response.text
        assert "Grand Total" in response.text
        assert "costEditDrawer" in response.text
        assert "cost-edit-btn" in response.text
        assert "/cost/update-section/" in response.text
        assert "/cost/update-item/" in response.text
        assert "/cost/delete-node/" in response.text
        assert "Earthworks" in response.text
        assert "Bulk excavation" in response.text
        start = response.text.index("const COST_NODE_ROWS = ") + len("const COST_NODE_ROWS = ")
        end = response.text.index(";\n\n  function escapeHtml", start)
        tree_data = json.loads(response.text[start:end])
        leaf = tree_data[0]["_children"][0]
        assert leaf["type"] == "Cost Item"
        assert "_children" not in leaf
        assert "Cost Item Lines" not in response.text
        assert "Create Cost Item Code" not in response.text
        assert "Add Cost Item Line" not in response.text
        assert '<span class="chip">{{ package.package_source }}</span>' not in response.text

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/update-section/{group.id}",
            data={"code": "02", "description": "Civils"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        session.refresh(group)
        assert group.code == "02"
        assert group.description == "Civils"

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/update-item/{item.id}",
            data={
                "code": "02.01",
                "description": "Bulk earthworks",
                "cc_code": "206",
                "baseline_amount": "1400",
                "pre_award_amount": "1500",
                "contract_amount": "1600",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        session.refresh(item)
        assert item.code == "02.01"
        assert item.description == "Bulk earthworks"
        assert item.cc_code == "206"
        assert item.baseline_amount == 1400
        assert item.pre_award_amount == 1500
        assert item.contract_amount == 1600

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/delete-node/{item.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(PackageCostNode, item.id) is None
    finally:
        app.dependency_overrides.clear()
        session.close()
