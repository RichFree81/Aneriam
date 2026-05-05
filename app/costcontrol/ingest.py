"""
Import pipeline: read NetSuite SpreadsheetML exports, apply R1–R4, persist to SQLite.

Full-replace strategy: every import truncates `transactions` and reloads.
Import batches history is retained so every transaction is traceable.
"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path

from lxml import etree
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import CAPITALISATION_ACCOUNT_KEYWORDS
from .models import (
    ControlAccount, GLLine, ImportBatch, JournalLine,
    ProjectTask, PurchaseOrderLine, Transaction,
)
from .seed import upsert_project

_NS = "urn:schemas-microsoft-com:office:spreadsheet"
_SS = f"{{{_NS}}}"

# NetSuite export file prefixes (case-insensitive stem match)
_PROJECTS_FILE_PREFIX        = "pmoprojectsreport"
_TASKS_FILE_PREFIX           = "pmoprojecttasksresults"
_VB_SUMMARY_PREFIX           = "pmovendorbillssummaryresults"
_PO_SUMMARY_PREFIX           = "pmopurchaseorderssummaryresults"
_PO_DETAIL_PREFIX            = "pmopurchaseordersdetailedresults"
_VB_DETAIL_PREFIX            = "pmovendorbillsdetailedresults"
# C-10 / C-11 — new pipes added 2026-05-04
_JOURNALS_DETAIL_PREFIX      = "pmojournalentriesdetailedresults"
_PROJECT_GL_DETAIL_PREFIX    = "pmoprojectgldetailedresults"


# ---------------------------------------------------------------------------
# SpreadsheetML parser
# ---------------------------------------------------------------------------

def _parse_cell(cell) -> str:
    data = cell.find(f"{_SS}Data")
    return (data.text or "").strip() if data is not None else ""


def _parse_rows(content: bytes) -> list[list[str]]:
    parser = etree.XMLParser(recover=True)
    root = etree.fromstring(content, parser)
    sheets = root.findall(f".//{_SS}Worksheet")
    if not sheets:
        return []
    table = sheets[0].find(f"{_SS}Table")
    if table is None:
        return []
    result = []
    for row_el in table.findall(f"{_SS}Row"):
        cells: dict[int, str] = {}
        col = 0
        for cell in row_el.findall(f"{_SS}Cell"):
            idx_attr = cell.get(f"{_SS}Index")
            if idx_attr is not None:
                col = int(idx_attr) - 1
            cells[col] = _parse_cell(cell)
            col += 1
        if not cells:
            result.append([])
            continue
        max_col = max(cells.keys())
        result.append([cells.get(i, "") for i in range(max_col + 1)])
    return result


def _find_header_row(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        if row and row[0] == "Transaction: Date":
            return i
    raise ValueError("Header row 'Transaction: Date' not found in file.")


# ---------------------------------------------------------------------------
# Transformation rules (R1–R4)
# ---------------------------------------------------------------------------

def _derive_cc_code(task_name: str, activity_code: str) -> str:
    """Rule 1: derive the 3-char control account code from NetSuite fields."""
    task = task_name.strip()
    if task:
        return task[:3]
    activity = activity_code.strip()
    # Activity prefix pattern: 4 digits followed by ":"
    if len(activity) >= 5 and activity[:4].isdigit() and activity[4] == ":":
        after_colon = activity[5:].strip()
        return after_colon[:3]
    return ""


def _is_capitalisation_row(account_full_name: str) -> bool:
    """C-13 — True if this row is a capitalisation/expensing reversal.

    Detection is by PMO Account: Account Full Name containing any of the
    configured CAPITALISATION_ACCOUNT_KEYWORDS (case-insensitive). The actual
    capitalisation amount is a NEGATIVE entry that nets WIP down to the
    final asset value; the app surfaces it as a separate metric so the
    Project Cost to Date figure stays gross.
    """
    s = (account_full_name or "").lower()
    return any(kw.lower() in s for kw in CAPITALISATION_ACCOUNT_KEYWORDS)


def _apply_rules(
    raw_actual: float,
    raw_committed: float,
    raw_cost: float,
    task_name: str,
    activity_code: str,
    ca_lookup: dict[str, ControlAccount],
) -> tuple[str, str, float, float, float]:
    """
    Apply R1, R2, R4. Returns (cc_code, cc_name, actual_cost, committed_cost, total_cost).

    C-13 (2026-05-04) — R3 (CapEx exclusion zeroing on codes 901/902) has
    been removed. Capitalisation is now detected by PMO Account name and
    surfaced as a separate metric in app.py rather than by zeroing
    actual/committed at row level. `actual_cost` and `committed_cost` always
    equal the raw values from PMO.
    """
    # R1 — derive code
    cc_code = _derive_cc_code(task_name, activity_code)

    # R2 — lookup name; miss → "Unallocated"
    ca = ca_lookup.get(cc_code)
    cc_name = ca.name if ca else "Unallocated"

    # R3 removed — actuals and committed pass through verbatim.
    actual_cost = raw_actual
    committed_cost = raw_committed

    # R4 — total
    total_cost = actual_cost + committed_cost

    return cc_code, cc_name, actual_cost, committed_cost, total_cost


# ---------------------------------------------------------------------------
# Date and numeric helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    # NetSuite format: 2024-04-01T00:00:00.000
    return datetime.fromisoformat(s.replace(".000", "")).date()


def _parse_date_safe(s: str) -> date | None:
    """Like _parse_date but returns None instead of raising on bad input."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return _parse_date(s)
    except (ValueError, AttributeError):
        return None


def _parse_datetime(s: str) -> datetime | None:
    """Parse a NetSuite datetime string (`2024-04-01T00:00:00.000` etc).
    Returns None on empty / unparseable input."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace(".000", ""))
    except (ValueError, AttributeError):
        return None


def _parse_amount(s: str) -> float:
    s = s.strip()
    return float(s) if s else 0.0


def _parse_int(s: str) -> int | None:
    """Parse an integer; return None on empty / unparseable input."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_bool_voided(status: str) -> bool:
    """Map a NetSuite Status string to a `voided` boolean. Status values like
    'Voided', 'Rejected by Approver' map to True; everything else False."""
    s = (status or "").strip().lower()
    return s in ("voided", "void", "rejected", "rejected by approver", "cancelled")


def _strip_id_prefix(s: str) -> str:
    """Strip leading NetSuite numeric ID prefix from name strings.
    e.g. '18 ALLIED FURNACE CONSULTANTS (PTY) LTD' → 'ALLIED FURNACE CONSULTANTS (PTY) LTD'"""
    s = (s or "").strip()
    if not s:
        return s
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].strip()
    return s


# ---------------------------------------------------------------------------
# Task hierarchy parser
# ---------------------------------------------------------------------------

def _parse_task_hierarchy(content: bytes) -> list[dict]:
    """Parse PMOProjectTasksResults file into ProjectTask records.

    The 'Name' column holds the full colon-separated path, e.g.:
        '102 - EPCM : 102.01 - Project Development Costs : 102.01.1 - Civil FEED'
    The last segment is the leaf_name, which matches Transaction.project_task_name.

    C-9 (2026-05-04) — also reads `Status`, `Parent Task`, `Date Created`,
    `Last Modified` for the new project_tasks columns. Note: the actual export
    column is plain `Status` (not `Project : Status` as the spec text says).
    """
    rows = _parse_rows(content)
    if not rows:
        return []

    # Find the header row
    header_idx = next((i for i, r in enumerate(rows) if r and r[0] == "Internal ID"), None)
    if header_idx is None:
        return []

    col = {h.strip(): i for i, h in enumerate(rows[header_idx])}
    records = []
    for row in rows[header_idx + 1:]:
        if not row or not any(row):
            continue
        full_name   = row[col["Name"]].strip() if "Name" in col else ""
        proj_num    = row[col["Project Number"]].strip() if "Project Number" in col else ""
        task_id_str = row[col["Internal ID"]].strip() if "Internal ID" in col else "0"
        if not full_name or not proj_num:
            continue

        parts   = full_name.split(" : ")
        level1  = parts[0]
        level2  = parts[1] if len(parts) >= 2 else None
        level3  = parts[2] if len(parts) >= 3 else None
        leaf    = parts[-1]

        try:
            task_id = int(task_id_str)
        except ValueError:
            task_id = 0

        # C-9 — new columns
        project_status = row[col["Status"]].strip() if "Status" in col else ""
        parent_task_raw = row[col["Parent Task"]].strip() if "Parent Task" in col else ""
        date_created_raw = row[col["Date Created"]].strip() if "Date Created" in col else ""
        last_modified_raw = row[col["Last Modified"]].strip() if "Last Modified" in col else ""

        # Parent Task is a name reference, not an integer ID — we don't have
        # the parent's Internal ID in this export. Store None for now; the
        # column is reserved for a future enhancement that joins on name.
        parent_task_id = None

        date_created = _parse_datetime(date_created_raw) if date_created_raw else None
        last_modified = _parse_datetime(last_modified_raw) if last_modified_raw else None

        records.append(dict(
            task_id=task_id,
            project_number=proj_num,
            full_name=full_name,
            leaf_name=leaf,
            level1=level1,
            level2=level2,
            level3=level3,
            project_status=project_status,
            parent_task_id=parent_task_id,
            date_created=date_created,
            last_modified=last_modified,
        ))
    return records


# ---------------------------------------------------------------------------
# Vendor / PO lookup helpers
# ---------------------------------------------------------------------------

def _parse_vb_summary(content: bytes) -> dict[str, tuple[str, str]]:
    """Parse PMOVendorBillsSummaryResults.  Returns {invoice_number: (vendor_name, po_number)}."""
    rows = _parse_rows(content)
    if len(rows) < 2:
        return {}
    col = {h.strip(): i for i, h in enumerate(rows[0])}
    lookup: dict[str, tuple[str, str]] = {}
    for row in rows[1:]:
        if not row or not any(row):
            continue
        inv = row[col["Invoice Number"]].strip() if "Invoice Number" in col else ""
        po_raw = row[col["PO Number"]].strip() if "PO Number" in col else ""
        vendor = row[col["Name"]].strip() if "Name" in col else ""
        if not inv or inv in lookup:
            continue
        po = "" if po_raw in ("- None -", "-", "") else po_raw
        lookup[inv] = (vendor, po)
    return lookup


def _parse_po_summary(content: bytes) -> dict[str, tuple[str, str]]:
    """Parse PMOPurchaseOrdersSummaryResults.  Returns {po_number: (vendor_name, memo)}."""
    rows = _parse_rows(content)
    if len(rows) < 2:
        return {}
    col = {h.strip(): i for i, h in enumerate(rows[0])}
    lookup: dict[str, tuple[str, str]] = {}
    for row in rows[1:]:
        if not row or not any(row):
            continue
        po = row[col["Document Number"]].strip() if "Document Number" in col else ""
        vendor = row[col["Name"]].strip() if "Name" in col else ""
        memo = row[col["Memo (Main)"]].strip() if "Memo (Main)" in col else ""
        if po and po not in lookup:
            lookup[po] = (vendor, memo)
    return lookup


def _parse_po_detail(content: bytes) -> list[dict]:
    """Parse PMOPurchaseOrdersDetailedResults (NetSuite saved search id=633).

    C-8 (2026-05-04) — reads the new columns: Internal ID, Remaining, Actual,
    Date, plus vendor (sourced from `Main Line Name`). The `voided` flag is
    derived from Status — there is no explicit Voided column on PO Detailed.

    The historical `name` field maps to `Project Task Name` under the new
    column layout (the old plain `Name` column no longer exists). This is
    used by C-7 as the per-line discriminator when joining bills→POs.

    Returns list of dicts ready for PurchaseOrderLine(**rec).
    """
    rows = _parse_rows(content)
    if len(rows) < 2:
        return []
    col = {h.strip(): i for i, h in enumerate(rows[0])}
    records = []
    for row in rows[1:]:
        if not row or not any(row):
            continue
        po       = row[col["Document Number"]].strip()    if "Document Number"    in col else ""
        proj     = row[col["Project Number"]].strip()     if "Project Number"     in col else ""
        m_main   = row[col["Memo (Main)"]].strip()        if "Memo (Main)"        in col else ""
        memo     = row[col["Memo"]].strip()               if "Memo"               in col else ""
        # C-8: map `name` to Project Task Name under the new layout.
        name     = row[col["Project Task Name"]].strip()  if "Project Task Name"  in col else ""
        status   = row[col["Status"]].strip()             if "Status"             in col else ""
        # New columns
        internal_id = _parse_int(row[col["Internal ID"]]) if "Internal ID" in col else None
        try:
            amount = float(row[col["Amount"]]) if "Amount" in col and row[col["Amount"]] else 0.0
        except (ValueError, IndexError):
            amount = 0.0
        try:
            remaining = float(row[col["Remaining"]]) if "Remaining" in col and row[col["Remaining"]] else 0.0
        except (ValueError, IndexError):
            remaining = 0.0
        try:
            actual = float(row[col["Actual"]]) if "Actual" in col and row[col["Actual"]] else 0.0
        except (ValueError, IndexError):
            actual = 0.0
        # Vendor: PO Detailed names this column `Main Line Name`. Strip leading
        # NetSuite ID prefix ("18 ALLIED FURNACE..." → "ALLIED FURNACE...").
        vendor_raw = row[col["Main Line Name"]].strip() if "Main Line Name" in col else ""
        vendor = _strip_id_prefix(vendor_raw)
        # Date
        po_date = _parse_date_safe(row[col["Date"]]) if "Date" in col else None
        # Voided derived from Status — no explicit Voided column under new layout.
        voided = _parse_bool_voided(status)

        if not po:
            continue
        records.append(dict(
            po_number=po, project_number=proj,
            memo_main=m_main, memo=memo, name=name,
            amount=amount, status=status,
            # C-8 additions
            internal_id=internal_id,
            remaining=remaining,
            actual=actual,
            vendor=vendor,
            date=po_date,
            voided=voided,
        ))
    return records


def _parse_vb_detail_actuals(content: bytes) -> dict[tuple[str, str, str], float]:
    """Parse PMOVendorBillsDetailedResults.

    C-6 (2026-05-04) — uses named-column lookup (the previous positional
    indexing broke when NetSuite added Internal ID at column 0).
    C-7 (2026-05-04) — keys on (PO Number, Project Number, PO Memo) where
    `PO Memo` is the bill's reference to the originating PO line's memo.
    This matches PO Detailed lines at line granularity. Project Task Name was
    initially considered but proved too coarse — multiple PO lines often share
    a task path, causing fan-out duplication of bill amounts.

    Returns {(po_number, project_number, po_memo): total_actual}.
    """
    rows = _parse_rows(content)
    if len(rows) < 2:
        return {}
    col = {h.strip(): i for i, h in enumerate(rows[0])}
    if "PO Number" not in col:
        # New layout missing — return empty, caller treats as no actuals.
        return {}
    lookup: dict[tuple[str, str, str], float] = {}
    for row in rows[1:]:
        if not row or not any(row):
            continue
        po   = row[col["PO Number"]].strip()      if "PO Number"      in col else ""
        proj = row[col["Project Number"]].strip() if "Project Number" in col else ""
        # `PO Memo` carries the originating PO line's per-line memo — matches
        # PurchaseOrderLine.memo. The bill's own `Memo` is a different field
        # (free-text bill memo) and must NOT be substituted: bills with blank
        # `PO Memo` aggregate under the empty-memo bucket alongside PO lines
        # whose own memo is empty.
        po_memo = row[col["PO Memo"]].strip() if "PO Memo" in col else ""
        if not po:
            continue
        try:
            amt_str = row[col["Amount"]] if "Amount" in col else ""
            amt = float(amt_str) if amt_str else 0.0
        except (ValueError, IndexError):
            amt = 0.0
        # Skip voided bills (Status column may be e.g. 'Voided')
        status = row[col["Status"]].strip() if "Status" in col else ""
        if _parse_bool_voided(status):
            continue
        key = (po, proj, po_memo)
        lookup[key] = lookup.get(key, 0.0) + amt
    return lookup


# ---------------------------------------------------------------------------
# Journals Detailed (id=790) — C-10
# ---------------------------------------------------------------------------

def _parse_journals(content: bytes) -> list[dict]:
    """Parse PMOJournalEntriesDetailedResults — line-level posting journals.

    Returns list of dicts ready for JournalLine(**rec, import_batch_id=...).
    """
    rows = _parse_rows(content)
    if len(rows) < 2:
        return []
    col = {h.strip(): i for i, h in enumerate(rows[0])}
    records: list[dict] = []
    for row in rows[1:]:
        if not row or not any(row):
            continue
        try:
            amt_str = row[col["Amount"]] if "Amount" in col else ""
            amount = float(amt_str) if amt_str else 0.0
        except (ValueError, IndexError):
            amount = 0.0
        status = row[col["Status"]].strip() if "Status" in col else ""
        records.append(dict(
            internal_id      = _parse_int(row[col["Internal ID"]]) if "Internal ID" in col else None,
            document_number  = row[col["Document Number"]].strip() if "Document Number" in col else "",
            project_number   = row[col["Project Number"]].strip()  if "Project Number"  in col else "",
            account_full_name = row[col["Account"]].strip()        if "Account"         in col else "",
            type             = row[col["Type"]].strip()            if "Type"            in col else "",
            memo_main        = row[col["Memo (Main)"]].strip()     if "Memo (Main)"     in col else "",
            memo             = row[col["Memo"]].strip()            if "Memo"            in col else "",
            date             = _parse_date_safe(row[col["Date"]])  if "Date"            in col else None,
            period           = row[col["Period"]].strip()          if "Period"          in col else "",
            amount           = amount,
            status           = status,
            approval_status  = row[col["Approval Status"]].strip() if "Approval Status" in col else "",
            voided           = _parse_bool_voided(status),
            created_date     = _parse_datetime(row[col["Date Created"]]) if "Date Created" in col else None,
            last_modified    = _parse_datetime(row[col["Last Modified"]]) if "Last Modified" in col else None,
            created_by       = row[col["Created By"]].strip()      if "Created By"      in col else "",
        ))
    return records


# ---------------------------------------------------------------------------
# Project GL Detailed (id=791) — C-11
# ---------------------------------------------------------------------------

def _parse_project_gl(content: bytes) -> list[dict]:
    """Parse PMOProjectGLDetailedResults — all project-tagged GL postings.

    Returns list of dicts ready for GLLine(**rec, import_batch_id=...).
    """
    rows = _parse_rows(content)
    if len(rows) < 2:
        return []
    col = {h.strip(): i for i, h in enumerate(rows[0])}
    records: list[dict] = []
    for row in rows[1:]:
        if not row or not any(row):
            continue
        try:
            amt_str = row[col["Amount"]] if "Amount" in col else ""
            amount = float(amt_str) if amt_str else 0.0
        except (ValueError, IndexError):
            amount = 0.0
        status = row[col["Status"]].strip() if "Status" in col else ""
        posting_raw = row[col["Posting"]].strip() if "Posting" in col else ""
        records.append(dict(
            internal_id      = _parse_int(row[col["Internal ID"]]) if "Internal ID" in col else None,
            document_number  = row[col["Document Number"]].strip() if "Document Number" in col else "",
            project_number   = row[col["Project Number"]].strip()  if "Project Number"  in col else "",
            account_full_name = row[col["Account"]].strip()        if "Account"         in col else "",
            type             = row[col["Type"]].strip()            if "Type"            in col else "",
            memo_main        = row[col["Memo (Main)"]].strip()     if "Memo (Main)"     in col else "",
            memo             = row[col["Memo"]].strip()            if "Memo"            in col else "",
            date             = _parse_date_safe(row[col["Date"]])  if "Date"            in col else None,
            period           = row[col["Period"]].strip()          if "Period"          in col else "",
            amount           = amount,
            status           = status,
            posting          = posting_raw.lower() in ("yes", "true", "1"),
            voided           = _parse_bool_voided(status),
        ))
    return records


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_import(db: Session, files: list[tuple[str, bytes]]) -> ImportBatch:
    """
    Full-replace import.  Truncates `transactions`, re-inserts from the
    supplied (filename, content) pairs.  Appends a new ImportBatch row.
    """
    if not files:
        raise ValueError("No files provided.")

    # Identify the Projects report file (must start with the known prefix)
    projects_entry = next(
        ((name, content) for name, content in files
         if Path(name).stem.lower().startswith(_PROJECTS_FILE_PREFIX)),
        None,
    )
    if projects_entry is None:
        raise FileNotFoundError(
            f"No file starting with '{_PROJECTS_FILE_PREFIX}' found in the uploaded files."
        )
    projects_filename, projects_content = projects_entry

    # Load CA lookup table (data-driven; never hardcode codes here)
    ca_lookup: dict[str, ControlAccount] = {
        ca.code: ca for ca in db.query(ControlAccount).all()
    }

    # Parse the projects report
    rows = _parse_rows(projects_content)
    header_idx = _find_header_row(rows)
    headers = rows[header_idx]
    data_rows = rows[header_idx + 1 :]

    # Map column names → indices (defensive: tolerate extra whitespace in headers)
    col = {h.strip(): i for i, h in enumerate(headers)}

    # Upsert projects discovered in the import.
    # Column name is `Project: Name` (with colon) under the new PMO 18-col layout.
    # Fall back to legacy `Project Name` for backward compatibility.
    proj_name_idx = col.get("Project: Name")
    if proj_name_idx is None:
        proj_name_idx = col.get("Project Name")

    seen_projects: set[str] = set()
    for row in data_rows:
        if not row or not any(row):
            continue
        proj_num = row[col["Project Number"]].strip()
        proj_name = row[proj_name_idx].strip() if proj_name_idx is not None else ""
        if proj_num and proj_num not in seen_projects:
            upsert_project(db, proj_num, proj_name)
            seen_projects.add(proj_num)
    db.flush()

    # Identify and parse the tasks hierarchy file (optional)
    tasks_entry = next(
        ((name, content) for name, content in files
         if Path(name).stem.lower().startswith(_TASKS_FILE_PREFIX)),
        None,
    )
    if tasks_entry is not None:
        _, tasks_content = tasks_entry
        task_records = _parse_task_hierarchy(tasks_content)
        # Upsert: update existing NetSuite tasks (matched by task_id + project_number),
        # insert new ones. Rows with task_id=0 are manually created — never touched
        # unless the NetSuite import contains the same full_name, in which case the
        # manual row is promoted (task_id updated) to prevent duplicate JOIN matches.
        existing: dict[tuple, ProjectTask] = {
            (t.task_id, t.project_number): t
            for t in db.query(ProjectTask).filter(ProjectTask.task_id != 0).all()
        }
        manual_by_full_name: dict[tuple, ProjectTask] = {
            (t.project_number, t.full_name): t
            for t in db.query(ProjectTask).filter(ProjectTask.task_id == 0).all()
        }
        seen: set[tuple] = set()
        for rec in task_records:
            key = (rec["task_id"], rec["project_number"])
            seen.add(key)
            if key in existing:
                t = existing[key]
                t.full_name      = rec["full_name"]
                t.leaf_name      = rec["leaf_name"]
                t.level1         = rec["level1"]
                t.level2         = rec["level2"]
                t.level3         = rec["level3"]
                # C-9 — also apply new columns on existing-task update
                t.project_status = rec["project_status"]
                t.parent_task_id = rec["parent_task_id"]
                t.date_created   = rec["date_created"]
                t.last_modified  = rec["last_modified"]
            else:
                promote_key = (rec["project_number"], rec["full_name"])
                if promote_key in manual_by_full_name:
                    # Manual placeholder matches a real NetSuite task — promote it
                    t = manual_by_full_name[promote_key]
                    t.task_id        = rec["task_id"]
                    t.leaf_name      = rec["leaf_name"]
                    t.level1         = rec["level1"]
                    t.level2         = rec["level2"]
                    t.level3         = rec["level3"]
                    # C-9 — apply new columns on promotion too
                    t.project_status = rec["project_status"]
                    t.parent_task_id = rec["parent_task_id"]
                    t.date_created   = rec["date_created"]
                    t.last_modified  = rec["last_modified"]
                else:
                    db.add(ProjectTask(**rec))
        # Remove NetSuite tasks that no longer exist in the file
        for key, t in existing.items():
            if key not in seen:
                db.delete(t)
        db.flush()

    # Build vendor / PO lookups from optional summary files
    vb_entry = next(
        ((n, c) for n, c in files if Path(n).stem.lower().startswith(_VB_SUMMARY_PREFIX)), None
    )
    vb_lookup: dict[str, tuple[str, str]] = _parse_vb_summary(vb_entry[1]) if vb_entry else {}

    po_entry = next(
        ((n, c) for n, c in files if Path(n).stem.lower().startswith(_PO_SUMMARY_PREFIX)), None
    )
    po_lookup: dict[str, tuple[str, str]] = _parse_po_summary(po_entry[1]) if po_entry else {}

    # Load and store PO detail lines (full replace), enriched with per-line actuals
    po_detail_entry = next(
        ((n, c) for n, c in files if Path(n).stem.lower().startswith(_PO_DETAIL_PREFIX)), None
    )
    if po_detail_entry is not None:
        vb_detail_entry = next(
            ((n, c) for n, c in files if Path(n).stem.lower().startswith(_VB_DETAIL_PREFIX)), None
        )
        # C-7 — vb_actuals key is (PO Number, Project Number, PO Memo).
        vb_actuals: dict[tuple[str, str, str], float] = (
            _parse_vb_detail_actuals(vb_detail_entry[1]) if vb_detail_entry else {}
        )
        db.execute(text("DELETE FROM po_lines"))
        for rec in _parse_po_detail(po_detail_entry[1]):
            # C-7 — match bills to PO line by (PO, Project, Memo). Bills carry
            # the originating PO's per-line memo as `PO Memo`, which matches
            # PO Detailed `Memo`. Per-line, not per-task.
            actual_from_bills = vb_actuals.get(
                (rec["po_number"], rec["project_number"], rec["memo"]),
                0.0,
            )
            rec["actual_amount"] = actual_from_bills
            db.add(PurchaseOrderLine(**rec))
        db.flush()

    # C-10 — Journals Detailed
    journals_entry = next(
        ((n, c) for n, c in files if Path(n).stem.lower().startswith(_JOURNALS_DETAIL_PREFIX)),
        None,
    )

    # C-11 — Project GL Detailed
    project_gl_entry = next(
        ((n, c) for n, c in files if Path(n).stem.lower().startswith(_PROJECT_GL_DETAIL_PREFIX)),
        None,
    )

    # Full replace: truncate transactions
    db.execute(text("DELETE FROM transactions"))

    # Build a new import batch (insert first to get the id)
    batch = ImportBatch(
        imported_at=datetime.utcnow(),
        source_files=json.dumps([name for name, _ in files]),
        row_count=0,
    )
    db.add(batch)
    db.flush()  # gives us batch.id

    # Insert transformed transactions
    inserted = 0
    for row_offset, row in enumerate(data_rows):
        if not row or not any(row):
            continue

        proj_num = row[col["Project Number"]].strip()
        if not proj_num:
            continue

        raw_actual = _parse_amount(row[col["Actual Cost"]])
        raw_committed = _parse_amount(row[col["Committed Cost"]])
        raw_cost = _parse_amount(row[col["Cost"]])
        task_name = row[col["Project Task: Name"]]
        activity_code = row[col["Activity Code: Name"]]
        source_val = row[col["Transaction / Source"]]
        doc_num = row[col["Transaction: Document Number"]]

        # C-5 — new PMO columns (account name, fiscal year/quarter, dates).
        account_full_name = row[col["Account: Account Full Name"]].strip() if "Account: Account Full Name" in col else ""
        fiscal_year       = row[col["Fiscal Year"]].strip()                if "Fiscal Year"                in col else ""
        fiscal_quarter    = row[col["Fiscal Quarter"]].strip()             if "Fiscal Quarter"             in col else ""
        txn_date_created  = _parse_date_safe(row[col["Transaction: Date Created"]]) if "Transaction: Date Created" in col else None
        txn_date_closed   = _parse_date_safe(row[col["Transaction: Date Closed"]])  if "Transaction: Date Closed"  in col else None
        # C-5 — vendor sourced from PMO `Vendor` column directly. Falls back
        # to the Bills Summary lookup for journal rows where PMO Vendor is blank.
        pmo_vendor = row[col["Vendor"]].strip() if "Vendor" in col else ""

        cc_code, cc_name, actual_cost, committed_cost, total_cost = _apply_rules(
            raw_actual, raw_committed, raw_cost, task_name, activity_code, ca_lookup
        )

        # Derive vendor, linked PO, and PO description.
        # C-5 — primary source for vendor is PMO `Vendor` column. Bills Summary
        # is now a fallback only (used when PMO has no vendor, e.g. journals).
        src_lower = source_val.lower()
        if "bill" in src_lower or "invoice" in src_lower:
            vb_info = vb_lookup.get(doc_num, ("", ""))
            vendor_name = pmo_vendor or vb_info[0]
            po_number   = vb_info[1]
            po_description = po_lookup.get(po_number, ("", ""))[1] if po_number else ""
        elif "purchase order" in src_lower:
            po_info = po_lookup.get(doc_num, ("", ""))
            vendor_name    = pmo_vendor or po_info[0]
            po_description = po_info[1]
            po_number      = doc_num
        else:
            # Journals & other — PMO Vendor likely empty. Fall back to Bills
            # Summary lookup (C-18: this is the only remaining use of vb_lookup).
            vb_info = vb_lookup.get(doc_num, ("", ""))
            vendor_name    = pmo_vendor or vb_info[0]
            po_number      = vb_info[1]
            po_description = po_lookup.get(po_number, ("", ""))[1] if po_number else ""

        txn = Transaction(
            date=_parse_date(row[col["Transaction: Date"]]),
            project_number=proj_num,
            project_task_name=task_name,
            activity_code_name=activity_code,
            source=source_val,
            document_number=doc_num,
            vendor_name=vendor_name,
            po_number=po_number,
            po_description=po_description,
            netsuite_actual=raw_actual,
            netsuite_committed=raw_committed,
            netsuite_cost=raw_cost,
            account_full_name=account_full_name,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            transaction_date_created=txn_date_created,
            transaction_date_closed=txn_date_closed,
            derived_cc_code=cc_code,
            derived_cc_name=cc_name,
            actual_cost=actual_cost,
            committed_cost=committed_cost,
            total_cost=total_cost,
            import_batch_id=batch.id,
            source_file=projects_filename,
            source_row=header_idx + 1 + row_offset + 1,
        )
        db.add(txn)
        inserted += 1

    if journals_entry is not None:
        db.execute(text("DELETE FROM journal_lines"))
        for rec in _parse_journals(journals_entry[1]):
            db.add(JournalLine(import_batch_id=batch.id, **rec))

    if project_gl_entry is not None:
        db.execute(text("DELETE FROM gl_lines"))
        for rec in _parse_project_gl(project_gl_entry[1]):
            db.add(GLLine(import_batch_id=batch.id, **rec))

    batch.row_count = inserted
    db.commit()
    return batch
