"""RTO helpers — number generation, status rules, suggested-match scoring.

Kept separate from app.py so the routes file stays focused on HTTP
plumbing while business rules sit somewhere small and testable.
"""
from __future__ import annotations

import re
from datetime import date

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


# ---------------------------------------------------------------------------
# PO -> RTO match scoring (see RTO_SPEC.md §6)
# ---------------------------------------------------------------------------

def _normalise_vendor(s: str) -> str:
    """Lowercase, drop leading numeric IDs (e.g. '12345 ACME Ltd'), strip
    non-alphanumeric so 'ACME-Ltd' and 'acme ltd' compare equal."""
    s = s.lower()
    s = re.sub(r"^[\d\s\-_:]+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _vendor_match(po_vendor: str, rto_vendor: str) -> int:
    pv = _normalise_vendor(po_vendor)
    rv = _normalise_vendor(rto_vendor)
    if not pv or not rv:
        return 0
    if pv == rv:
        return 40
    if pv in rv or rv in pv:
        return 20
    pw = po_vendor.lower().split()[:3]
    rw = rto_vendor.lower().split()[:3]
    if pw and pw == rw:
        return 20
    return 0


def _amount_match(po_amount: float, rto_amount: float) -> int:
    if rto_amount <= 0:
        return 0
    diff = abs(po_amount - rto_amount) / rto_amount
    if diff <= 0.02:
        return 25
    if diff <= 0.10:
        return 10
    return 0


def _date_match(po_date, rto_date) -> int:
    """Slides linearly: same day = +20, day 30 = +5, day 60+ = 0.
    Negative deltas (PO before RTO) score 0 — direction is wrong."""
    if not po_date or not rto_date:
        return 0
    delta = (po_date - rto_date).days
    if delta < 0:
        return 0
    if delta == 0:
        return 20
    if delta <= 30:
        return max(5, int(20 - (15 * delta / 30)))
    if delta <= 60:
        return max(0, int(5 - (5 * (delta - 30) / 30)))
    return 0


def score_match(po: dict, rto: RTO) -> int:
    """Compute 0-100 match score for a PO summary dict against an RTO.

    `po` keys: vendor (str), order_amount (float), first_date (date|None).
    """
    score = 0
    score += _vendor_match(po.get("vendor", ""), rto.vendor_name or "")
    score += _amount_match(float(po.get("order_amount", 0)), float(rto.total_amount or 0))
    score += _date_match(po.get("first_date"), rto.request_date)
    if rto.status == STATUS_APPROVED:
        score += 5
    return min(score, 100)


# RTOs eligible to be linked to a PO. Approved is the canonical state;
# Issued for PO is included so the user can re-link if Procurement raised a
# second PO against the same RTO (rare but possible).
LINKABLE_STATUSES = (STATUS_APPROVED, STATUS_ISSUED)


def _serialise_rto(rto: RTO, score: int | None = None) -> dict:
    return {
        "rto_id":       rto.id,
        "rto_number":   rto.rto_number,
        "vendor_name":  rto.vendor_name or "",
        "description":  rto.description or "",
        "total_amount": float(rto.total_amount or 0),
        "status":       rto.status,
        "request_date": rto.request_date.isoformat() if rto.request_date else None,
        "score":        score,
    }


def suggest_matches(db: Session, project_number: str, po: dict) -> dict:
    """Return {'top': [<=5 ranked candidates], 'all': [all linkable RTOs]}.

    The 'all' list is for the modal's search box — typical project has
    fewer than 50 RTOs so client-side filtering is fine.
    """
    rtos = db.execute(
        select(RTO).where(
            RTO.project_number == project_number,
            RTO.status.in_(LINKABLE_STATUSES),
        )
    ).scalars().all()

    scored = [(score_match(po, r), r) for r in rtos]
    scored.sort(key=lambda x: -x[0])

    return {
        "top": [_serialise_rto(r, s) for s, r in scored[:5]],
        "all": [_serialise_rto(r) for r in sorted(rtos, key=lambda r: r.rto_number, reverse=True)],
    }
