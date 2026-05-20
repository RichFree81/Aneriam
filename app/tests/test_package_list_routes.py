from __future__ import annotations

import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from costcontrol.app import app
from costcontrol.database import Base, get_db
from costcontrol.models import (
    CostComponent,
    CostItemCode,
    Package,
    PackageCostNode,
    PackageCostSheet,
    PORtoLink,
    Project,
    ProjectScopeItem,
    PurchaseOrderLine,
    RTO,
)
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


def test_package_cost_sheet_edit_drawer_deletes_working_sheet_and_baseline():
    client, session, package_id = _client_with_package()
    try:
        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert "sheetDeleteForm" in response.text
        assert "/cost/delete-sheet/" in response.text
        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-sheet",
            data={"title": "Estimate Costing 001", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        working_sheet = session.query(PackageCostSheet).filter_by(package_id=package_id, sheet_type="Working Estimate").one()
        node = PackageCostNode(
            package_id=package_id,
            cost_sheet_id=working_sheet.id,
            code="1",
            description="Temporary worksheet row",
            is_item=False,
            display_order=0,
        )
        session.add(node)
        session.commit()

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/delete-sheet/{working_sheet.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(PackageCostNode, node.id) is None
        assert session.query(PackageCostSheet).filter_by(package_id=package_id).count() == 0

        baseline = PackageCostSheet(
            package_id=package_id,
            sheet_number="1",
            title="Baseline 1 - Feasibility",
            sheet_type="Baseline",
            status="Approved",
            description="Admin removable baseline",
            display_order=1,
        )
        session.add(baseline)
        session.flush()
        baseline_node = PackageCostNode(
            package_id=package_id,
            cost_sheet_id=baseline.id,
            code="1",
            description="Baseline worksheet row",
            is_item=False,
            display_order=0,
        )
        session.add(baseline_node)
        session.commit()

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/delete-sheet/{baseline.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(PackageCostSheet, baseline.id) is None
        assert session.get(PackageCostNode, baseline_node.id) is None

        award_baseline = PackageCostSheet(
            package_id=package_id,
            sheet_number="1",
            title="Awarded Baseline",
            sheet_type="Baseline",
            status="Awarded",
            description="Contractual award reference",
            display_order=-100,
        )
        session.add(award_baseline)
        session.commit()
        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/delete-sheet/{award_baseline.id}",
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert session.get(PackageCostSheet, award_baseline.id) is not None
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_package_cost_tab_uses_hierarchical_actions_and_table():
    client, session, package_id = _client_with_package()
    try:
        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert session.query(PackageCostSheet).filter_by(package_id=package_id).count() == 0
        assert "Add Estimate Costing" in response.text
        assert '<div class="summary-cards package-kpi-cards">' not in response.text
        assert "No active baseline" not in response.text
        assert "Package Base Cost" not in response.text

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-sheet",
            data={"title": "Estimate Costing 001", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        original_sheet = session.query(PackageCostSheet).filter_by(package_id=package_id, sheet_type="Working Estimate").one()
        level2 = PackageCostNode(
            package_id=package_id,
            cost_sheet_id=original_sheet.id,
            code="01",
            description="Earthworks",
            is_item=False,
            display_order=0,
        )
        session.add(level2)
        session.flush()
        item = PackageCostNode(
            package_id=package_id,
            cost_sheet_id=original_sheet.id,
            parent_id=level2.id,
            code="01.01",
            description="Bulk excavation line",
            is_item=True,
            cc_code="205",
            pre_award_amount=1200,
            contract_amount=1300,
            display_order=0,
        )
        session.add(item)
        session.commit()

        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        session.refresh(level2)
        assert level2.cost_sheet_id == original_sheet.id
        assert original_sheet.status == "In Progress"
        assert "Estimate Costing 001" in response.text
        assert "Add Estimate Costing" in response.text
        assert '<div class="summary-cards package-kpi-cards">' not in response.text
        assert "No active baseline" not in response.text
        assert 'id="costSheetGrid"' in response.text
        assert 'id="costNodeGrid"' not in response.text
        assert "Back to Cost Sheets" not in response.text
        assert "Add Cost Grouping" not in response.text
        assert "Add Cost Line" not in response.text
        assert f"/cost?sheet_id={original_sheet.id}" in response.text
        start = response.text.index("const COST_SHEET_ROWS = ") + len("const COST_SHEET_ROWS = ")
        end = response.text.index(";\n  const ACTIVE_COST_SHEET_LOCKED", start)
        sheet_data = json.loads(response.text[start:end])
        assert sheet_data[0]["sheet_number"] == "1"
        assert sheet_data[0]["title"] == "Estimate Costing 001"
        assert sheet_data[0]["sheet_type"] == "Working Estimate"
        assert sheet_data[0]["status"] == "In Progress"
        assert sheet_data[0]["pre_award"] == 1200
        assert "Created by" in response.text
        assert "Reviewed by" in response.text
        assert "sheetEditDrawer" in response.text
        assert "rowClick" not in response.text

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/update-sheet/{original_sheet.id}",
            data={
                "title": "Estimate Costing 001 - reviewed",
                "status": "In Review",
                "created_by": "Estimator",
                "reviewed_by": "PM",
                "approved_by": "Sponsor",
                "description": "Updated basis note",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        session.refresh(original_sheet)
        assert original_sheet.sheet_number == "1"
        assert original_sheet.title == "Estimate Costing 001 - reviewed"
        assert original_sheet.created_by == "Estimator"
        assert original_sheet.reviewed_by == "PM"
        assert original_sheet.approved_by == "Sponsor"
        assert original_sheet.description == "Updated basis note"
        original_sheet.title = "Estimate Costing 001"
        original_sheet.created_by = ""
        original_sheet.reviewed_by = ""
        original_sheet.approved_by = ""
        original_sheet.description = ""
        session.commit()

        response = client.get(f"/project/5006/packages/5006-PKG-001/cost?sheet_id={original_sheet.id}")
        assert response.status_code == 200
        assert 'id="costNodeGrid"' in response.text
        assert 'id="costSheetGrid"' not in response.text
        assert "Back to Cost Sheets" in response.text
        assert "Create Baseline" in response.text
        assert f'name="sheet_id" value="{original_sheet.id}"' in response.text
        assert "Add Cost Grouping" in response.text
        assert "Add Cost Line" in response.text
        assert "Related Control Account" in response.text
        assert "Related Cost Item Account" in response.text
        assert "title: 'Related Control Account'" not in response.text
        assert "Worksheet Grouping" in response.text
        assert '<option value="205">205 - Structures</option>' in response.text
        assert '<option value="205">205 - 205 - Structures</option>' not in response.text
        assert "Related Cost Component" in response.text
        assert "Cost Item Account" in response.text
        assert "Cost Item Account (CBS Level 3)" not in response.text
        assert "Cost Category (CBS Level 1)" not in response.text
        assert "CBS cost item code" not in response.text
        assert "Cost line description" in response.text
        assert "Standard library" in response.text
        assert "Custom account" in response.text
        assert "Add Cost Item Account" in response.text
        assert "Add Account" in response.text
        assert "Use Account" not in response.text
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
        end = response.text.index(";\n  const COST_SHEET_ROWS", start)
        tree_data = json.loads(response.text[start:end])
        assert tree_data[0]["type"] == "Cost Grouping"
        leaf = tree_data[0]["_children"][0]
        assert leaf["type"] == "Cost Line"
        assert leaf["description"] == "Bulk excavation line"
        assert leaf["cost_item_account"] == "01.01"
        assert "_children" not in leaf
        assert "Cost Item Lines" not in response.text
        assert "Create Cost Item Code" not in response.text
        assert "Add Cost Item Line" not in response.text
        assert '<span class="chip">{{ package.package_source }}</span>' not in response.text

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-sheet",
            data={
                "title": "Variation 001 - scope change",
                "description": "Additional civils",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        variation_sheet = session.query(PackageCostSheet).filter_by(
            package_id=package_id,
            sheet_type="Working Estimate",
            title="Variation 001 - scope change",
        ).one()
        assert variation_sheet.sheet_number == "2"
        assert response.headers["location"].endswith(f"/cost?sheet_id={variation_sheet.id}")

        response = client.get(f"/project/5006/packages/5006-PKG-001/cost?sheet_id={variation_sheet.id}")
        assert response.status_code == 200
        assert "Variation 001 - scope change" in response.text
        start = response.text.index("const COST_NODE_ROWS = ") + len("const COST_NODE_ROWS = ")
        end = response.text.index(";\n  const COST_SHEET_ROWS", start)
        assert json.loads(response.text[start:end]) == []

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
                "description": "Bulk earthworks",
                "cc_code": "206",
                "pre_award_amount": "1500",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        session.refresh(item)
        assert item.code == "01.01"
        assert item.description == "Bulk earthworks"
        assert item.cc_code == "206"
        assert item.pre_award_amount == 1500
        assert item.contract_amount == 1300

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-section",
            data={
                "sheet_id": str(variation_sheet.id),
                "code": "SHOULD-NOT-BE-USED",
                "description": "Steelwork",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        new_grouping = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=None,
            cost_sheet_id=variation_sheet.id,
            description="Steelwork",
            is_item=False,
        ).one()
        assert new_grouping.code == "1"

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
                "cost_grouping_id": str(level2.id),
                "sheet_id": str(original_sheet.id),
                "cc_code": "205",
                "cost_item_code_id": str(existing_code.id),
                "account_mode": "existing",
                "description": "Install anchor bolts",
                "pre_award_amount": "2100",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        component_line = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=level2.id,
            description="Install anchor bolts",
            is_item=True,
        ).one()
        assert component_line.code == "205.01.01"
        assert component_line.cc_code == "205"
        assert component_line.pre_award_amount == 2100
        assert session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=None,
            description="Shell replacement",
            is_item=False,
        ).count() == 0
        assert session.query(PackageCostNode).filter_by(
            package_id=package_id,
            parent_id=level2.id,
            code="205.01.01",
            description="Installation",
            is_item=False,
        ).count() == 0

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "cost_component_id": str(component.id),
                "sheet_id": str(variation_sheet.id),
                "cc_code": "205",
                "cost_item_code_id": "__add__",
                "account_mode": "custom",
                "custom_account_name": "Refractory works",
                "description": "Install refractory",
                "pre_award_amount": "700",
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
        custom_line = session.query(PackageCostNode).filter_by(
            package_id=package_id,
            cost_sheet_id=variation_sheet.id,
            parent_id=None,
            description="Install refractory",
            is_item=True,
        ).one()
        assert custom_line.code == "205.01.02"
        assert custom_line.cc_code == "205"

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/add-item",
            data={
                "cost_component_id": str(component.id),
                "cc_code": "206",
                "cost_item_code_id": str(existing_code.id),
                "account_mode": "existing",
                "description": "Mismatched control account",
                "pre_award_amount": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/delete-node/{item.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(PackageCostNode, item.id) is None

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/create-baseline",
            data={
                "sheet_id": str(original_sheet.id),
                "title": "Baseline 1 - Feasibility",
                "description": "Feasibility estimate approval",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        baseline_sheet = session.query(PackageCostSheet).filter_by(
            package_id=package_id,
            sheet_type="Baseline",
            title="Baseline 1 - Feasibility",
        ).one()
        assert baseline_sheet.sheet_number == "2"
        assert baseline_sheet.status == "Approved"
        assert baseline_sheet.source_sheet_id is None
        assert "Baselined from 1 - Estimate Costing 001" in baseline_sheet.description
        assert baseline_sheet.locked_at is not None
        assert response.headers["location"].endswith(f"/cost?sheet_id={baseline_sheet.id}")
        assert session.get(PackageCostSheet, original_sheet.id) is None
        baseline_nodes = session.query(PackageCostNode).filter_by(package_id=package_id, cost_sheet_id=baseline_sheet.id).all()
        assert len(baseline_nodes) >= 2

        response = client.get(f"/project/5006/packages/5006-PKG-001/cost?sheet_id={baseline_sheet.id}")
        assert response.status_code == 200
        assert "This cost sheet is approved and read-only." in response.text
        assert '<div class="summary-cards package-kpi-cards">' not in response.text
        assert "Active baseline: Sheet 2" not in response.text
        assert "R 2,100.00" in response.text
        assert "Add Cost Grouping" not in response.text
        assert "Add Cost Line" not in response.text
        assert "Create Baseline" not in response.text
        assert "Add Estimate Costing" not in response.text
        assert "const ACTIVE_COST_SHEET_LOCKED = true" in response.text

        response = client.post(
            f"/project/5006/packages/5006-PKG-001/cost/update-section/{baseline_nodes[0].id}",
            data={"description": "Should not edit"},
            follow_redirects=False,
        )
        assert response.status_code == 400

        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert "Create Working Estimate" in response.text
        assert "Add Estimate Costing" not in response.text
        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/create-working-estimate",
            data={"baseline_sheet_id": str(baseline_sheet.id)},
            follow_redirects=False,
        )
        assert response.status_code == 303
        working_sheet = session.query(PackageCostSheet).filter_by(package_id=package_id, sheet_type="Working Estimate").one()
        assert working_sheet.source_sheet_id == baseline_sheet.id
        assert working_sheet.status == "In Progress"
        package = session.get(Package, package_id)
        package.package_source = "Internal"
        package.is_external = False
        session.commit()

        response = client.get("/project/5006/packages")
        assert response.status_code == 200
        assert "packageAwardButton" in response.text
        assert "Award Package and Issue RTO" in response.text
        assert "baseline_lines" in response.text
        assert "5006-PKG-001-RTO.01" in response.text

        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert "Award Package" not in response.text

        response = client.post(
            f"/project/5006/packages/award/{package_id}",
            data={"company_name": "ACME Contractors"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        rto = session.query(RTO).filter_by(package_number="5006-PKG-001").one()
        assert rto.rto_number == "5006-PKG-001-RTO.01"
        assert rto.total_amount == 2100
        assert rto.vendor_name == "ACME Contractors"
        package = session.get(Package, package_id)
        assert package.is_contracted is True
        assert package.awarded_vendor_name == "ACME Contractors"
        assert package.awarded_amount == 2100
        assert session.get(PackageCostSheet, working_sheet.id) is None
        session.refresh(baseline_sheet)
        assert baseline_sheet.status == "Awarded"

        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert "View RTO" in response.text
        assert "Awaiting PO" not in response.text
        assert "/packages/5006-PKG-001/rto" in response.text

        response = client.get("/project/5006/commitments/request-to-order")
        assert response.status_code == 200
        assert "5006-PKG-001-RTO.01" in response.text
        assert "ACME Contractors" in response.text

        session.add(PurchaseOrderLine(
            po_number="PO-001",
            project_number="5006",
            memo_main="Original package",
            memo="Original package",
            amount=2100,
            actual_amount=0,
            remaining=2100,
            vendor="ACME Contractors",
            date=date(2026, 5, 20),
            status="Pending Receipt",
        ))
        rto.status = "Approved"
        session.commit()

        response = client.post(
            "/project/5006/commitments/purchase-orders/PO-001/link",
            data={"rto_id": str(rto.id)},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.query(PORtoLink).filter_by(po_number="PO-001", rto_id=rto.id).one().is_original is True
        session.refresh(rto)
        assert rto.status == "Issued for PO"
        response = client.get("/project/5006/packages/5006-PKG-001/cost")
        assert response.status_code == 200
        assert "Committed" in response.text
        assert "Committed Cost" not in response.text

        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/create-baseline",
            data={"sheet_id": str(baseline_sheet.id), "title": "Baseline after award"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        response = client.post(
            "/project/5006/packages/5006-PKG-001/cost/create-working-estimate",
            data={"baseline_sheet_id": str(baseline_sheet.id)},
            follow_redirects=False,
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
        session.close()
