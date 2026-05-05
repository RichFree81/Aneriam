"""RTO helpers — number generation and status-transition rules.

Kept separate from app.py so the routes file stays focused on HTTP
plumbing while business rules sit somewhere small and testable.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RTO


# Status workflow constants (see RTO_SPEC.md §7).
STATUS_DRAFT       = "Draft"
STATUS_SUBMITTED   = "Submitted"
STATUS_APPROVED    = "Approved"
STATUS_ISSUED      = "Issued for PO"
STATUS_CANCELLED   = "Cancelled"

ALL_STATUSES = (STATUS_DRAFT, STATUS_SUBMITTED, STATUS_APPROVED, STATUS_ISSUED, STATUS_CANCELLED)

# Allowed transitions: source_status -> set of valid targets. v1 has a single
# operator so we don't gate by user role, only by current state.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_DRAFT:     {STATUS_SUBMITTED, STATUS_CANCELLED},
    STATUS_SUBMITTED: {STATUS_APPROVED, STATUS_DRAFT, STATUS_CANCELLED},
    STATUS_APPROVED:  {STATUS_ISSUED, STATUS_SUBMITTED, STATUS_CANCELLED},
    STATUS_ISSUED:    {STATUS_APPROVED, STATUS_CANCELLED},
    STATUS_CANCELLED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def can_delete(status: str) -> bool:
    """Delete is allowed for Draft, Submitted (early states) and Cancelled.
    Approved / Issued for PO must be cancelled first."""
    return status in (STATUS_DRAFT, STATUS_SUBMITTED, STATUS_CANCELLED)


_RTO_NUM_RE = re.compile(r"^\d+\.RTO\.(\d{3})$")


def next_rto_number(db: Session, project_number: str) -> str:
    """Generate the next RTO number for a project: {proj}.RTO.NNN where NNN
    is the highest existing 3-digit suffix + 1, zero-padded. Defaults to 001
    when no RTOs exist yet for the project."""
    rows = db.execute(
        select(RTO.rto_number).where(RTO.project_number == project_number)
    ).all()
    max_n = 0
    for (rto_number,) in rows:
        m = _RTO_NUM_RE.match(rto_number)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"{project_number}.RTO.{max_n + 1:03d}"
