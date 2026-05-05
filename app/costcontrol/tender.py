"""Tender helpers — number generation and status-transition rules.

Mirrors the structure of costcontrol/rto.py — small isolated module so
business rules sit in one place outside of HTTP plumbing.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Package, Tender


# Status workflow for a Tender. Slice C only exercises Draft / Issued /
# Closed / Cancelled — Adjudicating + Awarded are introduced in later
# slices and added to ALLOWED_TRANSITIONS at that time.
STATUS_DRAFT        = "Draft"
STATUS_ISSUED       = "Issued"
STATUS_CLOSED       = "Closed"
STATUS_ADJUDICATING = "Adjudicating"
STATUS_AWARDED      = "Awarded"
STATUS_CANCELLED    = "Cancelled"

ALL_STATUSES = (
    STATUS_DRAFT, STATUS_ISSUED, STATUS_CLOSED,
    STATUS_ADJUDICATING, STATUS_AWARDED, STATUS_CANCELLED,
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_DRAFT:        {STATUS_ISSUED, STATUS_CANCELLED},
    STATUS_ISSUED:       {STATUS_CLOSED, STATUS_DRAFT, STATUS_CANCELLED},
    STATUS_CLOSED:       {STATUS_ADJUDICATING, STATUS_ISSUED, STATUS_CANCELLED},
    STATUS_ADJUDICATING: {STATUS_AWARDED, STATUS_CLOSED, STATUS_CANCELLED},
    # STATUS_AWARDED is reached automatically when a bidder is marked Awarded
    # via the Adjudication UI in Slice E. v1 has no manual user transition
    # back out of Awarded — to undo, the user re-marks a different bidder.
    STATUS_AWARDED:      set(),
    STATUS_CANCELLED:    set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def can_delete(status: str) -> bool:
    """Delete is only allowed for Draft and Cancelled tenders. Once a
    tender has been Issued (bidders may have submitted), deletion is
    blocked — cancel it first to preserve the audit trail."""
    return status in (STATUS_DRAFT, STATUS_CANCELLED)


# Bidder status values — pre-adjudication subset used in Slice C.
BIDDER_STATUSES = (
    "Pending", "Submitted", "Withdrawn", "Disqualified",
    "Shortlisted", "Awarded",
)


_TENDER_SUFFIX_RE = re.compile(r"\.TND\.(\d+)$")


def next_tender_number(db: Session, package_number: str, package_id: int) -> str:
    """Generate the next tender number for a package: {package}.TND.NNN
    where NNN is the highest existing trailing-digit suffix + 1."""
    rows = db.execute(
        select(Tender.tender_number).where(Tender.package_id == package_id)
    ).all()
    max_n = 0
    for (tender_number,) in rows:
        m = _TENDER_SUFFIX_RE.search(tender_number)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"{package_number}.TND.{max_n + 1:03d}"


def weighted_score(scores_by_criterion: dict[int, float], weights_by_criterion: dict[int, float]) -> float | None:
    """Compute a weighted-average score across criteria for one bidder.

    `scores_by_criterion` maps criterion_id -> raw score (0-100).
    `weights_by_criterion` maps criterion_id -> weight.

    Returns None if no scored criteria, otherwise sum(score*weight) /
    sum(weight). Criteria with no score for this bidder are excluded
    from BOTH the numerator and denominator so the user can leave a
    cell blank without it dragging the total to zero.
    """
    num = 0.0
    den = 0.0
    for cid, score in scores_by_criterion.items():
        w = weights_by_criterion.get(cid, 0)
        if w <= 0:
            continue
        num += float(score) * float(w)
        den += float(w)
    return num / den if den > 0 else None
