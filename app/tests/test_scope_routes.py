from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from costcontrol.app import app
from costcontrol.database import Base, get_db
from costcontrol.models import (
    CostComponent,
    CostComponentPlantArea,
    PlantArea,
    Project,
    ProjectScopeItem,
)
from costcontrol.seed import seed_control_accounts, seed_cost_control_master_data


def _client_with_db():
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
    session.add(Project(project_number="5006", project_name="5006 Furnace 3", is_active=True))
    area_a = session.query(PlantArea).filter_by(code="3101").one()
    area_b = session.query(PlantArea).filter_by(code="3102").one()
    scope = ProjectScopeItem(
        project_number="5006",
        description="Original scope",
        work_type_code="NewBuild",
        modifies_ppe_reference="Existing PPE",
    )
    session.add(scope)
    session.flush()
    cost_component = CostComponent(
        project_number="5006",
        scope_item_id=scope.id,
        description="Original cost component",
        commodity_code="205",
        cbs_l2_code="205.01",
        sequence=1,
    )
    session.add(cost_component)
    session.flush()
    session.add(CostComponentPlantArea(cost_component_id=cost_component.id, plant_area_id=area_a.id))
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), session, scope.id, cost_component.id, area_b.id


def test_scope_edit_drawer_routes_update_and_delete_records():
    client, session, scope_id, cost_component_id, area_b_id = _client_with_db()
    try:
        response = client.post(
            f"/project/5006/scope/update-item/{scope_id}",
            data={
                "description": "Updated scope",
                "work_type_code": "TieIn",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        scope = session.get(ProjectScopeItem, scope_id)
        assert scope.description == "Updated scope"
        assert scope.work_type_code == "TieIn"
        assert scope.modifies_ppe_reference == "Existing PPE"

        response = client.post(
            f"/project/5006/scope/update-cost-component/{cost_component_id}",
            data={
                "scope_item_id": str(scope_id),
                "description": "Updated cost component",
                "commodity_code": "206",
                "plant_area_id": str(area_b_id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        cost_component = session.get(CostComponent, cost_component_id)
        assert cost_component.description == "Updated cost component"
        assert cost_component.commodity_code == "206"
        assert [link.plant_area_id for link in cost_component.plant_area_links] == [area_b_id]

        response = client.post(
            f"/project/5006/scope/delete-cost-component/{cost_component_id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(CostComponent, cost_component_id) is None

        response = client.post(
            f"/project/5006/scope/delete-item/{scope_id}",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert session.get(ProjectScopeItem, scope_id) is None
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_scope_page_uses_facility_unit_area_hierarchy():
    client, session, _, _, _ = _client_with_db()
    try:
        response = client.get("/project/5006/scope")
        assert response.status_code == 200
        assert "Facility Group" in response.text
        assert "Plant Unit" in response.text
        assert "Area" in response.text
        assert "Scope Items" in response.text
        assert "Cost Components" in response.text
        assert "Unpackaged Components" in response.text
        assert "Incomplete Records" in response.text
        assert '<div class="sc-value">1</div>' in response.text
        assert '<div class="sc-value">0</div>' in response.text
        assert "valueField === 'code' ? item.code : String(item.id)" in response.text
        assert "setAreaOptions(areaSelect, areas, selectedArea, true, 'All Areas', 'code')" in response.text
        assert '<option value="205">205 - Structures</option>' in response.text
        assert '<option value="205">205 - 205 - Structures</option>' not in response.text
        assert "PLANT_AREA_TREE" in response.text
        assert '"plant_unit_code": "3100"' in response.text
        assert '"plant_unit_name": "MK 07 Furnace"' in response.text
        assert "3101 - MK 07 Furnace Proper" in response.text
        assert '"plant_area_codes": ["3101"]' in response.text
    finally:
        app.dependency_overrides.clear()
        session.close()
