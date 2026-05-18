"""Package detail and cost buildup routes."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..cbs import award_package, create_cost_item_line, next_cost_item_code, plan_package
from ..cost_nodes import flatten_cost_nodes, parse_float, process_cost_column
from ..dependencies import DbDep
from ..formatting import fmt_zar
from ..lookups import get_package_or_404, get_project_or_404
from ..models import (
    ControlAccount,
    CostItemCode,
    CostNodeAuditLog,
    CostComponent,
    IndirectL2Account,
    PackageCostItem,
    PackageCostNode,
    PackageCostSheet,
)
from ..seed import COST_ITEM_LIBRARY_DIRECT, COST_ITEM_LIBRARY_INDIRECT, PRICING_BASES
from ..reports import project_totals
from ..templates import templates


router = APIRouter()


def _sheet_redirect(project_number: str, package_number: str, sheet_id: int | None = None):
    suffix = f"?sheet_id={sheet_id}" if sheet_id is not None else ""
    return RedirectResponse(
        f"/project/{project_number}/packages/{package_number}/cost{suffix}",
        status_code=303,
    )


def _next_cost_sheet_number(db: Session, package_id: int) -> str:
    count = db.query(PackageCostSheet).filter_by(package_id=package_id, sheet_type="Variation").count()
    return f"VAR-{count + 1:03d}"


def _next_baseline_sheet_number(db: Session, package_id: int) -> str:
    count = db.query(PackageCostSheet).filter_by(package_id=package_id, sheet_type="Baseline").count()
    return f"BL-{count + 1:03d}"


def _is_working_sheet(sheet: PackageCostSheet) -> bool:
    return sheet.sheet_type in {"Original", "Working Estimate", "Variation"} and sheet.status != "Locked"


def _is_locked_sheet(sheet: PackageCostSheet) -> bool:
    return sheet.sheet_type == "Baseline" or sheet.status == "Locked"


def _assert_cost_sheet_editable(sheet: PackageCostSheet) -> None:
    if _is_locked_sheet(sheet):
        raise HTTPException(status_code=400, detail="Locked baselines are read-only")


def _ensure_cost_sheets(db: Session, pkg) -> list[PackageCostSheet]:
    sheets = (
        db.query(PackageCostSheet)
        .filter_by(package_id=pkg.id)
        .order_by(PackageCostSheet.display_order, PackageCostSheet.id)
        .all()
    )
    original = next((sheet for sheet in sheets if sheet.sheet_type in {"Original", "Working Estimate"}), None)
    if original is None:
        original = PackageCostSheet(
            package_id=pkg.id,
            sheet_number="ORIGINAL",
            title="Package Base Cost",
            sheet_type="Working Estimate",
            status="Working",
            display_order=0,
            created_at=datetime.now(),
        )
        db.add(original)
        db.flush()
        sheets.insert(0, original)
    else:
        if original.title == "Original Cost Sheet":
            original.title = "Package Base Cost"
        if original.sheet_type == "Original":
            original.sheet_type = "Working Estimate"
        if original.status == "Draft":
            original.status = "Working"
    for node in pkg.cost_nodes:
        if node.cost_sheet_id is None:
            node.cost_sheet_id = original.id
    db.commit()
    return (
        db.query(PackageCostSheet)
        .filter_by(package_id=pkg.id)
        .order_by(PackageCostSheet.display_order, PackageCostSheet.id)
        .all()
    )


def _active_cost_sheet(request: Request, sheets: list[PackageCostSheet]) -> PackageCostSheet:
    requested = request.query_params.get("sheet_id", "")
    if requested:
        for sheet in sheets:
            if str(sheet.id) == requested:
                return sheet
    return next((sheet for sheet in sheets if sheet.sheet_type in {"Original", "Working Estimate"}), sheets[0])


def _is_cost_sheet_open(request: Request) -> bool:
    return bool(request.query_params.get("sheet_id", "").strip())


def _resolve_cost_sheet(db: Session, pkg, sheet_id: str) -> PackageCostSheet:
    if sheet_id.strip():
        sheet = db.get(PackageCostSheet, int(sheet_id))
        if sheet is None or sheet.package_id != pkg.id:
            raise HTTPException(status_code=400, detail="Cost Sheet must belong to the same package")
        return sheet
    return _ensure_cost_sheets(db, pkg)[0]


def _cost_node_amount(node: PackageCostNode, column: str) -> float:
    value = getattr(node, column) or 0
    return float(value)


def _cost_node_subtotals(node: PackageCostNode) -> dict[str, float]:
    baseline = _cost_node_amount(node, "baseline_amount")
    pre_award = _cost_node_amount(node, "pre_award_amount")
    contract = _cost_node_amount(node, "contract_amount")
    for child in node.children:
        child_totals = _cost_node_subtotals(child)
        baseline += child_totals["baseline"]
        pre_award += child_totals["pre_award"]
        contract += child_totals["contract"]
    return {
        "baseline": baseline,
        "pre_award": pre_award,
        "contract": contract,
    }


def _cost_node_grid_row(node: PackageCostNode, cost_item_account_names: dict[str, str] | None = None) -> dict:
    cost_item_account_names = cost_item_account_names or {}
    totals = _cost_node_subtotals(node)
    children = [
        _cost_node_grid_row(child, cost_item_account_names)
        for child in sorted(node.children, key=lambda n: n.display_order)
    ]
    is_item = node.is_item
    if is_item:
        node_type = "Cost Line"
    else:
        node_type = "Cost Grouping"
    cost_item_account = ""
    if is_item and node.code:
        account_name = cost_item_account_names.get(node.code, "")
        cost_item_account = f"{node.code} - {account_name}" if account_name else node.code

    row = {
        "id": node.id,
        "node_id": node.id,
        "parent_id": node.parent_id,
        "code": node.code or "",
        "description": node.description,
        "type": node_type,
        "control_account": node.cc_code or "",
        "cost_item_account": cost_item_account,
        "baseline": totals["baseline"],
        "baseline_display": fmt_zar(totals["baseline"]) if totals["baseline"] else "",
        "pre_award": totals["pre_award"],
        "pre_award_display": fmt_zar(totals["pre_award"]) if totals["pre_award"] else "",
        "contract": totals["contract"],
        "contract_display": fmt_zar(totals["contract"]) if totals["contract"] else "",
        "unit": node.unit,
        "qty": node.qty,
        "rate": node.rate,
        "baseline_amount": node.baseline_amount,
        "pre_award_unit": node.pre_award_unit,
        "pre_award_qty": node.pre_award_qty,
        "pre_award_rate": node.pre_award_rate,
        "pre_award_amount": node.pre_award_amount,
        "contract_unit": node.contract_unit,
        "contract_qty": node.contract_qty,
        "contract_rate": node.contract_rate,
        "contract_amount": node.contract_amount,
    }
    if children:
        row["_children"] = children
    return row


def _cost_node_options(nodes: list[PackageCostNode]) -> list[PackageCostNode]:
    ordered: list[PackageCostNode] = []

    def walk(node: PackageCostNode) -> None:
        ordered.append(node)
        for child in sorted(node.children, key=lambda n: n.display_order):
            if not child.is_item:
                walk(child)

    for node in sorted(nodes, key=lambda n: n.display_order):
        if not node.is_item:
            walk(node)
    return ordered


def _cost_item_code_option_rows(codes: list[CostItemCode]) -> list[dict]:
    return [
        {
            "id": code.id,
            "cost_component_id": code.cost_component_id,
            "code": code.code,
            "name": code.name,
        }
        for code in codes
        if code.cost_component_id is not None
    ]


def _cost_sheet_row(pkg, sheet: PackageCostSheet) -> dict:
    roots = [node for node in pkg.cost_nodes if node.parent_id is None and node.cost_sheet_id == sheet.id]
    totals = {"baseline": 0.0, "pre_award": 0.0, "contract": 0.0}
    for node in roots:
        node_totals = _cost_node_subtotals(node)
        totals["baseline"] += node_totals["baseline"]
        totals["pre_award"] += node_totals["pre_award"]
        totals["contract"] += node_totals["contract"]
    return {
        "id": sheet.id,
        "sheet_number": sheet.sheet_number,
        "title": sheet.title,
        "sheet_type": sheet.sheet_type,
        "status": sheet.status,
        "locked": _is_locked_sheet(sheet),
        "description": sheet.description or "",
        "baseline": totals["baseline"],
        "baseline_display": fmt_zar(totals["baseline"]) if totals["baseline"] else "R 0.00",
        "pre_award": totals["pre_award"],
        "pre_award_display": fmt_zar(totals["pre_award"]) if totals["pre_award"] else "R 0.00",
        "contract": totals["contract"],
        "contract_display": fmt_zar(totals["contract"]) if totals["contract"] else "R 0.00",
        "open_url": f"/project/{pkg.project_number}/packages/{pkg.package_number}/cost?sheet_id={sheet.id}",
    }


def _clone_cost_node_tree(
    db: Session,
    node: PackageCostNode,
    *,
    package_id: int,
    cost_sheet_id: int,
    parent_id: int | None,
) -> PackageCostNode:
    cloned = PackageCostNode(
        package_id=package_id,
        cost_sheet_id=cost_sheet_id,
        parent_id=parent_id,
        code=node.code,
        description=node.description,
        is_item=node.is_item,
        cc_code=node.cc_code,
        unit=node.unit,
        qty=node.qty,
        rate=node.rate,
        baseline_amount=node.baseline_amount,
        pre_award_unit=node.pre_award_unit,
        pre_award_qty=node.pre_award_qty,
        pre_award_rate=node.pre_award_rate,
        pre_award_amount=node.pre_award_amount,
        contract_unit=node.contract_unit,
        contract_qty=node.contract_qty,
        contract_rate=node.contract_rate,
        contract_amount=node.contract_amount,
        display_order=node.display_order,
    )
    db.add(cloned)
    db.flush()
    for child in sorted(node.children, key=lambda n: n.display_order):
        _clone_cost_node_tree(db, child, package_id=package_id, cost_sheet_id=cost_sheet_id, parent_id=cloned.id)
    return cloned


def _cost_component_option_rows(components: list[CostComponent]) -> list[dict]:
    return [
        {
            "id": component.id,
            "code": component.cbs_l2_code,
            "description": component.description,
            "commodity_code": component.commodity_code,
        }
        for component in components
    ]


def _package_detail_response(request: Request, db: Session, project_number: str, package_number: str, active_pkg_tab: str):
    project = get_project_or_404(db, project_number)
    pkg = get_package_or_404(db, project_number, package_number)
    totals = project_totals(db, project_number)

    if active_pkg_tab == "cost":
        cost_sheets = _ensure_cost_sheets(db, pkg)
        active_cost_sheet = _active_cost_sheet(request, cost_sheets)
        cost_sheet_open = _is_cost_sheet_open(request)
        cost_components = (
            db.query(CostComponent)
            .filter_by(project_number=project_number)
            .order_by(CostComponent.cbs_l2_code)
            .all()
        )
        indirect_l2 = db.query(IndirectL2Account).order_by(IndirectL2Account.code).all()
        cost_codes = db.query(CostItemCode).filter_by(project_number=project_number).order_by(CostItemCode.code).all()
        cost_item_account_names = {code.code: code.name for code in cost_codes}
        root_nodes = [
            n for n in pkg.cost_nodes
            if n.parent_id is None and n.cost_sheet_id == active_cost_sheet.id
        ]
        cost_node_rows = [
            _cost_node_grid_row(node, cost_item_account_names)
            for node in sorted(root_nodes, key=lambda n: n.display_order)
        ]
        cost_node_totals = {
            "baseline": sum(row["baseline"] for row in cost_node_rows),
            "pre_award": sum(row["pre_award"] for row in cost_node_rows),
            "contract": sum(row["contract"] for row in cost_node_rows),
        }
        cost_group_options = _cost_node_options(root_nodes)
        cost_sheet_rows = [_cost_sheet_row(pkg, sheet) for sheet in cost_sheets]
        control_accounts = db.query(ControlAccount).order_by(ControlAccount.code).all()
        award_errors = []
        return templates.TemplateResponse("package_wbs.html", {
            "request": request,
            "project": project,
            "totals": totals,
            "package": pkg,
            "cost_components": cost_components,
            "cost_component_options": _cost_component_option_rows(cost_components),
            "indirect_l2": indirect_l2,
            "cost_codes": cost_codes,
            "cost_item_code_options": _cost_item_code_option_rows(cost_codes),
            "direct_library": COST_ITEM_LIBRARY_DIRECT,
            "indirect_library": COST_ITEM_LIBRARY_INDIRECT,
            "pricing_bases": PRICING_BASES,
            "cost_node_rows": cost_node_rows,
            "cost_node_totals": cost_node_totals,
            "cost_group_options": cost_group_options,
            "cost_sheets": cost_sheets,
            "cost_sheet_rows": cost_sheet_rows,
            "active_cost_sheet": active_cost_sheet,
            "cost_sheet_open": cost_sheet_open,
            "active_cost_sheet_locked": _is_locked_sheet(active_cost_sheet),
            "active_cost_sheet_working": _is_working_sheet(active_cost_sheet),
            "control_accounts": control_accounts,
            "award_errors": award_errors,
            "active_tab": "wbs",
            "active_pkg_tab": active_pkg_tab,
        })

    root_nodes = [n for n in pkg.cost_nodes if n.parent_id is None]
    cost_rows = flatten_cost_nodes(root_nodes)

    all_sections = sorted(
        [n for n in pkg.cost_nodes if not n.is_item],
        key=lambda n: n.display_order,
    )
    control_accounts = db.query(ControlAccount).order_by(ControlAccount.code).all()

    item_ids = [n.id for n in pkg.cost_nodes if n.is_item]
    audit_data: dict[int, list] = {}
    if item_ids:
        from sqlalchemy import select as sa_select
        audit_rows = db.execute(
            sa_select(CostNodeAuditLog)
            .where(CostNodeAuditLog.cost_node_id.in_(item_ids))
            .order_by(CostNodeAuditLog.changed_at)
        ).scalars().all()
        for row in audit_rows:
            audit_data.setdefault(row.cost_node_id, []).append({
                "action": row.action,
                "changed_at": row.changed_at.strftime("%d %b %Y %H:%M"),
                "snapshot": json.loads(row.snapshot),
            })

    return templates.TemplateResponse("package_detail.html", {
        "request": request,
        "project": project,
        "totals": totals,
        "package": pkg,
        "cost_rows": cost_rows,
        "all_sections": all_sections,
        "control_accounts": control_accounts,
        "audit_data": audit_data,
        "active_tab": "wbs",
        "active_pkg_tab": active_pkg_tab,
    })


@router.get("/project/{project_number}/packages/{package_number}/scope")
def package_scope(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "scope")


@router.get("/project/{project_number}/packages/{package_number}/schedule")
def package_schedule(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "schedule")


@router.get("/project/{project_number}/packages/{package_number}/cost")
def package_cost(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "cost")


@router.get("/project/{project_number}/packages/{package_number}/cost_components")
def package_cost_components(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "cost_components")


@router.get("/project/{project_number}/packages/{package_number}")
def package_detail(project_number: str, package_number: str, request: Request, db: DbDep):
    # Default tab is Cost — Scope/Schedule/Cost Components are hidden from the UI
    # for the cost-control-focused MVP. Their routes still exist but are
    # unreachable without typing the URL by hand.
    return _package_detail_response(request, db, project_number, package_number, "cost")


# ---------------------------------------------------------------------------
# Cost node CRUD routes
# ---------------------------------------------------------------------------

def _cost_redirect(project_number: str, package_number: str, sheet_id: int | None = None):
    return _sheet_redirect(project_number, package_number, sheet_id)


@router.post("/project/{project_number}/packages/{package_number}/cost/update-package")
def cost_update_package(
    project_number: str,
    package_number: str,
    db: DbDep,
    package_source: str = Form("Internal"),
    pricing_basis: str = Form("LS"),
    package_type: str = Form(""),
    planned_value: str = Form("0"),
):
    pkg = get_package_or_404(db, project_number, package_number)
    if package_source not in ("External", "Internal", "Client"):
        raise HTTPException(status_code=400, detail="Package source must be External, Internal, or Client")
    if pricing_basis not in PRICING_BASES:
        raise HTTPException(status_code=400, detail="Invalid pricing basis")
    pkg.package_source = package_source
    pkg.is_external = package_source == "External"
    pkg.pricing_basis = pricing_basis
    if package_type.strip():
        pkg.package_type = package_type.strip()
    try:
        planned = float(planned_value or 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Provisional allocation must be numeric") from exc
    try:
        plan_package(db, pkg, planned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _cost_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/cost/create-code")
def cost_create_code(
    project_number: str,
    package_number: str,
    db: DbDep,
    l2_kind: str = Form(...),
    cost_component_id: str = Form(""),
    indirect_l2_code: str = Form(""),
    name: str = Form(...),
    source: str = Form("custom"),
):
    get_package_or_404(db, project_number, package_number)
    cost_component = None
    indirect_code = None
    if l2_kind == "cost_component":
        cost_component = db.get(CostComponent, int(cost_component_id))
        if cost_component is None or cost_component.project_number != project_number:
            raise HTTPException(status_code=404, detail="Cost Component not found")
    elif l2_kind == "indirect":
        if db.get(IndirectL2Account, indirect_l2_code) is None:
            raise HTTPException(status_code=404, detail="Indirect Cost Component not found")
        indirect_code = indirect_l2_code
    else:
        raise HTTPException(status_code=400, detail="Level 2 kind must be direct Cost Component or indirect Cost Component")
    code, seq, _ = next_cost_item_code(
        db,
        project_number,
        cost_component=cost_component,
        indirect_l2_code=indirect_code,
    )
    db.add(CostItemCode(
        project_number=project_number,
        cost_component_id=cost_component.id if cost_component else None,
        indirect_l2_code=indirect_code,
        code=code,
        sequence=seq,
        name=name.strip(),
        source="library" if source == "library" else "custom",
    ))
    db.commit()
    return _cost_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/cost/add-line")
def cost_add_line(
    project_number: str,
    package_number: str,
    db: DbDep,
    cost_item_code_id: int = Form(...),
    description: str = Form(...),
    value: str = Form(...),
    line_type: str = Form("firm"),
    confirm_supersede: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    code = db.get(CostItemCode, cost_item_code_id)
    if code is None or code.project_number != project_number:
        raise HTTPException(status_code=404, detail="Cost Item Code not found")
    try:
        amount = float(value or 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Value must be numeric") from exc
    try:
        create_cost_item_line(
            db,
            pkg,
            code,
            description.strip(),
            amount,
            provisional=line_type == "ps",
            confirm_supersede=confirm_supersede == "yes",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _cost_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/cost/delete-line/{line_id}")
def cost_delete_line(project_number: str, package_number: str, line_id: int, db: DbDep):
    pkg = get_package_or_404(db, project_number, package_number)
    line = db.get(PackageCostItem, line_id)
    if line is None or line.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost Item line not found")
    db.delete(line)
    db.commit()
    return _cost_redirect(project_number, package_number)


def _next_sibling_order(pkg, parent_id: int | None, sheet_id: int | None = None) -> int:
    siblings = [
        n for n in pkg.cost_nodes
        if n.parent_id == parent_id and (sheet_id is None or n.cost_sheet_id == sheet_id)
    ]
    return max((n.display_order for n in siblings), default=-1) + 1


def _next_group_code(pkg, parent_id: int | None, db: Session, sheet_id: int | None = None) -> str:
    siblings = [
        n for n in pkg.cost_nodes
        if n.parent_id == parent_id and not n.is_item and (sheet_id is None or n.cost_sheet_id == sheet_id)
    ]
    sequence = len(siblings) + 1
    if parent_id is None:
        return str(sequence)
    parent = db.get(PackageCostNode, parent_id)
    parent_code = parent.code if parent and parent.code else str(sequence)
    return f"{parent_code}.{sequence}"


def _resolve_parent_id(db: Session, pkg, parent_id_str: str, sheet_id: int | None = None) -> int | None:
    """Parse a form-supplied parent_id and verify it belongs to *pkg*.

    Raises HTTP 400 if the parent exists but lives in a different package —
    the FK on `parent_id` only enforces row existence, so without this guard a
    hand-crafted POST could mis-parent a node into another package and trigger
    silent cross-package cascade-delete via ON DELETE CASCADE.
    """
    if not parent_id_str.strip():
        return None
    parent_int = int(parent_id_str)
    parent = db.get(PackageCostNode, parent_int)
    if parent is None or parent.package_id != pkg.id or (sheet_id is not None and parent.cost_sheet_id != sheet_id):
        raise HTTPException(status_code=400, detail="Parent must belong to the same package")
    return parent_int


def _resolve_cost_line_parent(db: Session, pkg, grouping_id: str, sheet_id: int | None = None) -> int | None:
    if not grouping_id.strip():
        return None
    node = db.get(PackageCostNode, int(grouping_id))
    if node is None or node.package_id != pkg.id or node.is_item or (sheet_id is not None and node.cost_sheet_id != sheet_id):
        raise HTTPException(status_code=400, detail="Worksheet Grouping must belong to the same package")
    return node.id


def _resolve_or_create_cost_item_code(
    db: Session,
    project_number: str,
    *,
    cost_component_id: str,
    cost_item_code_id: str,
    account_mode: str,
    library_account_name: str,
    custom_account_name: str,
) -> CostItemCode:
    if account_mode == "existing":
        if not cost_item_code_id.strip():
            raise HTTPException(status_code=400, detail="A CBS Level 3 Cost Item Account is required")
        if cost_item_code_id == "__add__":
            raise HTTPException(status_code=400, detail="Complete the Add Cost Item Account pop-out before saving")
        cost_code = db.get(CostItemCode, int(cost_item_code_id))
        if cost_code is None or cost_code.project_number != project_number:
            raise HTTPException(status_code=400, detail="Cost Item Account must belong to the same project")
        if cost_component_id.strip() and str(cost_code.cost_component_id) != str(cost_component_id):
            raise HTTPException(status_code=400, detail="Cost Item Account must belong to the selected Level 2 Cost Component")
        return cost_code

    if not cost_component_id.strip():
        raise HTTPException(status_code=400, detail="A Level 2 Cost Component is required")
    component = db.get(CostComponent, int(cost_component_id))
    if component is None or component.project_number != project_number:
        raise HTTPException(status_code=400, detail="Level 2 Cost Component must belong to the same project")

    if account_mode == "library":
        name = library_account_name.strip()
        source = "library"
    elif account_mode == "custom":
        name = custom_account_name.strip()
        source = "custom"
    else:
        raise HTTPException(status_code=400, detail="Cost Item Account mode must be existing, library, or custom")
    if not name:
        raise HTTPException(status_code=400, detail="Cost Item Account description is required")

    code, seq, _ = next_cost_item_code(db, project_number, cost_component=component)
    cost_code = CostItemCode(
        project_number=project_number,
        cost_component_id=component.id,
        code=code,
        sequence=seq,
        name=name,
        source=source,
    )
    db.add(cost_code)
    db.flush()
    return cost_code


@router.post("/project/{project_number}/packages/{package_number}/cost/add-section")
def cost_add_section(
    project_number: str,
    package_number: str,
    db: DbDep,
    code: str = Form(""),
    description: str = Form(...),
    parent_id: str = Form(""),
    sheet_id: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    sheet = _resolve_cost_sheet(db, pkg, sheet_id)
    _assert_cost_sheet_editable(sheet)
    parent_int = _resolve_parent_id(db, pkg, parent_id, sheet.id)
    if parent_int is not None:
        parent = db.get(PackageCostNode, parent_int)
        if parent is None or parent.parent_id is not None or parent.is_item:
            raise HTTPException(status_code=400, detail="Cost item accounts must sit directly below a Cost Grouping")
    node = PackageCostNode(
        package_id=pkg.id,
        cost_sheet_id=sheet.id,
        parent_id=parent_int,
        code=_next_group_code(pkg, parent_int, db, sheet.id),
        description=description.strip(),
        is_item=False,
        display_order=_next_sibling_order(pkg, parent_int, sheet.id),
    )
    db.add(node)
    db.commit()
    return _cost_redirect(project_number, package_number, sheet.id)


@router.post("/project/{project_number}/packages/{package_number}/cost/update-section/{node_id}")
def cost_update_section(
    project_number: str,
    package_number: str,
    node_id: int,
    db: DbDep,
    code: str = Form(""),
    description: str = Form(...),
):
    pkg = get_package_or_404(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    if node.cost_sheet_ref is not None:
        _assert_cost_sheet_editable(node.cost_sheet_ref)
    if node.is_item:
        raise HTTPException(status_code=400, detail="Use the cost line editor for cost lines")
    node.description = description.strip()
    db.commit()
    return _cost_redirect(project_number, package_number, node.cost_sheet_id)


def _write_audit_log(db: Session, node: PackageCostNode, action: str) -> None:
    log = CostNodeAuditLog(
        cost_node_id=node.id,
        action=action,
        changed_at=datetime.now(),
        snapshot=json.dumps({
            "bl_unit": node.unit, "bl_qty": node.qty, "bl_rate": node.rate, "bl_amount": node.baseline_amount,
            "pa_unit": node.pre_award_unit, "pa_qty": node.pre_award_qty, "pa_rate": node.pre_award_rate, "pa_amount": node.pre_award_amount,
            "ct_unit": node.contract_unit, "ct_qty": node.contract_qty, "ct_rate": node.contract_rate, "ct_amount": node.contract_amount,
        }),
    )
    db.add(log)
    db.commit()


@router.post("/project/{project_number}/packages/{package_number}/cost/add-sheet")
def cost_add_sheet(
    project_number: str,
    package_number: str,
    db: DbDep,
    title: str = Form(...),
    description: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    _ensure_cost_sheets(db, pkg)
    sheet_number = _next_cost_sheet_number(db, pkg.id)
    display_order = db.query(PackageCostSheet).filter_by(package_id=pkg.id).count()
    sheet = PackageCostSheet(
        package_id=pkg.id,
        sheet_number=sheet_number,
        title=title.strip(),
        sheet_type="Variation",
        status="Draft",
        description=description.strip(),
        display_order=display_order,
        created_at=datetime.now(),
    )
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return _cost_redirect(project_number, package_number, sheet.id)


@router.post("/project/{project_number}/packages/{package_number}/cost/create-baseline")
def cost_create_baseline(
    project_number: str,
    package_number: str,
    db: DbDep,
    sheet_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    if pkg.is_contracted:
        raise HTTPException(status_code=400, detail="Estimate baselines cannot be created after package award")
    source_sheet = _resolve_cost_sheet(db, pkg, sheet_id)
    if _is_locked_sheet(source_sheet):
        raise HTTPException(status_code=400, detail="Create a new baseline from an editable working estimate")
    sheet_number = _next_baseline_sheet_number(db, pkg.id)
    display_order = db.query(PackageCostSheet).filter_by(package_id=pkg.id).count()
    baseline = PackageCostSheet(
        package_id=pkg.id,
        sheet_number=sheet_number,
        title=title.strip(),
        sheet_type="Baseline",
        status="Locked",
        description=description.strip(),
        source_sheet_id=source_sheet.id,
        locked_at=datetime.now(),
        display_order=display_order,
        created_at=datetime.now(),
    )
    db.add(baseline)
    db.flush()
    roots = [
        node for node in pkg.cost_nodes
        if node.parent_id is None and node.cost_sheet_id == source_sheet.id
    ]
    for node in sorted(roots, key=lambda n: n.display_order):
        _clone_cost_node_tree(db, node, package_id=pkg.id, cost_sheet_id=baseline.id, parent_id=None)
    db.commit()
    db.refresh(baseline)
    return _cost_redirect(project_number, package_number, baseline.id)


@router.post("/project/{project_number}/packages/{package_number}/cost/add-item")
def cost_add_item(
    project_number: str,
    package_number: str,
    db: DbDep,
    code: str = Form(""),
    description: str = Form(...),
    parent_id: str = Form(""),
    sheet_id: str = Form(""),
    cost_grouping_id: str = Form(""),
    cost_component_id: str = Form(""),
    level2_id: str = Form(""),
    account_mode: str = Form("existing"),
    cost_item_code_id: str = Form(""),
    library_account_name: str = Form(""),
    custom_account_name: str = Form(""),
    cc_code: str = Form(""),
    baseline_unit: str = Form("Sum"),
    baseline_qty: str = Form(""),
    baseline_rate: str = Form(""),
    baseline_amount: str = Form(""),
    pre_award_unit: str = Form("Sum"),
    pre_award_qty: str = Form(""),
    pre_award_rate: str = Form(""),
    pre_award_amount: str = Form(""),
    contract_unit: str = Form("Sum"),
    contract_qty: str = Form(""),
    contract_rate: str = Form(""),
    contract_amount: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    sheet = _resolve_cost_sheet(db, pkg, sheet_id)
    _assert_cost_sheet_editable(sheet)
    selected_component_id = cost_component_id or level2_id
    cost_code = _resolve_or_create_cost_item_code(
        db,
        project_number,
        cost_component_id=selected_component_id,
        cost_item_code_id=cost_item_code_id,
        account_mode=account_mode,
        library_account_name=library_account_name,
        custom_account_name=custom_account_name,
    )
    component = db.get(CostComponent, cost_code.cost_component_id)
    if component is None:
        raise HTTPException(status_code=400, detail="Cost Item Account must be linked to a Level 2 Cost Component")
    if cc_code.strip() and cc_code.strip() != component.commodity_code:
        raise HTTPException(status_code=400, detail="Related Control Account must match the selected Cost Component")
    code = cost_code.code
    cc_code = cc_code.strip() or component.commodity_code
    parent_int = _resolve_cost_line_parent(db, pkg, cost_grouping_id or parent_id, sheet.id)
    bl_u, bl_q, bl_r, bl_a = process_cost_column(baseline_unit, baseline_qty, baseline_rate, baseline_amount)
    pa_u, pa_q, pa_r, pa_a = process_cost_column(pre_award_unit, pre_award_qty, pre_award_rate, pre_award_amount)
    ct_u, ct_q, ct_r, ct_a = process_cost_column(contract_unit, contract_qty, contract_rate, contract_amount)
    node = PackageCostNode(
        package_id=pkg.id,
        cost_sheet_id=sheet.id,
        parent_id=parent_int,
        code=code.strip(),
        description=description.strip(),
        is_item=True,
        cc_code=cc_code.strip() or None,
        unit=bl_u, qty=bl_q, rate=bl_r, baseline_amount=bl_a,
        pre_award_unit=pa_u, pre_award_qty=pa_q, pre_award_rate=pa_r, pre_award_amount=pa_a,
        contract_unit=ct_u, contract_qty=ct_q, contract_rate=ct_r, contract_amount=ct_a or None,
        display_order=_next_sibling_order(pkg, parent_int, sheet.id),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    _write_audit_log(db, node, "Created")
    return _cost_redirect(project_number, package_number, sheet.id)


@router.post("/project/{project_number}/packages/{package_number}/cost/update-item/{node_id}")
def cost_update_item(
    project_number: str,
    package_number: str,
    node_id: int,
    db: DbDep,
    code: str | None = Form(None),
    description: str = Form(...),
    cc_code: str = Form(""),
    baseline_unit: str = Form("Sum"),
    baseline_qty: str = Form(""),
    baseline_rate: str = Form(""),
    baseline_amount: str = Form(""),
    pre_award_unit: str = Form("Sum"),
    pre_award_qty: str = Form(""),
    pre_award_rate: str = Form(""),
    pre_award_amount: str = Form(""),
    contract_unit: str = Form("Sum"),
    contract_qty: str = Form(""),
    contract_rate: str = Form(""),
    contract_amount: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    if node.cost_sheet_ref is not None:
        _assert_cost_sheet_editable(node.cost_sheet_ref)
    if not node.is_item:
        raise HTTPException(status_code=400, detail="Use the group editor for Cost Groupings and cost item accounts")
    bl_u, bl_q, bl_r, bl_a = process_cost_column(baseline_unit, baseline_qty, baseline_rate, baseline_amount)
    pa_u, pa_q, pa_r, pa_a = process_cost_column(pre_award_unit, pre_award_qty, pre_award_rate, pre_award_amount)
    ct_u, ct_q, ct_r, ct_a = process_cost_column(contract_unit, contract_qty, contract_rate, contract_amount)
    if code is not None:
        node.code = code.strip()
    node.description = description.strip()
    node.cc_code = cc_code.strip() or None
    node.unit = bl_u
    node.qty = bl_q
    node.rate = bl_r
    node.baseline_amount = bl_a
    node.pre_award_unit = pa_u
    node.pre_award_qty = pa_q
    node.pre_award_rate = pa_r
    node.pre_award_amount = pa_a
    node.contract_unit = ct_u
    node.contract_qty = ct_q
    node.contract_rate = ct_r
    node.contract_amount = ct_a or None
    db.commit()
    _write_audit_log(db, node, "Updated")
    return _cost_redirect(project_number, package_number, node.cost_sheet_id)


@router.post("/project/{project_number}/packages/{package_number}/cost/set-contract/{node_id}")
def cost_set_contract(
    project_number: str,
    package_number: str,
    node_id: int,
    db: DbDep,
    contract_amount: str = Form(""),
):
    pkg = get_package_or_404(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    if node.cost_sheet_ref is not None:
        _assert_cost_sheet_editable(node.cost_sheet_ref)
    node.contract_amount = parse_float(contract_amount)
    db.commit()
    _write_audit_log(db, node, "Updated")
    return _cost_redirect(project_number, package_number, node.cost_sheet_id)


@router.post("/project/{project_number}/packages/{package_number}/cost/award")
def cost_award(project_number: str, package_number: str, db: DbDep):
    pkg = get_package_or_404(db, project_number, package_number)
    try:
        award_package(db, pkg)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _cost_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/cost/delete-node/{node_id}")
def cost_delete_node(project_number: str, package_number: str, node_id: int, db: DbDep):
    pkg = get_package_or_404(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    if node.cost_sheet_ref is not None:
        _assert_cost_sheet_editable(node.cost_sheet_ref)
    sheet_id = node.cost_sheet_id
    db.delete(node)
    db.commit()
    return _cost_redirect(project_number, package_number, sheet_id)
