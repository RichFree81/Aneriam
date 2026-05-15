from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from costcontrol.app import app
from costcontrol.database import Base, get_db
from costcontrol.models import Package, Project
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
