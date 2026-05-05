"""FastAPI application — Cost Control MVP."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import BUNDLE_DIR, CAPITALISATION_ACCOUNT_KEYWORDS, REGISTER_DIR
from .database import Base, SessionLocal, engine, get_db
from .ingest import run_import
from .models import ControlAccount, CostNodeAuditLog, ImportBatch, Package, PackageCostNode, Project, ProjectTask, Transaction
from .packages_ingest import seed_packages
from .seed import seed_control_accounts, seed_projects


# C-14 — SQL fragments for capitalisation detection. Built once at import time
# from CAPITALISATION_ACCOUNT_KEYWORDS so future PMO renames only require a
# config edit. NOTE: keywords must not contain SQL `'` characters.
def _build_capitalisation_clauses() -> tuple[str, str]:
    """Return (is_cap, not_cap) SQL boolean fragments. Both reference the
    `account_full_name` column on the table you join them with."""
    likes = " OR ".join(
        f"account_full_name LIKE '%{kw.replace(chr(39), chr(39)*2)}%'"
        for kw in CAPITALISATION_ACCOUNT_KEYWORDS
    )
    return f"({likes})", f"NOT ({likes})"


_IS_CAP_SQL, _NOT_CAP_SQL = _build_capitalisation_clauses()

app = FastAPI(title="Cost Control MVP")

TEMPLATES_DIR = BUNDLE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))




# ---------------------------------------------------------------------------
# Startup: create tables and seed master data
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Migrations for columns added after initial release
        for migration in [
            "ALTER TABLE projects ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 0",
            "ALTER TABLE projects ADD COLUMN current_budget NUMERIC(18,2)",
            "ALTER TABLE projects ADD COLUMN approved_capex NUMERIC(18,2)",
            "ALTER TABLE projects ADD COLUMN planned_fy2027 NUMERIC(18,2)",
            "ALTER TABLE transactions ADD COLUMN vendor_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE transactions ADD COLUMN po_number TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE transactions ADD COLUMN po_description TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE po_lines ADD COLUMN name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE po_lines ADD COLUMN actual_amount NUMERIC(18,2) NOT NULL DEFAULT 0",
            "ALTER TABLE packages ADD COLUMN is_contracted BOOLEAN NOT NULL DEFAULT 0",
            "ALTER TABLE package_cost_nodes ADD COLUMN unit TEXT NOT NULL DEFAULT 'Sum'",
            "ALTER TABLE package_cost_nodes ADD COLUMN qty NUMERIC(18,4)",
            "ALTER TABLE package_cost_nodes ADD COLUMN rate NUMERIC(18,2)",
            "ALTER TABLE package_cost_nodes ADD COLUMN pre_award_unit TEXT NOT NULL DEFAULT 'Sum'",
            "ALTER TABLE package_cost_nodes ADD COLUMN pre_award_qty NUMERIC(18,4)",
            "ALTER TABLE package_cost_nodes ADD COLUMN pre_award_rate NUMERIC(18,2)",
            "ALTER TABLE package_cost_nodes ADD COLUMN contract_unit TEXT NOT NULL DEFAULT 'Sum'",
            "ALTER TABLE package_cost_nodes ADD COLUMN contract_qty NUMERIC(18,4)",
            "ALTER TABLE package_cost_nodes ADD COLUMN contract_rate NUMERIC(18,2)",
            (
                "CREATE TABLE IF NOT EXISTS cost_node_audit_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "cost_node_id INTEGER NOT NULL REFERENCES package_cost_nodes(id) ON DELETE CASCADE, "
                "action TEXT NOT NULL, "
                "changed_at DATETIME NOT NULL, "
                "snapshot TEXT NOT NULL)"
            ),
            # C-1 — PMO 18-column additions on transactions (added 2026-05-04)
            "ALTER TABLE transactions ADD COLUMN account_full_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE transactions ADD COLUMN fiscal_year TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE transactions ADD COLUMN fiscal_quarter TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE transactions ADD COLUMN transaction_date_created DATE",
            "ALTER TABLE transactions ADD COLUMN transaction_date_closed DATE",
            # C-2 — PO Detailed new columns on po_lines
            "ALTER TABLE po_lines ADD COLUMN internal_id INTEGER",
            "ALTER TABLE po_lines ADD COLUMN remaining NUMERIC(18,2) NOT NULL DEFAULT 0",
            "ALTER TABLE po_lines ADD COLUMN actual NUMERIC(18,2) NOT NULL DEFAULT 0",
            "ALTER TABLE po_lines ADD COLUMN vendor TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE po_lines ADD COLUMN date DATE",
            "ALTER TABLE po_lines ADD COLUMN voided BOOLEAN NOT NULL DEFAULT 0",
            # C-3 — Project Tasks new columns
            "ALTER TABLE project_tasks ADD COLUMN project_status TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE project_tasks ADD COLUMN parent_task_id INTEGER",
            "ALTER TABLE project_tasks ADD COLUMN date_created DATETIME",
            "ALTER TABLE project_tasks ADD COLUMN last_modified DATETIME",
            # C-4 — journal_lines and gl_lines tables are created automatically
            # by Base.metadata.create_all (see end of this function), so no
            # explicit CREATE TABLE migration is needed here.
        ]:
            try:
                db.execute(text(migration))
                db.commit()
            except Exception:
                db.rollback()
        seed_control_accounts(db)
        seed_projects(db)
        seed_packages(db, REGISTER_DIR)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def _build_hierarchy(rows) -> list[dict]:
    """Convert aggregated (level1, level2, level3, actual, committed, total) rows
    into a nested L1 → L2 → L3 list for the project template."""

    def _zero() -> dict:
        return {"actual": 0.0, "committed": 0.0, "total": 0.0}

    l1_order: list[str] = []
    l1_map: dict[str, dict] = {}

    for r in rows:
        l1 = r.level1 or "Unallocated"
        l2 = r.level2
        l3 = r.level3
        a  = float(r.actual or 0)
        c  = float(r.committed or 0)
        t  = float(r.total or 0)

        if l1 not in l1_map:
            l1_map[l1] = {**_zero(), "direct": None, "l2s": {}, "l2_order": []}
            l1_order.append(l1)
        n1 = l1_map[l1]
        n1["actual"] += a; n1["committed"] += c; n1["total"] += t

        if l2 is None:
            if n1["direct"] is None:
                n1["direct"] = _zero()
            n1["direct"]["actual"] += a; n1["direct"]["committed"] += c; n1["direct"]["total"] += t
        else:
            if l2 not in n1["l2s"]:
                n1["l2s"][l2] = {**_zero(), "name": l2, "direct": None, "l3_items": [], "_item_set": set()}
                n1["l2_order"].append(l2)
            n2 = n1["l2s"][l2]
            n2["actual"] += a; n2["committed"] += c; n2["total"] += t

            if l3 is None:
                if n2["direct"] is None:
                    n2["direct"] = _zero()
                n2["direct"]["actual"] += a; n2["direct"]["committed"] += c; n2["direct"]["total"] += t
            else:
                if l3 not in n2["_item_set"]:
                    n2["l3_items"].append({"name": l3, **_zero()})
                    n2["_item_set"].add(l3)
                item = next(i for i in n2["l3_items"] if i["name"] == l3)
                item["actual"] += a; item["committed"] += c; item["total"] += t

    result = []
    for l1_name in l1_order:
        n1 = l1_map[l1_name]
        l2_groups = []
        for l2_name in n1["l2_order"]:
            n2 = n1["l2s"][l2_name]
            l2_groups.append({
                "name": n2["name"], "actual": n2["actual"],
                "committed": n2["committed"], "total": n2["total"],
                "direct": n2["direct"], "l3_items": n2["l3_items"],
            })
        result.append({
            "name": l1_name, "actual": n1["actual"],
            "committed": n1["committed"], "total": n1["total"],
            "direct": n1["direct"], "l2_groups": l2_groups,
        })
    return result


def _flatten_cost_nodes(nodes: list, depth: int = 0, ancestor_ids: tuple = ()) -> list[dict]:
    """Recursively flatten a tree of PackageCostNode root nodes into a display list.

    Each entry carries: node, depth, ancestor_ids (tuple of ancestor node IDs from
    root down), and subtotals rolled up from all descendant item nodes.
    """
    rows = []
    for node in sorted(nodes, key=lambda n: n.display_order):
        my_ancestors = ancestor_ids
        child_rows = _flatten_cost_nodes(node.children, depth + 1, ancestor_ids + (node.id,))

        # Subtotals: own amounts (if is_item) + direct-child subtotals
        def _col_total(col: str, n=node, cr=child_rows) -> float:
            own = getattr(n, col) or 0.0
            return own + sum(r["_subtotals"][col] for r in cr if r["node"].parent_id == n.id)

        subtotals = {
            "baseline": _col_total("baseline_amount"),
            "pre_award": _col_total("pre_award_amount"),
            "contract": _col_total("contract_amount"),
        }
        subtotals["effective"] = (
            subtotals["contract"] if subtotals["contract"]
            else subtotals["pre_award"] if subtotals["pre_award"]
            else subtotals["baseline"]
        )

        rows.append({
            "node": node,
            "depth": depth,
            "ancestor_ids": my_ancestors,
            "_subtotals": subtotals,
        })
        rows.extend(child_rows)
    return rows


def _pkg_effective_total(pkg) -> float:
    """Sum the most-mature cost value across all item nodes for one package.

    Per item: contract_amount if set, else pre_award_amount, else baseline_amount.
    Sums all is_item=True nodes at any tree depth.
    """
    total = 0.0
    for node in pkg.cost_nodes:
        if node.is_item:
            v = node.contract_amount or node.pre_award_amount or node.baseline_amount
            if v:
                total += v
    return total


def _last_batch(db: Session) -> ImportBatch | None:
    return db.query(ImportBatch).order_by(ImportBatch.imported_at.desc()).first()


def _fmt_zar(value) -> str:
    try:
        if value is None:
            return "R 0.00"
        return f"R {float(value):,.2f}"
    except (TypeError, ValueError):
        return "R 0.00"


templates.env.filters["zar"] = _fmt_zar


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

DbDep = Annotated[Session, Depends(get_db)]


@app.get("/")
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
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL} THEN t.actual_cost    ELSE 0 END), 0) AS actual,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL} THEN t.committed_cost ELSE 0 END), 0) AS committed,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL}
                                  THEN t.actual_cost + t.committed_cost
                                  ELSE 0 END), 0) AS project_cost,
                COALESCE(ABS(SUM(CASE WHEN {_IS_CAP_SQL}
                                      THEN t.actual_cost + t.committed_cost
                                      ELSE 0 END)), 0) AS capitalised,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL}
                                  THEN t.actual_cost + t.committed_cost
                                  ELSE 0 END), 0)
                - COALESCE(ABS(SUM(CASE WHEN {_IS_CAP_SQL}
                                      THEN t.actual_cost + t.committed_cost
                                      ELSE 0 END)), 0) AS net_wip,
                p.planned_fy2027,
                0 AS forecast_fy2027,
                COALESCE(SUM(CASE WHEN t.fiscal_year = '2027' AND {_NOT_CAP_SQL}
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


@app.get("/project/{project_number}")
def project_page(
    project_number: str,
    request: Request,
    db: DbDep,
    cc_code: str = "",
    date_from: str = "",
    date_to: str = "",
):
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Totals for this project (always unfiltered — used by summary cards).
    # C-14 / C-15 — three-figure split (Project Cost / Capitalised / Net WIP)
    # plus Fiscal Year-driven FY2027 figure.
    totals = db.execute(
        text(f"""
            SELECT
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL} THEN actual_cost    ELSE 0 END), 0) AS actual,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL} THEN committed_cost ELSE 0 END), 0) AS committed,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL}
                                  THEN actual_cost + committed_cost ELSE 0 END), 0) AS project_cost,
                COALESCE(ABS(SUM(CASE WHEN {_IS_CAP_SQL}
                                      THEN actual_cost + committed_cost ELSE 0 END)), 0) AS capitalised,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL}
                                  THEN actual_cost + committed_cost ELSE 0 END), 0)
                - COALESCE(ABS(SUM(CASE WHEN {_IS_CAP_SQL}
                                      THEN actual_cost + committed_cost ELSE 0 END)), 0) AS net_wip,
                COALESCE(SUM(CASE WHEN fiscal_year = '2027' AND {_NOT_CAP_SQL}
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

    hierarchy = _build_hierarchy(agg_rows)

    # Control account options for filter dropdown
    cc_options = db.execute(
        text("""
            SELECT DISTINCT derived_cc_code, derived_cc_name
            FROM transactions WHERE project_number = :proj
            ORDER BY derived_cc_code
        """),
        {"proj": project_number},
    ).fetchall()

    return templates.TemplateResponse("project.html", {
        "request": request,
        "project": project,
        "hierarchy": hierarchy,
        "totals": totals,
        "cc_options": cc_options,
        "filter_cc": cc_code,
        "filter_date_from": date_from,
        "filter_date_to": date_to,
        "active_tab": "cost",
    })


@app.get("/project/{project_number}/drilldown")
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
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
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


@app.get("/project/{project_number}/po-detail/{po_number:path}")
def po_detail(project_number: str, po_number: str, db: DbDep):
    """Return structured PO detail: header info + per-task actuals/remaining/order."""
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

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
    from .config import INCLUDE_VOIDED
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
    total_order = sum(l["amount"] for g in task_groups for l in g["lines"])

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


@app.get("/project/{project_number}/invoice-detail/{invoice_number:path}")
def invoice_detail(project_number: str, invoice_number: str, db: DbDep):
    """Return structured invoice detail: header info + line items."""
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

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
        "total":          sum(l["amount"] for l in lines),
    }


def _project_totals(db: Session, project_number: str):
    """C-14 / C-15 — three-figure cost split + Fiscal Year-driven FY2027.

    Returns: (actual, committed, project_cost, capitalised, net_wip, actual_fy2027)
    All figures EXCLUDE capitalisation rows except `capitalised` itself.
    """
    return db.execute(
        text(f"""
            SELECT
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL} THEN actual_cost    ELSE 0 END), 0) AS actual,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL} THEN committed_cost ELSE 0 END), 0) AS committed,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL}
                                  THEN actual_cost + committed_cost ELSE 0 END), 0) AS project_cost,
                COALESCE(ABS(SUM(CASE WHEN {_IS_CAP_SQL}
                                      THEN actual_cost + committed_cost ELSE 0 END)), 0) AS capitalised,
                COALESCE(SUM(CASE WHEN {_NOT_CAP_SQL}
                                  THEN actual_cost + committed_cost ELSE 0 END), 0)
                - COALESCE(ABS(SUM(CASE WHEN {_IS_CAP_SQL}
                                      THEN actual_cost + committed_cost ELSE 0 END)), 0) AS net_wip,
                COALESCE(SUM(CASE WHEN fiscal_year = '2027' AND {_NOT_CAP_SQL}
                               THEN actual_cost ELSE 0 END), 0) AS actual_fy2027
            FROM transactions WHERE project_number = :proj
        """),
        {"proj": project_number},
    ).fetchone()


@app.get("/project/{project_number}/packages")
def project_packages_page(project_number: str, request: Request, db: DbDep):
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    totals = _project_totals(db, project_number)
    packages = (
        db.query(Package)
        .filter_by(project_number=project_number)
        .order_by(Package.display_order)
        .all()
    )

    # Package budget allocation totals — per item, use most mature value:
    # contract_amount if set, else pre_award_amount, else baseline_amount
    total_alloc = sum(
        _pkg_effective_total(pkg)
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

    return templates.TemplateResponse("project_packages.html", {
        "request": request,
        "project": project,
        "totals": totals,
        "packages": packages,
        "pkg_stats": pkg_stats,
        "active_tab": "packages",
    })


@app.get("/project/{project_number}/purchase-orders")
def project_purchase_orders_page(project_number: str, request: Request, db: DbDep):
    """Project-level Purchase Orders listing.

    One row per PO (aggregated from po_lines), filtered to the project and
    excluding voided lines. The Package column is a placeholder until the RTO
    workflow is implemented — every PO renders as 'Unassigned' for now.
    """
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    totals = _project_totals(db, project_number)

    # Aggregate po_lines into one row per po_number. MAX(vendor)/MAX(memo_main)
    # picks the populated value (lines of the same PO carry the same metadata
    # in NetSuite). MAX(status) biases toward the alphabetically-latest open
    # status, so a partly-billed PO shows "Pending Receipt" rather than
    # "Closed" — useful at a glance.
    rows = db.execute(
        text("""
            SELECT
                po_number,
                MIN(date)             AS first_date,
                MAX(vendor)           AS vendor,
                MAX(memo_main)        AS description,
                COALESCE(SUM(amount),         0) AS order_amount,
                COALESCE(SUM(actual_amount),  0) AS actual_amount,
                COALESCE(SUM(remaining),      0) AS remaining_amount,
                MAX(status)           AS status,
                COUNT(*)              AS line_count
            FROM po_lines
            WHERE project_number = :proj AND voided = 0
            GROUP BY po_number
            ORDER BY first_date DESC, po_number
        """),
        {"proj": project_number},
    ).fetchall()

    # Portfolio-style summary: count, total order value, total actual, total remaining.
    summary = {
        "po_count":   len(rows),
        "order":      sum(r.order_amount    for r in rows),
        "actual":     sum(r.actual_amount   for r in rows),
        "remaining":  sum(r.remaining_amount for r in rows),
    }

    return templates.TemplateResponse("project_purchase_orders.html", {
        "request": request,
        "project": project,
        "totals": totals,
        "purchase_orders": rows,
        "summary": summary,
        "active_tab": "purchase_orders",
    })


def _get_package(db: Session, project_number: str, package_number: str) -> Package:
    pkg = db.query(Package).filter_by(package_number=package_number, project_number=project_number).first()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


def _package_detail_response(request: Request, db: Session, project_number: str, package_number: str, active_pkg_tab: str):
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    pkg = _get_package(db, project_number, package_number)
    totals = _project_totals(db, project_number)

    root_nodes = [n for n in pkg.cost_nodes if n.parent_id is None]
    cost_rows = _flatten_cost_nodes(root_nodes)

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
        "active_tab": "packages",
        "active_pkg_tab": active_pkg_tab,
    })


@app.get("/project/{project_number}/packages/{package_number}/scope")
def package_scope(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "scope")


@app.get("/project/{project_number}/packages/{package_number}/schedule")
def package_schedule(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "schedule")


@app.get("/project/{project_number}/packages/{package_number}/cost")
def package_cost(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "cost")


@app.get("/project/{project_number}/packages/{package_number}/deliverables")
def package_deliverables(project_number: str, package_number: str, request: Request, db: DbDep):
    return _package_detail_response(request, db, project_number, package_number, "deliverables")


@app.get("/project/{project_number}/packages/{package_number}")
def package_detail(project_number: str, package_number: str, request: Request, db: DbDep):
    # Default tab is Cost — Scope/Schedule/Deliverables are hidden from the UI
    # for the cost-control-focused MVP. Their routes still exist but are
    # unreachable without typing the URL by hand.
    return _package_detail_response(request, db, project_number, package_number, "cost")


# ---------------------------------------------------------------------------
# Cost node CRUD routes
# ---------------------------------------------------------------------------

def _cost_redirect(project_number: str, package_number: str):
    return RedirectResponse(
        f"/project/{project_number}/packages/{package_number}/cost",
        status_code=303,
    )


def _parse_float(val: str) -> float | None:
    try:
        v = float(val)
        return v
    except (ValueError, TypeError):
        return None


def _next_sibling_order(pkg, parent_id: int | None) -> int:
    siblings = [n for n in pkg.cost_nodes if n.parent_id == parent_id]
    return max((n.display_order for n in siblings), default=-1) + 1


def _resolve_parent_id(db: Session, pkg, parent_id_str: str) -> int | None:
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
    if parent is None or parent.package_id != pkg.id:
        raise HTTPException(status_code=400, detail="Parent must belong to the same package")
    return parent_int


@app.post("/project/{project_number}/packages/{package_number}/cost/add-section")
def cost_add_section(
    project_number: str,
    package_number: str,
    db: DbDep,
    code: str = Form(""),
    description: str = Form(...),
    parent_id: str = Form(""),
):
    pkg = _get_package(db, project_number, package_number)
    parent_int = _resolve_parent_id(db, pkg, parent_id)
    node = PackageCostNode(
        package_id=pkg.id,
        parent_id=parent_int,
        code=code.strip(),
        description=description.strip(),
        is_item=False,
        display_order=_next_sibling_order(pkg, parent_int),
    )
    db.add(node)
    db.commit()
    return _cost_redirect(project_number, package_number)


@app.post("/project/{project_number}/packages/{package_number}/cost/update-section/{node_id}")
def cost_update_section(
    project_number: str,
    package_number: str,
    node_id: int,
    db: DbDep,
    code: str = Form(""),
    description: str = Form(...),
):
    pkg = _get_package(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    node.code = code.strip()
    node.description = description.strip()
    db.commit()
    return _cost_redirect(project_number, package_number)


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


def _process_col(unit_str: str, qty_str: str, rate_str: str, amount_str: str):
    """Return (unit, qty, rate, computed_amount) for one cost column.

    Blank Sum/P.Sum amounts return None (not 0.0) so the template can render a
    `—` placeholder consistently across all three columns. Rollups already
    coalesce None to 0.0 via `getattr(n, col) or 0.0`.
    """
    unit = unit_str.strip() or "Sum"
    if unit in ("Sum", "P.Sum"):
        return unit, None, None, _parse_float(amount_str)
    qty = _parse_float(qty_str)
    rate = _parse_float(rate_str)
    return unit, qty, rate, (qty or 0.0) * (rate or 0.0)


@app.post("/project/{project_number}/packages/{package_number}/cost/add-item")
def cost_add_item(
    project_number: str,
    package_number: str,
    db: DbDep,
    code: str = Form(""),
    description: str = Form(...),
    parent_id: str = Form(""),
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
    pkg = _get_package(db, project_number, package_number)
    parent_int = _resolve_parent_id(db, pkg, parent_id)
    bl_u, bl_q, bl_r, bl_a = _process_col(baseline_unit, baseline_qty, baseline_rate, baseline_amount)
    pa_u, pa_q, pa_r, pa_a = _process_col(pre_award_unit, pre_award_qty, pre_award_rate, pre_award_amount)
    ct_u, ct_q, ct_r, ct_a = _process_col(contract_unit, contract_qty, contract_rate, contract_amount)
    node = PackageCostNode(
        package_id=pkg.id,
        parent_id=parent_int,
        code=code.strip(),
        description=description.strip(),
        is_item=True,
        cc_code=cc_code.strip() or None,
        unit=bl_u, qty=bl_q, rate=bl_r, baseline_amount=bl_a,
        pre_award_unit=pa_u, pre_award_qty=pa_q, pre_award_rate=pa_r, pre_award_amount=pa_a,
        contract_unit=ct_u, contract_qty=ct_q, contract_rate=ct_r, contract_amount=ct_a or None,
        display_order=_next_sibling_order(pkg, parent_int),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    _write_audit_log(db, node, "Created")
    return _cost_redirect(project_number, package_number)


@app.post("/project/{project_number}/packages/{package_number}/cost/update-item/{node_id}")
def cost_update_item(
    project_number: str,
    package_number: str,
    node_id: int,
    db: DbDep,
    code: str = Form(""),
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
    pkg = _get_package(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    bl_u, bl_q, bl_r, bl_a = _process_col(baseline_unit, baseline_qty, baseline_rate, baseline_amount)
    pa_u, pa_q, pa_r, pa_a = _process_col(pre_award_unit, pre_award_qty, pre_award_rate, pre_award_amount)
    ct_u, ct_q, ct_r, ct_a = _process_col(contract_unit, contract_qty, contract_rate, contract_amount)
    node.code = code.strip()
    node.description = description.strip()
    node.cc_code = cc_code.strip() or None
    node.unit = bl_u;       node.qty = bl_q;       node.rate = bl_r;       node.baseline_amount = bl_a
    node.pre_award_unit=pa_u; node.pre_award_qty=pa_q; node.pre_award_rate=pa_r; node.pre_award_amount=pa_a
    node.contract_unit=ct_u;  node.contract_qty=ct_q;  node.contract_rate=ct_r
    node.contract_amount = ct_a or None
    db.commit()
    _write_audit_log(db, node, "Updated")
    return _cost_redirect(project_number, package_number)


@app.post("/project/{project_number}/packages/{package_number}/cost/set-contract/{node_id}")
def cost_set_contract(
    project_number: str,
    package_number: str,
    node_id: int,
    db: DbDep,
    contract_amount: str = Form(""),
):
    pkg = _get_package(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    node.contract_amount = _parse_float(contract_amount)
    db.commit()
    _write_audit_log(db, node, "Updated")
    return _cost_redirect(project_number, package_number)


@app.post("/project/{project_number}/packages/{package_number}/cost/award")
def cost_award(project_number: str, package_number: str, db: DbDep):
    pkg = _get_package(db, project_number, package_number)
    pkg.is_contracted = True
    db.commit()
    return _cost_redirect(project_number, package_number)


@app.post("/project/{project_number}/packages/{package_number}/cost/delete-node/{node_id}")
def cost_delete_node(project_number: str, package_number: str, node_id: int, db: DbDep):
    pkg = _get_package(db, project_number, package_number)
    node = db.get(PackageCostNode, node_id)
    if node is None or node.package_id != pkg.id:
        raise HTTPException(status_code=404, detail="Cost node not found")
    db.delete(node)
    db.commit()
    return _cost_redirect(project_number, package_number)


@app.get("/import")
def import_page(request: Request, db: DbDep, msg: str = "", error: str = ""):
    batches = (
        db.query(ImportBatch)
        .order_by(ImportBatch.imported_at.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse("import.html", {
        "request": request,
        "batches": batches,
        "msg": msg,
        "error": error,
    })


@app.post("/import/run")
def do_import(
    request: Request,
    db: DbDep,
    files: list[UploadFile] = File(...),
):
    try:
        if not files or not any(f.filename for f in files):
            raise ValueError("No files selected.")
        file_data = [(f.filename, f.file.read()) for f in files]
        batch = run_import(db, file_data)
        return RedirectResponse(
            f"/import?msg=Import+complete:+{batch.row_count}+transactions+loaded",
            status_code=303,
        )
    except Exception as exc:
        from urllib.parse import quote_plus
        return RedirectResponse(
            f"/import?error={quote_plus(str(exc))}",
            status_code=303,
        )


@app.get("/project/{project_number}/export/csv")
def export_project_csv(project_number: str, db: DbDep):
    """C-20 — per-project CSV export. Same shape as /export/csv but scoped."""
    project = db.query(Project).filter_by(project_number=project_number).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = db.execute(
        text("""
            SELECT
                t.date,
                t.source,
                t.document_number,
                t.vendor_name,
                t.po_number,
                t.po_description,
                t.project_task_name,
                t.derived_cc_code,
                t.derived_cc_name,
                t.account_full_name,
                t.fiscal_year,
                t.actual_cost,
                t.committed_cost,
                t.total_cost
            FROM transactions t
            WHERE t.project_number = :proj
            ORDER BY t.date, t.document_number
        """),
        {"proj": project_number},
    ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Date", "Source", "Document Number", "Vendor", "PO Number",
        "PO Description", "Task", "CC Code", "CC Name",
        "Account Full Name", "Fiscal Year",
        "Actual Cost", "Committed Cost", "Total Cost",
    ])
    for r in rows:
        writer.writerow([
            r.date, r.source, r.document_number, r.vendor_name, r.po_number,
            r.po_description, r.project_task_name, r.derived_cc_code, r.derived_cc_name,
            r.account_full_name, r.fiscal_year,
            f"{r.actual_cost:.2f}", f"{r.committed_cost:.2f}", f"{r.total_cost:.2f}",
        ])

    buf.seek(0)
    safe_proj = project_number.replace("/", "_")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=project_{safe_proj}.csv"},
    )


@app.get("/export/csv")
def export_csv(db: DbDep):
    rows = db.execute(
        text("""
            SELECT
                t.project_number,
                p.project_name,
                SUM(t.actual_cost)    AS actual,
                SUM(t.committed_cost) AS committed,
                SUM(t.total_cost)     AS total
            FROM transactions t
            JOIN projects p ON p.project_number = t.project_number
            GROUP BY t.project_number, p.project_name
            ORDER BY t.project_number
        """)
    ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Project Number", "Project Name", "Actual Cost", "Committed Cost", "Total Cost"])
    for row in rows:
        writer.writerow([
            row.project_number,
            row.project_name,
            f"{row.actual:.2f}",
            f"{row.committed:.2f}",
            f"{row.total:.2f}",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cost_control.csv"},
    )


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8090, reload=False)
