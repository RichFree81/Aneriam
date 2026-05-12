"""CSV export helpers for project and portfolio cost data."""
from __future__ import annotations

import csv
import io

from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session


def _csv_response(filename: str, rows: list[list[object]]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def project_transactions_csv(db: Session, project_number: str) -> StreamingResponse:
    """Return a transaction-level CSV export for one project."""
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

    csv_rows: list[list[object]] = [[
        "Date", "Source", "Document Number", "Vendor", "PO Number",
        "PO Description", "Task", "CC Code", "CC Name",
        "Account Full Name", "Fiscal Year",
        "Actual Cost", "Committed Cost", "Total Cost",
    ]]
    csv_rows.extend([
        [
            r.date, r.source, r.document_number, r.vendor_name, r.po_number,
            r.po_description, r.project_task_name, r.derived_cc_code, r.derived_cc_name,
            r.account_full_name, r.fiscal_year,
            f"{r.actual_cost:.2f}", f"{r.committed_cost:.2f}", f"{r.total_cost:.2f}",
        ]
        for r in rows
    ])

    safe_proj = project_number.replace("/", "_")
    return _csv_response(f"project_{safe_proj}.csv", csv_rows)


def portfolio_summary_csv(db: Session) -> StreamingResponse:
    """Return a portfolio-level cost summary CSV export."""
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

    csv_rows: list[list[object]] = [[
        "Project Number", "Project Name", "Actual Cost", "Committed Cost", "Total Cost",
    ]]
    csv_rows.extend([
        [
            row.project_number,
            row.project_name,
            f"{row.actual:.2f}",
            f"{row.committed:.2f}",
            f"{row.total:.2f}",
        ]
        for row in rows
    ])

    return _csv_response("cost_control.csv", csv_rows)
