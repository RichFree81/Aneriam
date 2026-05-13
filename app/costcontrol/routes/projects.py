"""Portfolio and project-level routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..capitalisation import IS_CAP_SQL, NOT_CAP_SQL
from ..cbs import cbs_rows, next_deliverable_code, po_package_suggestions, scope_item_state
from ..cost_nodes import package_effective_total
from ..dependencies import DbDep
from ..hierarchy import build_hierarchy
from ..lookups import get_project_or_404
from ..models import (
    ControlAccount,
    Deliverable,
    DeliverablePlantArea,
    ImportBatch,
    Package,
    PlantArea,
    PORtoLink,
    ProjectScopeItem,
    RTO,
    WorkType,
)
from .. import rto as rto_helpers
from ..reports import project_totals
from ..templates import templates


router = APIRouter()


def _plant_area_context(area: PlantArea, areas_by_id: dict[int, PlantArea]) -> dict[str, str]:
    """Return Facility Group / Plant Unit / Area codes for a level-3 area."""
    unit = areas_by_id.get(area.parent_id or 0)
    facility = areas_by_id.get(unit.parent_id) if unit is not None and unit.parent_id else None
    return {
        "facility_group_code": facility.code if facility is not None else "",
        "facility_group_name": facility.name if facility is not None else "",
        "plant_unit_code": unit.code if unit is not None else "",
        "plant_unit_name": unit.name if unit is not None else "",
        "area_code": area.code,
        "area_name": area.name,
    }


def _plant_area_tree(plant_areas: list[PlantArea]) -> list[dict[str, str | int]]:
    areas_by_id = {area.id: area for area in plant_areas}
    tree = []
    for area in plant_areas:
        if area.level != 3:
            continue
        context = _plant_area_context(area, areas_by_id)
        tree.append({
            "id": area.id,
            "code": context["area_code"],
            "name": context["area_name"],
            "plant_unit_code": context["plant_unit_code"],
            "plant_unit_name": context["plant_unit_name"],
            "facility_group_code": context["facility_group_code"],
            "facility_group_name": context["facility_group_name"],
        })
    return tree


def _get_deliverable_area_or_400(db: Session, plant_area_id: int) -> PlantArea:
    plant_area_ref = db.get(PlantArea, plant_area_id)
    if plant_area_ref is None or plant_area_ref.level != 3:
        raise HTTPException(status_code=400, detail="Deliverable area must be a level-3 Area")
    return plant_area_ref


def _last_batch(db: Session) -> ImportBatch | None:
    return db.query(ImportBatch).order_by(ImportBatch.imported_at.desc()).first()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def main_page(
    request: Request,
    db: DbDep,
    proj: list[str] = Query(default=[]),
):
    last_batch = _last_batch(db)

    # Active projects that have transactions (for the filter panel)
    all_projects = db.execute(
        text("""
            SELECT DISTINCT t.project_number, p.project_name
            FROM transactions t
            JOIN projects p ON p.project_number = t.project_number
            WHERE p.is_active = 1
            ORDER BY t.project_number
        """)
    ).fetchall()

    # Build IN-filter clause using numbered bind params (safe, no string interpolation)
    selected = [p for p in proj if p]  # drop empty strings
    if selected:
        placeholders = ", ".join(f":p{i}" for i in range(len(selected)))
        proj_filter = f"AND t.project_number IN ({placeholders})"
        bind = {f"p{i}": v for i, v in enumerate(selected)}
    else:
        proj_filter = ""
        bind = {}

    # Per-project totals — all active projects, left-joined so zero-spend projects still appear
    # proj_filter uses p.project_number here (not t.) because projects is the driving table
    active_proj_filter = proj_filter.replace("t.project_number", "p.project_number")
    # C-14 / C-15 — three-figure cost split + Fiscal Year column for FY2027.
    # Project Cost to Date EXCLUDES capitalisation rows (gross WIP figure).
    # Capitalised / Expensed is the ABS of the negative reversal account.
    # Net WIP = Project Cost − Capitalised.
    rows = db.execute(
        text(f"""
            SELECT
                p.project_number,
                p.project_name,
                p.current_budget,
                p.approved_capex,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL} THEN t.actual_cost    ELSE 0 END), 0) AS actual,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL} THEN t.committed_cost ELSE 0 END), 0) AS committed,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL}
                                  THEN t.actual_cost + t.committed_cost
                                  ELSE 0 END), 0) AS project_cost,
                COALESCE(ABS(SUM(CASE WHEN {IS_CAP_SQL}
                                      THEN t.actual_cost + t.committed_cost
                                      ELSE 0 END)), 0) AS capitalised,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL}
                                  THEN t.actual_cost + t.committed_cost
                                  ELSE 0 END), 0)
                - COALESCE(ABS(SUM(CASE WHEN {IS_CAP_SQL}
                                      THEN t.actual_cost + t.committed_cost
                                      ELSE 0 END)), 0) AS net_wip,
                p.planned_fy2027,
                0 AS forecast_fy2027,
                COALESCE(SUM(CASE WHEN t.fiscal_year = '2027' AND {NOT_CAP_SQL}
                               THEN t.actual_cost ELSE 0 END), 0) AS actual_fy2027
            FROM projects p
            LEFT JOIN transactions t ON t.project_number = p.project_number
            WHERE p.is_active = 1
            {active_proj_filter}
            GROUP BY p.project_number, p.project_name, p.current_budget, p.approved_capex, p.planned_fy2027
            ORDER BY p.project_number
        """),
        bind,
    ).fetchall()

    return templates.TemplateResponse("main.html", {
        "request": request,
        "projects": rows,
        "last_batch": last_batch,
        "all_projects": all_projects,
        "selected_projs": set(selected),
    })


@router.get("/project/{project_number}")
def project_page(
    project_number: str,
    request: Request,
    db: DbDep,
    cc_code: str = "",
    date_from: str = "",
    date_to: str = "",
):
    project = get_project_or_404(db, project_number)

    # Totals for this project (always unfiltered — used by summary cards).
    # C-14 / C-15 — three-figure split (Project Cost / Capitalised / Net WIP)
    # plus Fiscal Year-driven FY2027 figure.
    totals = db.execute(
        text(f"""
            SELECT
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL} THEN actual_cost    ELSE 0 END), 0) AS actual,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL} THEN committed_cost ELSE 0 END), 0) AS committed,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL}
                                  THEN actual_cost + committed_cost ELSE 0 END), 0) AS project_cost,
                COALESCE(ABS(SUM(CASE WHEN {IS_CAP_SQL}
                                      THEN actual_cost + committed_cost ELSE 0 END)), 0) AS capitalised,
                COALESCE(SUM(CASE WHEN {NOT_CAP_SQL}
                                  THEN actual_cost + committed_cost ELSE 0 END), 0)
                - COALESCE(ABS(SUM(CASE WHEN {IS_CAP_SQL}
                                      THEN actual_cost + committed_cost ELSE 0 END)), 0) AS net_wip,
                COALESCE(SUM(CASE WHEN fiscal_year = '2027' AND {NOT_CAP_SQL}
                               THEN actual_cost ELSE 0 END), 0) AS actual_fy2027
            FROM transactions WHERE project_number = :proj
        """),
        {"proj": project_number},
    ).fetchone()

    # Build filter clause (applied to the hierarchy aggregation)
    where = "WHERE t.project_number = :proj"
    params: dict = {"proj": project_number}
    if cc_code:
        where += " AND t.derived_cc_code = :cc"
        params["cc"] = cc_code
    if date_from:
        where += " AND t.date >= :df"
        params["df"] = date_from
    if date_to:
        where += " AND t.date <= :dt"
        params["dt"] = date_to

    # Aggregated hierarchy: one row per (L1, L2, L3) combination
    agg_rows = db.execute(
        text(f"""
            SELECT
                COALESCE(pt.level1, 'Unallocated') AS level1,
                pt.level2,
                pt.level3,
                SUM(t.actual_cost)    AS actual,
                SUM(t.committed_cost) AS committed,
                SUM(t.total_cost)     AS total
            FROM transactions t
            LEFT JOIN project_tasks pt
                ON  pt.project_number = t.project_number
                AND pt.leaf_name      = t.project_task_name
                AND t.project_task_name != ''
            {where}
            GROUP BY COALESCE(pt.level1, 'Unallocated'), pt.level2, pt.level3
            ORDER BY COALESCE(pt.level1, 'Unallocated'), pt.level2, pt.level3
        """),
        params,
    ).fetchall()

    hierarchy = build_hierarchy(agg_rows)

    # Control account options for filter dropdown
    cc_options = db.execute(
        text("""
            SELECT DISTINCT derived_cc_code, derived_cc_name
            FROM transactions WHERE project_number = :proj
            ORDER BY derived_cc_code
        """),
        {"proj": project_number},
    ).fetchall()

    po_total, po_unassigned, _ = _po_counts(db, project_number)
    return templates.TemplateResponse("project.html", {
        "request": request,
        "project": project,
        "hierarchy": hierarchy,
        "totals": totals,
        "cc_options": cc_options,
        "filter_cc": cc_code,
        "filter_date_from": date_from,
        "filter_date_to": date_to,
        "po_total_count": po_total,
        "po_unassigned_count": po_unassigned,
        "active_tab": "dashboard",
    })


@router.get("/project/{project_number}/scope")
def project_scope_page(
    project_number: str,
    request: Request,
    db: DbDep,
    work_type: str = "",
    plant_area: str = "",
    state: str = "",
):
    project = get_project_or_404(db, project_number)
    scope_items = (
        db.query(ProjectScopeItem)
        .filter_by(project_number=project_number)
        .order_by(ProjectScopeItem.id)
        .all()
    )
    work_types = db.query(WorkType).order_by(WorkType.label).all()
    plant_areas = db.query(PlantArea).order_by(PlantArea.code).all()
    areas_by_id = {area.id: area for area in plant_areas}
    facility_groups = [area for area in plant_areas if area.level == 1]
    plant_units = [area for area in plant_areas if area.level == 2]
    selectable_areas = [area for area in plant_areas if area.level == 3]
    plant_area_tree = _plant_area_tree(plant_areas)
    commodities = (
        db.query(ControlAccount)
        .filter(ControlAccount.code.in_(("201", "202", "203", "204", "205", "206")))
        .order_by(ControlAccount.code)
        .all()
    )

    rows = []
    scope_grid_rows = []
    for item in scope_items:
        item_state = scope_item_state(item)
        deliverables = []
        child_rows = []
        for deliverable in item.deliverables:
            area_contexts = [
                _plant_area_context(link.plant_area_ref, areas_by_id)
                for link in deliverable.plant_area_links
            ]
            area_labels = [f"{context['area_code']} {context['area_name']}" for context in area_contexts]
            area_codes = [context["area_code"] for context in area_contexts]
            plant_unit_codes = sorted({context["plant_unit_code"] for context in area_contexts if context["plant_unit_code"]})
            facility_group_codes = sorted({
                context["facility_group_code"]
                for context in area_contexts
                if context["facility_group_code"]
            })
            deliverables.append(deliverable)
            child_rows.append({
                "id": f"deliverable-{deliverable.id}",
                "record_id": deliverable.id,
                "parent_id": item.id,
                "description": deliverable.description,
                "type": "Deliverable",
                "scope_item_id": item.id,
                "work_type": item.work_type_ref.label if item.work_type_ref else "Not set",
                "work_type_code": item.work_type_code or "",
                "state": deliverable.state,
                "cbs_l2": deliverable.cbs_l2_code,
                "commodity_code": deliverable.commodity_code,
                "plant_areas": ", ".join(area_labels),
                "plant_area_codes": area_codes,
                "plant_unit_codes": plant_unit_codes,
                "facility_group_codes": facility_group_codes,
                "plant_area_ids": [link.plant_area_id for link in deliverable.plant_area_links],
                "actions": "",
            })
        rows.append({"item": item, "state": item_state, "deliverables": deliverables})
        scope_grid_rows.append({
            "id": f"scope-{item.id}",
            "record_id": item.id,
            "description": item.description,
            "type": "Scope Item",
            "scope_item_id": item.id,
            "modifies_ppe_reference": item.modifies_ppe_reference or "",
            "work_type": item.work_type_ref.label if item.work_type_ref else "Not set",
            "work_type_code": item.work_type_code or "",
            "state": item_state,
            "cbs_l2": "",
            "plant_areas": "",
            "plant_area_codes": [],
            "plant_unit_codes": [],
            "facility_group_codes": [],
            "actions": "",
            "_children": child_rows,
        })

    return templates.TemplateResponse("project_scope.html", {
        "request": request,
        "project": project,
        "rows": rows,
        "work_types": work_types,
        "facility_groups": facility_groups,
        "plant_units": plant_units,
        "plant_areas": selectable_areas,
        "plant_area_tree": plant_area_tree,
        "commodities": commodities,
        "filters": {"work_type": work_type, "plant_area": plant_area, "state": state},
        "scope_grid_rows": scope_grid_rows,
        "active_tab": "scope",
    })


@router.post("/project/{project_number}/scope/add-item")
def project_scope_add_item(
    project_number: str,
    db: DbDep,
    description: str = Form(...),
    work_type_code: str = Form(""),
    modifies_ppe_reference: str | None = Form(None),
):
    get_project_or_404(db, project_number)
    db.add(ProjectScopeItem(
        project_number=project_number,
        description=description.strip(),
        work_type_code=work_type_code.strip() or None,
        modifies_ppe_reference=modifies_ppe_reference.strip() or None,
    ))
    db.commit()
    return RedirectResponse(f"/project/{project_number}/scope", status_code=303)


@router.post("/project/{project_number}/scope/update-item/{scope_item_id}")
def project_scope_update_item(
    project_number: str,
    scope_item_id: int,
    db: DbDep,
    description: str = Form(...),
    work_type_code: str = Form(""),
    modifies_ppe_reference: str | None = Form(None),
):
    item = db.get(ProjectScopeItem, scope_item_id)
    if item is None or item.project_number != project_number:
        raise HTTPException(status_code=404, detail="Scope Item not found")
    item.description = description.strip()
    item.work_type_code = work_type_code.strip() or None
    if modifies_ppe_reference is not None:
        item.modifies_ppe_reference = modifies_ppe_reference.strip() or None
    db.commit()
    return RedirectResponse(f"/project/{project_number}/scope", status_code=303)


@router.post("/project/{project_number}/scope/delete-item/{scope_item_id}")
def project_scope_delete_item(project_number: str, scope_item_id: int, db: DbDep):
    item = db.get(ProjectScopeItem, scope_item_id)
    if item is None or item.project_number != project_number:
        raise HTTPException(status_code=404, detail="Scope Item not found")
    db.delete(item)
    db.commit()
    return RedirectResponse(f"/project/{project_number}/scope", status_code=303)


@router.post("/project/{project_number}/scope/add-deliverable")
def project_scope_add_deliverable(
    project_number: str,
    db: DbDep,
    scope_item_id: int = Form(...),
    description: str = Form(...),
    commodity_code: str = Form(...),
    plant_area_id: int = Form(...),
):
    get_project_or_404(db, project_number)
    scope_item = db.get(ProjectScopeItem, scope_item_id)
    if scope_item is None or scope_item.project_number != project_number:
        raise HTTPException(status_code=404, detail="Scope Item not found")
    if commodity_code not in ("201", "202", "203", "204", "205", "206"):
        raise HTTPException(status_code=400, detail="Deliverable commodity must be a direct Cost Category")
    plant_area_ref = _get_deliverable_area_or_400(db, plant_area_id)
    code, seq = next_deliverable_code(db, project_number, commodity_code)
    deliverable = Deliverable(
        project_number=project_number,
        scope_item_id=scope_item.id,
        description=description.strip(),
        commodity_code=commodity_code,
        cbs_l2_code=code,
        sequence=seq,
    )
    db.add(deliverable)
    db.flush()
    db.add(DeliverablePlantArea(deliverable_id=deliverable.id, plant_area_id=plant_area_ref.id))
    db.commit()
    return RedirectResponse(f"/project/{project_number}/scope", status_code=303)


@router.post("/project/{project_number}/scope/update-deliverable/{deliverable_id}")
def project_scope_update_deliverable(
    project_number: str,
    deliverable_id: int,
    db: DbDep,
    scope_item_id: int = Form(...),
    description: str = Form(...),
    commodity_code: str = Form(...),
    plant_area_id: int = Form(...),
):
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None or deliverable.project_number != project_number:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    scope_item = db.get(ProjectScopeItem, scope_item_id)
    if scope_item is None or scope_item.project_number != project_number:
        raise HTTPException(status_code=404, detail="Scope Item not found")
    if commodity_code not in ("201", "202", "203", "204", "205", "206"):
        raise HTTPException(status_code=400, detail="Deliverable commodity must be a direct Cost Category")
    plant_area_ref = _get_deliverable_area_or_400(db, plant_area_id)
    deliverable.scope_item_id = scope_item.id
    deliverable.description = description.strip()
    deliverable.commodity_code = commodity_code
    db.query(DeliverablePlantArea).filter_by(deliverable_id=deliverable.id).delete()
    db.add(DeliverablePlantArea(deliverable_id=deliverable.id, plant_area_id=plant_area_ref.id))
    db.commit()
    return RedirectResponse(f"/project/{project_number}/scope", status_code=303)


@router.post("/project/{project_number}/scope/delete-deliverable/{deliverable_id}")
def project_scope_delete_deliverable(project_number: str, deliverable_id: int, db: DbDep):
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None or deliverable.project_number != project_number:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    db.delete(deliverable)
    db.commit()
    return RedirectResponse(f"/project/{project_number}/scope", status_code=303)


@router.get("/project/{project_number}/cbs")
def project_cbs_page(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_cbs.html", {
        "request": request,
        "project": project,
        "cbs": cbs_rows(db, project_number),
        "active_tab": "cbs",
    })


@router.get("/project/{project_number}/po-package-suggestions")
def project_po_package_suggestions(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_po_package_suggestions.html", {
        "request": request,
        "project": project,
        "suggestions": po_package_suggestions(db, project_number),
        "active_tab": "wbs",
    })


@router.get("/project/{project_number}/analysis")
def project_analysis_placeholder(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_placeholder.html", {
        "request": request,
        "project": project,
        "active_tab": "analysis",
        "heading": "Analysis",
        "message": "Pivoted cost views and performance indicators are deferred for this rebuild.",
    })


@router.get("/project/{project_number}/changes")
def project_changes_placeholder(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_placeholder.html", {
        "request": request,
        "project": project,
        "active_tab": "changes",
        "heading": "Changes",
        "message": "Variation, compensation event, and trend tracking are deferred for this rebuild.",
    })


@router.get("/project/{project_number}/closeout")
def project_closeout_placeholder(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_placeholder.html", {
        "request": request,
        "project": project,
        "active_tab": "closeout",
        "heading": "Closeout",
        "message": "Capitalisation closeout is deferred; PBS and Work Type hooks are now in place.",
    })


@router.get("/project/{project_number}/drilldown")
def project_drilldown(
    project_number: str,
    db: DbDep,
    cost_type: str = "actual",
    l1: str = "",
    l2: str = "",
    l3: str = "",
    direct: bool = False,
    cc_code: str = "",
    date_from: str = "",
    date_to: str = "",
):
    """Return individual transactions backing a cost hierarchy cell (JSON)."""
    get_project_or_404(db, project_number)
    if cost_type not in ("actual", "committed"):
        raise HTTPException(status_code=400, detail="cost_type must be 'actual' or 'committed'")

    where_parts = ["t.project_number = :proj"]
    params: dict = {"proj": project_number}

    if l1 == "Unallocated":
        where_parts.append("COALESCE(pt.level1, 'Unallocated') = 'Unallocated'")
    elif l1:
        where_parts.append("COALESCE(pt.level1, 'Unallocated') = :l1")
        params["l1"] = l1

    if l2:
        where_parts.append("pt.level2 = :l2")
        params["l2"] = l2
        if direct:
            where_parts.append("pt.level3 IS NULL")
    elif l1 and direct:
        where_parts.append("pt.level2 IS NULL")

    if l3:
        where_parts.append("pt.level3 = :l3")
        params["l3"] = l3

    if cc_code:
        where_parts.append("t.derived_cc_code = :cc")
        params["cc"] = cc_code
    if date_from:
        where_parts.append("t.date >= :df")
        params["df"] = date_from
    if date_to:
        where_parts.append("t.date <= :dt")
        params["dt"] = date_to

    where = " AND ".join(where_parts)

    rows = db.execute(
        text(f"""
            SELECT
                t.date,
                t.source,
                t.document_number,
                t.vendor_name,
                t.po_number,
                t.po_description,
                t.project_task_name,
                t.derived_cc_name,
                t.actual_cost,
                t.committed_cost
            FROM transactions t
            LEFT JOIN project_tasks pt
                ON  pt.project_number = t.project_number
                AND pt.leaf_name      = t.project_task_name
                AND t.project_task_name != ''
            WHERE {where}
            ORDER BY t.document_number, t.date
        """),
        params,
    ).fetchall()

    parts = [p for p in [l1, l2, l3] if p]
    level_name = " › ".join(parts) if parts else project_number
    type_label = "Actual Cost" if cost_type == "actual" else "Committed Cost"

    all_rows = [
        {
            "date": str(r.date) if r.date else "",
            "source": r.source or "",
            "document_number": r.document_number or "",
            "vendor_name": r.vendor_name or "",
            "po_number": r.po_number or "",
            "po_description": r.po_description or "",
            "task": r.project_task_name or "",
            "cc": r.derived_cc_name or "",
            "actual": float(r.actual_cost or 0),
            "committed": float(r.committed_cost or 0),
        }
        for r in rows
    ]

    # Exclude zero-value rows for the selected cost type
    amt_key = "actual" if cost_type == "actual" else "committed"
    result_rows = [r for r in all_rows if r[amt_key] != 0]

    total = sum(r[amt_key] for r in result_rows)

    return {
        "type_label": type_label,
        "level_name": level_name,
        "cost_type": cost_type,
        "rows": result_rows,
        "total": total,
    }


@router.get("/project/{project_number}/po-detail/{po_number:path}")
def po_detail(project_number: str, po_number: str, db: DbDep):
    """Return structured PO detail: header info + per-task actuals/remaining/order."""
    get_project_or_404(db, project_number)

    # Header: vendor name and description from any transaction linked to this PO.
    # ORDER BY prefers rows where BOTH fields are populated, then by id for
    # determinism — without this, SQLite's row order can flip between requests
    # and render a row missing either field.
    header = db.execute(text("""
        SELECT vendor_name, po_description
        FROM transactions
        WHERE project_number = :proj
          AND (document_number = :po OR po_number = :po)
          AND (vendor_name != '' OR po_description != '')
        ORDER BY (vendor_name != '' AND po_description != '') DESC, id
        LIMIT 1
    """), {"proj": project_number, "po": po_number}).fetchone()

    vendor      = header.vendor_name    if header else ""
    description = header.po_description if header else ""

    import re as _re

    def _norm(s: str) -> str:
        """Normalise task name for fuzzy matching: strip non-alphanumeric chars."""
        return _re.sub(r"[^a-z0-9]", "", s.lower())

    # PO detail lines — order amounts per line from the detailed results file.
    # C-17 — exclude voided lines unless config flag flipped for debugging.
    from ..config import INCLUDE_VOIDED
    voided_clause = "" if INCLUDE_VOIDED else " AND voided = 0"
    detail_lines = db.execute(text(f"""
        SELECT memo, name, amount, status
        FROM po_lines
        WHERE po_number = :po{voided_clause}
        ORDER BY id
    """), {"po": po_number}).fetchall()

    # cc_code per task — derive from transactions where available
    cc_rows = db.execute(text("""
        SELECT project_task_name, derived_cc_code
        FROM transactions
        WHERE project_number = :proj
          AND (document_number = :po OR po_number = :po)
          AND derived_cc_code != ''
        LIMIT 100
    """), {"proj": project_number, "po": po_number}).fetchall()

    cc_by_norm: dict[str, str] = {}
    for r in cc_rows:
        k = _norm(r.project_task_name)
        if k not in cc_by_norm:
            cc_by_norm[k] = r.derived_cc_code

    # Group detail lines by task (leaf segment of the Name path)
    from collections import OrderedDict
    groups: OrderedDict = OrderedDict()
    for r in detail_lines:
        parts    = (r.name or "").split(" : ")
        leaf     = parts[-1].strip() if parts else (r.name or "")
        norm_key = _norm(leaf)
        if leaf not in groups:
            cc_code = cc_by_norm.get(norm_key, leaf[:3] if leaf else "")
            groups[leaf] = {"cc_code": cc_code, "task": leaf, "lines": []}
        groups[leaf]["lines"].append({
            "memo":   r.memo         or "",
            "amount": float(r.amount or 0),
            "status": r.status       or "",
        })

    task_groups = list(groups.values())
    total_order = sum(line["amount"] for group in task_groups for line in group["lines"])

    # Actuals and remaining — accurate totals from transaction data
    act_row = db.execute(text("""
        SELECT SUM(actual_cost) AS actual
        FROM transactions
        WHERE project_number = :proj AND po_number = :po
          AND lower(source) LIKE '%bill%'
    """), {"proj": project_number, "po": po_number}).fetchone()

    rem_row = db.execute(text("""
        SELECT SUM(committed_cost) AS remaining
        FROM transactions
        WHERE project_number = :proj AND document_number = :po
          AND lower(source) LIKE '%purchase order%'
    """), {"proj": project_number, "po": po_number}).fetchone()

    total_actual    = float(act_row.actual    or 0) if act_row else 0.0
    total_remaining = float(rem_row.remaining or 0) if rem_row else 0.0

    # C-16 — operational rule 1: closed POs have no live commitment, even
    # when their `Remaining` value is non-zero (that's an agreed shortfall).
    # Voided lines carry their own status strings ("Voided", "Cancelled", etc.)
    # which would defeat the closed-PO check, so exclude them here too.
    status_row = db.execute(text("""
        SELECT status FROM po_lines
        WHERE po_number = :po AND voided = 0
        ORDER BY id LIMIT 1
    """), {"po": po_number}).fetchone()
    po_status = status_row.status if status_row else ""
    is_closed = po_status.lower() in ("closed", "fully billed")
    effective_remaining = 0.0 if is_closed else total_remaining
    agreed_shortfall = total_remaining if (is_closed and total_remaining > 0) else 0.0

    return {
        "po_number":           po_number,
        "description":         description,
        "vendor":              vendor,
        "task_groups":         task_groups,
        "total_actual":        total_actual,
        "total_remaining":     total_remaining,      # raw — kept for back-compat
        "effective_remaining": effective_remaining,  # C-16 — zero for closed POs
        "total_order":         total_order,
        "po_status":           po_status,            # C-16
        "agreed_shortfall":    agreed_shortfall,     # C-16 — only when closed
    }


@router.get("/project/{project_number}/invoice-detail/{invoice_number:path}")
def invoice_detail(project_number: str, invoice_number: str, db: DbDep):
    """Return structured invoice detail: header info + line items."""
    get_project_or_404(db, project_number)

    rows = db.execute(text("""
        SELECT derived_cc_code, derived_cc_name, project_task_name,
               vendor_name, po_number, po_description,
               actual_cost
        FROM transactions
        WHERE project_number = :proj AND document_number = :inv
        ORDER BY derived_cc_code, project_task_name
    """), {"proj": project_number, "inv": invoice_number}).fetchall()

    if not rows:
        return {
            "invoice_number": invoice_number,
            "vendor": "", "po_number": "", "po_description": "",
            "lines": [], "total": 0.0,
        }

    first = rows[0]
    lines = [{
        "cc_code": r.derived_cc_code or "",
        "cc_name": r.derived_cc_name or "",
        "task":    r.project_task_name or "",
        "amount":  float(r.actual_cost or 0),
    } for r in rows]

    return {
        "invoice_number": invoice_number,
        "vendor":         first.vendor_name    or "",
        "po_number":      first.po_number      or "",
        "po_description": first.po_description or "",
        "lines":          lines,
        "total":          sum(line["amount"] for line in lines),
    }


@router.get("/project/{project_number}/packages")
def project_packages_page(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)

    totals = project_totals(db, project_number)
    packages = (
        db.query(Package)
        .filter_by(project_number=project_number)
        .order_by(Package.display_order)
        .all()
    )

    # Package budget allocation totals — per item, use most mature value:
    # contract_amount if set, else pre_award_amount, else baseline_amount
    total_alloc = sum(
        package_effective_total(pkg)
        for pkg in packages if pkg.package_stage != "Cancelled"
    )
    budget = project.current_budget or 0.0
    unallocated = budget - total_alloc
    alloc_pct = (total_alloc / budget * 100) if budget else 0.0

    pkg_stats = {
        "total_alloc": total_alloc,
        "unallocated": unallocated,
        "alloc_pct": alloc_pct,
    }

    po_total, po_unassigned, _ = _po_counts(db, project_number)
    return templates.TemplateResponse("project_packages.html", {
        "request": request,
        "project": project,
        "totals": totals,
        "packages": packages,
        "pkg_stats": pkg_stats,
        "po_total_count": po_total,
        "po_unassigned_count": po_unassigned,
        "active_tab": "wbs",
    })


def _po_counts(db: Session, project_number: str) -> tuple[int, int, int]:
    """Return (all, unassigned, linked) PO counts for the given project.
    Used both by the PO tab itself (for the filter pills) and by the other
    project-level pages (for the tab-title badge: 'Purchase Orders (N — M
    unassigned)')."""
    row = db.execute(
        text("""
            SELECT
                COUNT(DISTINCT pl.po_number) AS total,
                COUNT(DISTINCT CASE WHEN l.po_number IS NULL THEN pl.po_number END) AS unassigned
            FROM po_lines pl
            LEFT JOIN po_rto_links l ON l.po_number = pl.po_number
            WHERE pl.project_number = :proj AND pl.voided = 0
        """),
        {"proj": project_number},
    ).fetchone()
    total = row.total or 0
    unassigned = row.unassigned or 0
    return total, unassigned, total - unassigned


def _commitments_overview(db: Session, project_number: str) -> dict:
    po_total, po_unassigned, po_linked = _po_counts(db, project_number)
    po_row = db.execute(
        text("""
            SELECT
                COALESCE(SUM(amount), 0)        AS order_amount,
                COALESCE(SUM(actual_amount), 0) AS actual_amount,
                COALESCE(SUM(remaining), 0)     AS remaining_amount
            FROM po_lines
            WHERE project_number = :proj AND voided = 0
        """),
        {"proj": project_number},
    ).fetchone()
    rto_row = db.execute(
        text("""
            SELECT
                COUNT(*) AS rto_count,
                COALESCE(SUM(total_amount), 0) AS rto_amount,
                COUNT(CASE WHEN status = 'Approved' THEN 1 END) AS approved_count,
                COUNT(CASE WHEN status = 'Issued for PO' THEN 1 END) AS issued_count
            FROM rto
            WHERE project_number = :proj
        """),
        {"proj": project_number},
    ).fetchone()
    return {
        "po_total": po_total,
        "po_unassigned": po_unassigned,
        "po_linked": po_linked,
        "po_order_amount": float(po_row.order_amount or 0) if po_row else 0.0,
        "po_actual_amount": float(po_row.actual_amount or 0) if po_row else 0.0,
        "po_remaining_amount": float(po_row.remaining_amount or 0) if po_row else 0.0,
        "rto_count": rto_row.rto_count or 0,
        "rto_amount": float(rto_row.rto_amount or 0) if rto_row else 0.0,
        "rto_approved_count": rto_row.approved_count or 0,
        "rto_issued_count": rto_row.issued_count or 0,
    }


@router.get("/project/{project_number}/commitments")
def project_commitments_overview(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    summary = _commitments_overview(db, project_number)
    return templates.TemplateResponse("project_commitments_overview.html", {
        "request": request,
        "project": project,
        "summary": summary,
        "active_tab": "commitments",
        "active_commitments_tab": "overview",
    })


@router.get("/project/{project_number}/commitments/request-to-order")
def project_commitments_rtos(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    rows = db.execute(
        text("""
            SELECT
                r.id,
                r.rto_number,
                r.package_number,
                p.description AS package_description,
                r.vendor_name,
                r.description,
                r.total_amount,
                r.status,
                r.request_date,
                COUNT(l.id) AS linked_po_count,
                COALESCE(SUM(CASE WHEN l.is_original = 1 THEN pl.amount ELSE 0 END), 0) AS original_total,
                COALESCE(SUM(CASE WHEN l.is_original = 0 THEN pl.amount ELSE 0 END), 0) AS variation_total,
                COALESCE(SUM(pl.amount), 0) AS linked_po_total
            FROM rto r
            LEFT JOIN packages p
                ON p.project_number = r.project_number
               AND p.package_number = r.package_number
            LEFT JOIN po_rto_links l ON l.rto_id = r.id
            LEFT JOIN po_lines pl ON pl.po_number = l.po_number AND pl.voided = 0
            WHERE r.project_number = :proj
            GROUP BY r.id, r.rto_number, r.package_number, p.description, r.vendor_name,
                     r.description, r.total_amount, r.status, r.request_date
            ORDER BY r.request_date DESC, r.id DESC
        """),
        {"proj": project_number},
    ).fetchall()
    summary = {
        "rto_count": len(rows),
        "rto_amount": sum(float(row.total_amount or 0) for row in rows),
        "linked_po_total": sum(float(row.linked_po_total or 0) for row in rows),
    }
    return templates.TemplateResponse("project_commitments_rtos.html", {
        "request": request,
        "project": project,
        "rtos": rows,
        "summary": summary,
        "active_tab": "commitments",
        "active_commitments_tab": "rto",
    })


@router.get("/project/{project_number}/commitments/variation-requests")
def project_commitments_variation_requests(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_commitments_placeholder.html", {
        "request": request,
        "project": project,
        "active_tab": "commitments",
        "active_commitments_tab": "variation_requests",
        "heading": "Variation Requests",
        "message": "Variation request tracking will be defined here before order-level variations are implemented.",
    })


@router.get("/project/{project_number}/commitments/cashflow")
def project_commitments_cashflow(project_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    return templates.TemplateResponse("project_commitments_placeholder.html", {
        "request": request,
        "project": project,
        "active_tab": "commitments",
        "active_commitments_tab": "cashflow",
        "heading": "Cashflow",
        "message": "Project cashflow will be built from commitments, purchase orders, and approved forecast phasing.",
    })


@router.get("/project/{project_number}/commitments/purchase-orders")
@router.get("/project/{project_number}/purchase-orders")
def project_purchase_orders_page(
    project_number: str,
    request: Request,
    db: DbDep,
    filter: str = "all",
):
    """Project-level Purchase Orders listing.

    One row per PO (aggregated from po_lines), filtered to the project and
    excluding voided lines. The `filter` query param accepts 'all',
    'unassigned' (no RTO link), or 'linked' (has an RTO link).
    """
    project = get_project_or_404(db, project_number)
    if filter not in ("all", "unassigned", "linked"):
        filter = "all"

    totals = project_totals(db, project_number)

    # Aggregate po_lines into one row per po_number. MAX(vendor)/MAX(memo_main)
    # picks the populated value (lines of the same PO carry the same metadata
    # in NetSuite). MAX(status) biases toward the alphabetically-latest open
    # status, so a partly-billed PO shows "Pending Receipt" rather than
    # "Closed" — useful at a glance. LEFT JOIN po_rto_links surfaces the
    # linked RTO (if any) so the template can render either a clickable RTO
    # number or a "Link to RTO" button.
    if filter == "unassigned":
        having_clause = "HAVING l.po_number IS NULL"
    elif filter == "linked":
        having_clause = "HAVING l.po_number IS NOT NULL"
    else:
        having_clause = ""

    rows = db.execute(
        text(f"""
            SELECT
                pl.po_number,
                MIN(pl.date)             AS first_date,
                MAX(pl.vendor)           AS vendor,
                MAX(pl.memo_main)        AS description,
                COALESCE(SUM(pl.amount),         0) AS order_amount,
                COALESCE(SUM(pl.actual_amount),  0) AS actual_amount,
                COALESCE(SUM(pl.remaining),      0) AS remaining_amount,
                MAX(pl.status)           AS status,
                COUNT(*)                 AS line_count,
                r.rto_number             AS linked_rto_number,
                r.id                     AS linked_rto_id,
                r.total_amount           AS rto_total,
                r.package_number         AS linked_rto_package,
                l.is_original            AS linked_is_original
            FROM po_lines pl
            LEFT JOIN po_rto_links l ON l.po_number = pl.po_number
            LEFT JOIN rto r           ON r.id       = l.rto_id
            WHERE pl.project_number = :proj AND pl.voided = 0
            GROUP BY pl.po_number, r.rto_number, r.id, r.total_amount, r.package_number, l.po_number, l.is_original
            {having_clause}
            ORDER BY first_date DESC, pl.po_number
        """),
        {"proj": project_number},
    ).fetchall()

    # Counts are computed across the *unfiltered* set so the filter pills
    # always show the full picture; `summary.po_count` reflects the current
    # filtered view.
    total_count, unassigned_count, linked_count = _po_counts(db, project_number)

    summary = {
        "po_count":   len(rows),
        "order":      sum(r.order_amount    for r in rows),
        "actual":     sum(r.actual_amount   for r in rows),
        "remaining":  sum(r.remaining_amount for r in rows),
        "unassigned": unassigned_count,
    }

    return templates.TemplateResponse("project_purchase_orders.html", {
        "request": request,
        "project": project,
        "totals": totals,
        "purchase_orders": rows,
        "summary": summary,
        "po_total_count": total_count,
        "po_unassigned_count": unassigned_count,
        "po_linked_count": linked_count,
        "active_filter": filter,
        "active_tab": "commitments",
        "active_commitments_tab": "purchase_orders",
    })


# ---------------------------------------------------------------------------
# PO -> RTO link routes
# ---------------------------------------------------------------------------

def _po_summary(db: Session, project_number: str, po_number: str) -> dict | None:
    """Return aggregated PO data (vendor, amount, date) used both for the
    suggestions modal header and the match-scoring algorithm."""
    row = db.execute(
        text("""
            SELECT
                MIN(date)              AS first_date,
                MAX(vendor)            AS vendor,
                MAX(memo_main)         AS description,
                COALESCE(SUM(amount),  0) AS order_amount
            FROM po_lines
            WHERE project_number = :proj AND po_number = :po AND voided = 0
        """),
        {"proj": project_number, "po": po_number},
    ).fetchone()
    if not row or row.order_amount == 0 and not row.vendor:
        return None
    # SQLite returns dates as strings; normalise to date for the matcher.
    first_date = row.first_date
    if isinstance(first_date, str):
        try:
            from datetime import date as _date
            first_date = _date.fromisoformat(first_date)
        except ValueError:
            first_date = None
    return {
        "po_number":    po_number,
        "vendor":       row.vendor or "",
        "description":  row.description or "",
        "order_amount": float(row.order_amount or 0),
        "first_date":   first_date,
    }


@router.get("/project/{project_number}/commitments/purchase-orders/{po_number}/link-suggestions")
@router.get("/project/{project_number}/purchase-orders/{po_number}/link-suggestions")
def po_link_suggestions(project_number: str, po_number: str, db: DbDep):
    """JSON endpoint feeding the link modal — returns top-5 ranked candidates
    plus the full list of linkable RTOs for client-side search."""
    get_project_or_404(db, project_number)
    po = _po_summary(db, project_number, po_number)
    if po is None:
        raise HTTPException(status_code=404, detail="PO not found")
    suggestions = rto_helpers.suggest_matches(db, project_number, po)
    suggestions["po"] = {
        "po_number":    po["po_number"],
        "vendor":       po["vendor"],
        "description":  po["description"],
        "order_amount": po["order_amount"],
        "first_date":   po["first_date"].isoformat() if po["first_date"] else None,
    }
    # Include current link state if any
    existing = db.query(PORtoLink).filter_by(po_number=po_number).first()
    if existing:
        existing_rto = db.get(RTO, existing.rto_id)
        suggestions["currently_linked"] = {
            "rto_id":     existing.rto_id,
            "rto_number": existing_rto.rto_number if existing_rto else None,
        }
    else:
        suggestions["currently_linked"] = None
    return suggestions


@router.post("/project/{project_number}/commitments/purchase-orders/{po_number}/link")
@router.post("/project/{project_number}/purchase-orders/{po_number}/link")
def po_link_create(
    project_number: str,
    po_number: str,
    db: DbDep,
    rto_id: int = Form(...),
):
    get_project_or_404(db, project_number)
    rto = db.get(RTO, rto_id)
    if rto is None or rto.project_number != project_number:
        raise HTTPException(status_code=404, detail="RTO not found")
    existing = db.query(PORtoLink).filter_by(po_number=po_number).first()
    if existing:
        existing_rto = db.get(RTO, existing.rto_id)
        raise HTTPException(
            status_code=400,
            detail=f"PO already linked to {existing_rto.rto_number if existing_rto else existing.rto_id}",
        )
    # Slice E: first PO to link to this RTO is the original; later ones are
    # variations.
    is_first = db.query(PORtoLink).filter_by(rto_id=rto_id).count() == 0
    now = datetime.now()
    db.add(PORtoLink(
        po_number=po_number,
        rto_id=rto_id,
        source="manual",
        linked_at=now,
        linked_by="",
        is_original=is_first,
    ))
    # Auto-flip Approved -> Issued for PO when first PO links.
    if rto.status == rto_helpers.STATUS_APPROVED:
        rto.status = rto_helpers.STATUS_ISSUED
        rto.updated_at = now
    db.commit()
    return RedirectResponse(f"/project/{project_number}/commitments/purchase-orders", status_code=303)


@router.post("/project/{project_number}/commitments/purchase-orders/{po_number}/unlink")
@router.post("/project/{project_number}/purchase-orders/{po_number}/unlink")
def po_link_remove(project_number: str, po_number: str, db: DbDep):
    get_project_or_404(db, project_number)
    link = db.query(PORtoLink).filter_by(po_number=po_number).first()
    if link is None:
        raise HTTPException(status_code=404, detail="No link to remove")
    rto = db.get(RTO, link.rto_id)
    # Count BEFORE delete so we know how many will remain on the RTO.
    siblings = db.query(PORtoLink).filter_by(rto_id=link.rto_id).count() - 1
    db.delete(link)
    # Auto-flip back to Approved if the unlinked PO was the only one and the
    # RTO was sitting at "Issued for PO" purely on its account.
    if rto and rto.status == rto_helpers.STATUS_ISSUED and siblings == 0:
        rto.status = rto_helpers.STATUS_APPROVED
        rto.updated_at = datetime.now()
    db.commit()
    return RedirectResponse(f"/project/{project_number}/commitments/purchase-orders", status_code=303)
