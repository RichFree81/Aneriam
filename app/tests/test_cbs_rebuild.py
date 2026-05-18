from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from costcontrol.cbs import (
    award_package,
    create_cost_item_line,
    funding_identity,
    next_cost_item_code,
    next_cost_component_code,
    normalise_cbs_code,
    plan_package,
    validate_package_award,
)
from costcontrol.database import Base
from costcontrol.models import (
    BudgetReserveBalance,
    CostItemCode,
    CostComponent,
    CostComponentPlantArea,
    Package,
    PlantArea,
    Project,
    ProjectScopeItem,
)
from costcontrol.seed import seed_control_accounts, seed_cost_control_master_data


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_control_accounts(session)
    seed_cost_control_master_data(session)
    session.add(Project(project_number="5006", project_name="5006 Furnace 3", is_active=True))
    session.add(BudgetReserveBalance(project_number="5006", reserve_code="101.01", balance=1_000_000))
    session.add(BudgetReserveBalance(project_number="5006", reserve_code="101.02", balance=0))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _package(db) -> Package:
    pkg = Package(
        package_number="5006-PKG-001",
        project_number="5006",
        description="Construction package",
        package_type="Construction Package Labour & Materials",
        package_stage="Procurement",
        package_source="External",
        is_external=True,
        pricing_basis="BOQ",
    )
    db.add(pkg)
    db.commit()
    return pkg


def _cost_component_with_code(db, *, complete_metadata: bool = True) -> tuple[CostComponent, CostItemCode]:
    scope = ProjectScopeItem(
        project_number="5006",
        description="Maintenance Workshop Addition",
        work_type_code="TieIn" if complete_metadata else None,
        modifies_ppe_reference="F3 workshop PPE" if complete_metadata else None,
    )
    db.add(scope)
    db.flush()
    cost_component = CostComponent(
        project_number="5006",
        scope_item_id=scope.id,
        description="Maintenance Workshop",
        commodity_code="205",
        cbs_l2_code="205.01",
        sequence=1,
    )
    db.add(cost_component)
    db.flush()
    if complete_metadata:
        area = db.query(PlantArea).filter_by(code="3101").one()
        db.add(CostComponentPlantArea(cost_component_id=cost_component.id, plant_area_id=area.id))
    code = CostItemCode(
        project_number="5006",
        cost_component_id=cost_component.id,
        code="205.01.01",
        sequence=1,
        name="Civil works",
        source="library",
    )
    db.add(code)
    db.commit()
    return cost_component, code


def test_normalise_existing_netsuite_l3_widths():
    assert normalise_cbs_code("205.01.1 - Civil works") == "205.01.01"
    assert normalise_cbs_code("102.01.10 - Regulatory Compliance and Permits") == "102.01.10"
    assert normalise_cbs_code("205.01") == "205.01"


def test_l2_and_l3_sequences_are_zero_padded_and_not_reused(db):
    assert next_cost_component_code(db, "5006", "205") == ("205.01", 1)
    cost_component, _ = _cost_component_with_code(db)
    assert next_cost_component_code(db, "5006", "205") == ("205.02", 2)
    assert next_cost_item_code(db, "5006", cost_component=cost_component) == ("205.01.02", 2, "205.01")


def test_provisional_sum_supersedes_only_same_package_cost_item_intersection(db):
    pkg = _package(db)
    _, code = _cost_component_with_code(db)
    ps = create_cost_item_line(db, pkg, code, "Civil works PS", 1000, True)
    with pytest.raises(ValueError):
        create_cost_item_line(db, pkg, code, "Civil works firm", 900, False)
    firm = create_cost_item_line(db, pkg, code, "Civil works firm", 900, False, confirm_supersede=True)
    db.commit()
    assert ps.superseded is True
    assert ps.superseded_by_id == firm.id


def test_award_validation_blocks_missing_pbs_capitalisation_metadata(db):
    pkg = _package(db)
    _, code = _cost_component_with_code(db, complete_metadata=False)
    create_cost_item_line(db, pkg, code, "Civil works", 1000, False)
    errors = validate_package_award(db, pkg)
    assert any("Plant Area is required" in error for error in errors)
    assert any("Work Type is required" in error for error in errors)


def test_award_moves_reserve_and_commits_cost_component(db):
    pkg = _package(db)
    cost_component, code = _cost_component_with_code(db)
    plan_package(db, pkg, 1200)
    create_cost_item_line(db, pkg, code, "Civil works", 1000, False)
    award_package(db, pkg)
    db.commit()
    assert pkg.is_contracted is True
    assert pkg.awarded_amount == 1000
    assert cost_component.state == "Committed"
    balances = {row.reserve_code: row.balance for row in db.query(BudgetReserveBalance).all()}
    assert balances["101.02"] == 0
    assert balances["101.01"] == 999_000
    assert funding_identity(db, "5006") == 1_000_000
