from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from costcontrol.cbs import (
    award_package,
    create_cost_item_line,
    funding_identity,
    next_cost_item_code,
    next_deliverable_code,
    normalise_cbs_code,
    plan_package,
    validate_package_award,
)
from costcontrol.database import Base
from costcontrol.models import (
    BudgetReserveSubAccount,
    CostItemCode,
    Deliverable,
    DeliverablePlantArea,
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
    unallocated = session.get(BudgetReserveSubAccount, "101.01")
    unallocated.balance = 1_000_000
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


def _deliverable_with_code(db, *, complete_metadata: bool = True) -> tuple[Deliverable, CostItemCode]:
    scope = ProjectScopeItem(
        project_number="5006",
        description="Maintenance Workshop Addition",
        work_type_code="TieIn" if complete_metadata else None,
        modifies_ppe_reference="F3 workshop PPE" if complete_metadata else None,
    )
    db.add(scope)
    db.flush()
    deliverable = Deliverable(
        project_number="5006",
        scope_item_id=scope.id,
        description="Maintenance Workshop",
        commodity_code="205",
        cbs_l2_code="205.01",
        sequence=1,
    )
    db.add(deliverable)
    db.flush()
    if complete_metadata:
        area = PlantArea(code="3101", name="Furnace 3 Proper", level=3, is_ppe=True)
        db.add(area)
        db.flush()
        db.add(DeliverablePlantArea(deliverable_id=deliverable.id, plant_area_id=area.id))
    code = CostItemCode(
        project_number="5006",
        deliverable_id=deliverable.id,
        code="205.01.01",
        sequence=1,
        name="Civil works",
        source="library",
    )
    db.add(code)
    db.commit()
    return deliverable, code


def test_normalise_existing_netsuite_l3_widths():
    assert normalise_cbs_code("205.01.1 - Civil works") == "205.01.01"
    assert normalise_cbs_code("102.01.10 - Regulatory Compliance and Permits") == "102.01.10"
    assert normalise_cbs_code("205.01") == "205.01"


def test_l2_and_l3_sequences_are_zero_padded_and_not_reused(db):
    assert next_deliverable_code(db, "5006", "205") == ("205.01", 1)
    deliverable, _ = _deliverable_with_code(db)
    assert next_deliverable_code(db, "5006", "205") == ("205.02", 2)
    assert next_cost_item_code(db, "5006", deliverable=deliverable) == ("205.01.02", 2, "205.01")


def test_provisional_sum_supersedes_only_same_package_cost_item_intersection(db):
    pkg = _package(db)
    _, code = _deliverable_with_code(db)
    ps = create_cost_item_line(db, pkg, code, "Civil works PS", 1000, True)
    with pytest.raises(ValueError):
        create_cost_item_line(db, pkg, code, "Civil works firm", 900, False)
    firm = create_cost_item_line(db, pkg, code, "Civil works firm", 900, False, confirm_supersede=True)
    db.commit()
    assert ps.superseded is True
    assert ps.superseded_by_id == firm.id


def test_award_validation_blocks_missing_pbs_capitalisation_metadata(db):
    pkg = _package(db)
    _, code = _deliverable_with_code(db, complete_metadata=False)
    create_cost_item_line(db, pkg, code, "Civil works", 1000, False)
    errors = validate_package_award(db, pkg)
    assert any("Plant Area is required" in error for error in errors)
    assert any("Work Type is required" in error for error in errors)


def test_award_moves_reserve_and_commits_deliverable(db):
    pkg = _package(db)
    deliverable, code = _deliverable_with_code(db)
    plan_package(db, pkg, 1200)
    create_cost_item_line(db, pkg, code, "Civil works", 1000, False)
    award_package(db, pkg)
    db.commit()
    assert pkg.is_contracted is True
    assert pkg.awarded_amount == 1000
    assert deliverable.state == "Committed"
    assert db.get(BudgetReserveSubAccount, "101.02").balance == 0
    assert db.get(BudgetReserveSubAccount, "101.01").balance == 999_000
    assert funding_identity(db) == 1_000_000
