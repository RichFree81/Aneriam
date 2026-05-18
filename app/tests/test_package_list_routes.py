from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from costcontrol.app import app
from costcontrol.database import Base, get_db
from costcontrol.models import CostComponent, CostItemCode, Package, PackageCostNode, Project, ProjectScopeItem
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
        level2 = PackageCostNode(
            package_id=package_id,
            code="01",
            description="Earthworks",
            is_item=False,
            display_order=0,
        )
        session.add(level2)
        session.flush()
        account = PackageCostNode(
            package_id=package_id,
            parent_id=level2.id,
            code="",
            description="Bulk earthworks",
            is_item=False,
            display_order=0,
        )
        session.add(account)
        session.flush()
        item = PackageCostNode(
            package_id=package_id,
            parent_id=account.id,
            code="01.01",
            description="Bulk excavation line",
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
        assert "Add Cost Grouping" in response.text
        assert "Add Cost Line" in response.text
        assert "Related Cost Component" in response.text
        assert "Cost Item Account" in response.text
        assert "Cost Item Account (CBS Level 3)" not in response.text
        assert "Cost Category (CBS Level 1)" in response.text
        assert "CBS cost item code" in response.text
        assert "Cost line description" in response.text
        assert "Standard library" in response.text
        assert "Custom account" in response.text
        assert "Add Cost Item Account" in response.text
        assert "+ Add new Cost Item Account" in response.text
        assert "COST_COMPONENT_OPTIONS" in response.text
        assert "COST_ITEM_CODE_OPTIONS" in response.text
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
        end = response.text.index(";\n  const COST_COMPONENT_OPTIONS", start)
        tree_data = json.loads(response.text[start:end])
        assert tree_data[0]["type"] == "Cost Grouping"
        account_row = tree_data[0]["_children"][0]
        assert account_row["type"] == "Cost Item Account"
        leaf = account_row["_children"][0]
        assert leaf["type"] == "Cost Line"
        assert "_children" not in leaf
        assert "Cost Item Lines" not in response.text
        assert "Create Cost Item Code" not in response.text
        assert "Add Cost Item Line" not in response.text
        assert '<span class="chip">{{ package.package_source }}</span>' not in response.text

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/update-section/{level2.id}",
            data={"code": "02", "description": "Civils"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        session.refresh(level2)
        assert level2.code == "01"
        assert level2.description == "Civils"

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
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "cost_grouping_id": str(level2.id),
                "account_mode": "library",
                "library_account_name": "Installation",
                "description": "Install anchor bolts",
                "baseline_amount": "900",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        new_account = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=level2.id,
            description="Installation",
            is_item=False,
        ).one()
        assert new_account.code == "01.2"
        new_line = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=new_account.id,
            description="Install anchor bolts",
            is_item=True,
        ).one()
        assert new_line.code == ""
        assert new_line.baseline_amount == 900

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-section",
            data={
                "code": "SHOULD-NOT-BE-USED",
                "description": "Steelwork",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        new_grouping = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=None,
            description="Steelwork",
            is_item=False,
        ).one()
        assert new_grouping.code == "2"

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "cost_account_id": str(account.id),
                "description": "Cart spoil",
                "baseline_amount": "300",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.query(PackageCostNode).filter_by(parent_id=account.id, description="Cart spoil").one().is_item

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "parent_id": str(level2.id),
                "description": "Invalid direct line",
                "baseline_amount": "100",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

        scope = ProjectScopeItem(project_number="5006", description="Furnace shell")
        session.add(scope)
        session.flush()
        component = CostComponent(
            project_number="5006",
            scope_item_id=scope.id,
            description="Shell replacement",
            commodity_code="205",
            cbs_l2_code="205.01",
            sequence=1,
        )
        session.add(component)
        session.flush()
        existing_code = CostItemCode(
            project_number="5006",
            cost_component_id=component.id,
            code="205.01.01",
            sequence=1,
            name="Installation",
            source="library",
        )
        session.add(existing_code)
        session.commit()

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "cost_component_id": str(component.id),
                "cost_item_code_id": str(existing_code.id),
                "account_mode": "existing",
                "description": "Install furnace shell",
                "baseline_amount": "2100",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        component_group = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=None,
            description="Shell replacement",
            is_item=False,
        ).one()
        account_node = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=component_group.id,
            code="205.01.01",
            description="Installation",
            is_item=False,
        ).one()
        component_line = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=account_node.id,
            description="Install furnace shell",
            is_item=True,
        ).one()
        assert component_line.code == "205.01.01"
        assert component_line.cc_code == "205"
        assert component_line.baseline_amount == 2100

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "cost_component_id": str(component.id),
                "cost_item_code_id": "__add__",
                "account_mode": "custom",
                "custom_account_name": "Refractory works",
                "description": "Install refractory",
                "baseline_amount": "700",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        custom_code = session.query(CostItemCode).filter_by(
            project_number="5006",
            cost_component_id=component.id,
            name="Refractory works",
            source="custom",
        ).one()
        assert custom_code.code == "205.01.02"

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/delete-node/{item.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(PackageCostNode, item.id) is None
    finally:
        app.dependency_overrides.clear()
        session.close()
