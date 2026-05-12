"""Shared cost reporting queries."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .capitalisation import IS_CAP_SQL, NOT_CAP_SQL


def project_totals(db: Session, project_number: str):
    """Return the project summary cost split used by project-level tabs."""
    return db.execute(
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
