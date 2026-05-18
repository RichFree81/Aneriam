"""WBS/PBS/CBS domain helpers for the Cost Control rebuild."""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .models import (
    BudgetReserveBalance,
    BudgetReserveSubAccount,
    CostControlAuditLog,
    CostItemCode,
    Deliverable,
    IndirectL2Account,
    Package,
    PackageCostItem,
    Project,
    ProjectScopeItem,
    PurchaseOrderLine,
    WorkType,
)

DIRECT_COMMODITIES = ("201", "202", "203", "204", "205", "206")
REQUIRES_MODIFIES_PPE = {"TieIn", "Upgrade", "Replacement", "MajorOverhaul"}


def normalise_cbs_code(code: str) -> str:
    """Normalise NetSuite one-digit L3 task codes to the app's two-digit form."""
    match = re.search(r"(?P<l1>\d{3})\.(?P<l2>\d{2,3})(?:\.(?P<l3>\d{1,2}))?", code or "")
    if not match:
        return (code or "").strip()
    l1 = match.group("l1")
    l2 = int(match.group("l2"))
    l3 = match.group("l3")
    if l3 is None:
        return f"{l1}.{l2:02d}"
    return f"{l1}.{l2:02d}.{int(l3):02d}"


def next_deliverable_code(db: Session, project_number: str, commodity_code: str) -> tuple[str, int]:
    seq = (
        db.query(func.max(Deliverable.sequence))
        .filter_by(project_number=project_number, commodity_code=commodity_code)
        .scalar()
        or 0
    ) + 1
    return f"{commodity_code}.{seq:02d}", seq


def next_cost_item_code(
    db: Session,
    project_number: str,
    *,
    deliverable: Deliverable | None = None,
    indirect_l2_code: str | None = None,
) -> tuple[str, int, str]:
    if deliverable is None and not indirect_l2_code:
        raise ValueError("Either deliverable or indirect_l2_code is required")
    if deliverable is not None:
        seq = (
            db.query(func.max(CostItemCode.sequence))
            .filter_by(deliverable_id=deliverable.id)
            .scalar()
            or 0
        ) + 1
        parent_code = deliverable.cbs_l2_code
    else:
        seq = (
            db.query(func.max(CostItemCode.sequence))
            .filter_by(project_number=project_number, indirect_l2_code=indirect_l2_code)
            .scalar()
            or 0
        ) + 1
        parent_code = indirect_l2_code or ""
    return f"{parent_code}.{seq:02d}", seq, parent_code


def scope_item_state(scope_item: ProjectScopeItem) -> str:
    states = [d.state for d in scope_item.deliverables]
    if not states:
        return "Provisional"
    if all(state == "Final" for state in states):
        return "Final"
    if any(state in ("Committed", "Final") for state in states):
        return "Committed"
    return "Provisional"


def write_audit(
    db: Session,
    project_number: str,
    action: str,
    description: str,
    *,
    target_type: str = "",
    target_id: int | None = None,
) -> None:
    db.add(CostControlAuditLog(
        project_number=project_number,
        action=action,
        changed_at=datetime.now(),
        target_type=target_type,
        target_id=target_id,
        description=description,
    ))


def reserve_accounts(db: Session, project_number: str) -> tuple[BudgetReserveBalance, BudgetReserveBalance]:
    if db.get(BudgetReserveSubAccount, "101.01") is None or db.get(BudgetReserveSubAccount, "101.02") is None:
        raise ValueError("Budget reserve subaccounts 101.01 and 101.02 must be seeded")
    rows = {
        row.reserve_code: row
        for row in db.query(BudgetReserveBalance).filter_by(project_number=project_number).all()
    }
    for code in ("101.01", "101.02"):
        if code not in rows:
            opening = 0.0
            if code == "101.01":
                project = db.query(Project).filter_by(project_number=project_number).first()
                opening = float((project.current_budget or project.approved_capex or 0) if project else 0)
            rows[code] = BudgetReserveBalance(project_number=project_number, reserve_code=code, balance=opening)
            db.add(rows[code])
            db.flush()
    unallocated = rows["101.01"]
    provisional = rows["101.02"]
    return unallocated, provisional


def plan_package(db: Session, pkg: Package, planned_value: float) -> None:
    previous = float(pkg.planned_value or 0)
    delta = planned_value - previous
    unallocated, provisional = reserve_accounts(db, pkg.project_number)
    if delta > 0 and float(unallocated.balance or 0) < delta:
        raise ValueError("Provisional allocation exceeds 101.01 Unallocated balance")
    unallocated.balance = float(unallocated.balance or 0) - delta
    provisional.balance = float(provisional.balance or 0) + delta
    pkg.planned_value = planned_value
    write_audit(
        db,
        pkg.project_number,
        "Package Provisional Allocation",
        f"{pkg.package_number} provisional allocation set to {planned_value:.2f}; reserve delta {delta:.2f}",
        target_type="Package",
        target_id=pkg.id,
    )


def active_package_line_items(pkg: Package) -> list[PackageCostItem]:
    return [item for item in pkg.cost_items if not item.superseded]


def validate_package_award(db: Session, pkg: Package) -> list[str]:
    errors: list[str] = []
    deliverable_ids = {
        item.cost_item_code_ref.deliverable_id
        for item in active_package_line_items(pkg)
        if item.cost_item_code_ref.deliverable_id is not None
    }
    if not deliverable_ids:
        return errors
    deliverables = db.query(Deliverable).filter(Deliverable.id.in_(deliverable_ids)).all()
    for deliverable in deliverables:
        if not deliverable.plant_area_links:
            errors.append(f"Deliverable {deliverable.cbs_l2_code} {deliverable.description}: Plant Area is required")
        scope_item = deliverable.scope_item_ref
        if not scope_item.work_type_code:
            errors.append(f"Scope Item {scope_item.description}: Work Type is required")
            continue
        work_type = db.get(WorkType, scope_item.work_type_code)
        requires_modifies = (
            scope_item.work_type_code in REQUIRES_MODIFIES_PPE
            or bool(work_type and work_type.requires_modifies_ppe)
        )
        if requires_modifies and not (scope_item.modifies_ppe_reference or "").strip():
            errors.append(f"Scope Item {scope_item.description}: Modifies PPE reference is required")
    return errors


def award_package(db: Session, pkg: Package) -> None:
    errors = validate_package_award(db, pkg)
    if errors:
        raise ValueError("Cannot award - missing fields:\n" + "\n".join(errors))

    unallocated, provisional = reserve_accounts(db, pkg.project_number)
    planned = float(pkg.planned_value or 0)
    awarded = sum(float(item.value or 0) for item in active_package_line_items(pkg))
    provisional.balance = float(provisional.balance or 0) - planned
    unallocated.balance = float(unallocated.balance or 0) + (planned - awarded)

    for item in active_package_line_items(pkg):
        item.status = "Awarded"
        code = item.cost_item_code_ref
        if code.deliverable_ref is not None and code.deliverable_ref.state == "Provisional":
            code.deliverable_ref.state = "Committed"

    pkg.is_contracted = True
    pkg.awarded_amount = awarded
    write_audit(
        db,
        pkg.project_number,
        "Package Awarded",
        f"{pkg.package_number} awarded at {awarded:.2f}; planned reserve released {planned:.2f}",
        target_type="Package",
        target_id=pkg.id,
    )


def create_cost_item_line(
    db: Session,
    pkg: Package,
    cost_item_code: CostItemCode,
    description: str,
    value: float,
    provisional: bool,
    *,
    confirm_supersede: bool = False,
) -> PackageCostItem:
    existing_ps = (
        db.query(PackageCostItem)
        .filter_by(
            package_id=pkg.id,
            cost_item_code_id=cost_item_code.id,
            provisional=True,
            superseded=False,
        )
        .first()
    )
    if existing_ps is not None and not provisional and not confirm_supersede:
        raise ValueError("A provisional sum exists at this Package x Cost Item Code intersection")

    line = PackageCostItem(
        package_id=pkg.id,
        cost_item_code_id=cost_item_code.id,
        cbs_l2_code=cost_item_code.deliverable_ref.cbs_l2_code
        if cost_item_code.deliverable_ref is not None else (cost_item_code.indirect_l2_code or ""),
        description=description,
        value=value,
        provisional=provisional,
        status="Awarded" if pkg.is_contracted else "Draft",
    )
    db.add(line)
    db.flush()
    if existing_ps is not None and not provisional:
        existing_ps.superseded = True
        existing_ps.superseded_by_id = line.id
        write_audit(
            db,
            pkg.project_number,
            "Line Item Superseded",
            f"Provisional line {existing_ps.id} superseded by firm line {line.id} at {cost_item_code.code}",
            target_type="PackageCostItem",
            target_id=existing_ps.id,
        )
    write_audit(
        db,
        pkg.project_number,
        "Line Item Created",
        f"{pkg.package_number}: {cost_item_code.code} {description} value {value:.2f}",
        target_type="PackageCostItem",
        target_id=line.id,
    )
    return line


def funding_identity(db: Session, project_number: str) -> float:
    unallocated, provisional = reserve_accounts(db, project_number)
    awarded_total = (
        db.query(func.coalesce(func.sum(PackageCostItem.value), 0))
        .join(Package, Package.id == PackageCostItem.package_id)
        .filter(Package.project_number == project_number)
        .filter(PackageCostItem.status == "Awarded", PackageCostItem.superseded.is_(False))
        .scalar()
        or 0
    )
    return float(unallocated.balance or 0) + float(provisional.balance or 0) + float(awarded_total or 0)


def po_package_suggestions(db: Session, project_number: str) -> list[dict]:
    po_rows = (
        db.query(
            PurchaseOrderLine.po_number,
            func.max(PurchaseOrderLine.memo_main).label("memo_main"),
            func.sum(PurchaseOrderLine.amount).label("amount"),
        )
        .filter_by(project_number=project_number, voided=False)
        .group_by(PurchaseOrderLine.po_number)
        .all()
    )
    packages = db.query(Package).filter_by(project_number=project_number).all()
    suggestions: list[dict] = []
    for po in po_rows:
        memo = (po.memo_main or "").lower()
        best: Package | None = None
        score = 0
        for pkg in packages:
            desc = (pkg.description or "").lower()
            if memo and desc and (memo in desc or desc in memo):
                candidate_score = min(len(memo), len(desc))
                if candidate_score > score:
                    score = candidate_score
                    best = pkg
        suggestions.append({
            "po_number": po.po_number,
            "memo_main": po.memo_main or "",
            "amount": float(po.amount or 0),
            "suggested_package": best.package_number if best else "",
            "suggested_description": best.description if best else "",
        })
    return suggestions


def cbs_rows(db: Session, project_number: str) -> list[dict]:
    reserve_accounts(db, project_number)
    reserve_rows = (
        db.query(BudgetReserveBalance, BudgetReserveSubAccount)
        .join(BudgetReserveSubAccount, BudgetReserveSubAccount.code == BudgetReserveBalance.reserve_code)
        .filter(BudgetReserveBalance.project_number == project_number)
        .order_by(BudgetReserveBalance.reserve_code)
        .all()
    )
    reserve = [
        {
            "code": subaccount.code,
            "name": subaccount.name,
            "role": subaccount.role,
            "balance": balance.balance,
        }
        for balance, subaccount in reserve_rows
    ]
    indirect_l2 = db.query(IndirectL2Account).order_by(IndirectL2Account.code).all()
    direct_components = db.query(Deliverable).filter_by(project_number=project_number).order_by(Deliverable.cbs_l2_code).all()
    codes = db.query(CostItemCode).filter_by(project_number=project_number).order_by(CostItemCode.code).all()
    totals = dict(
        db.execute(text("""
            SELECT cic.code, COALESCE(SUM(pci.value), 0) AS total
            FROM cost_item_codes cic
            LEFT JOIN package_cost_items pci
              ON pci.cost_item_code_id = cic.id
             AND pci.superseded = 0
            WHERE cic.project_number = :project_number
            GROUP BY cic.code
        """), {"project_number": project_number}).fetchall()
    )
    ps_codes = {
        row[0]
        for row in db.execute(text("""
            SELECT DISTINCT cic.code
            FROM cost_item_codes cic
            JOIN package_cost_items pci ON pci.cost_item_code_id = cic.id
            WHERE cic.project_number = :project_number
              AND pci.provisional = 1
              AND pci.superseded = 0
        """), {"project_number": project_number}).fetchall()
    }
    return [
        {"reserve": reserve},
        {"indirect_l2": indirect_l2},
        {"direct_components": direct_components, "deliverables": direct_components},
        {"codes": codes, "totals": totals, "ps_codes": ps_codes},
    ]
