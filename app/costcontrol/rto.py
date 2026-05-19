"""RTO helpers — number generation, status rules, suggested-match scoring.

Kept separate from the routes so the HTTP layer stays focused on request
plumbing while business rules sit somewhere small and testable.
"""
from __future__ import annotations

import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import Package, RTO


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


_RTO_SUFFIX_RE = re.compile(r"\.RTO\.(\d+)$")


def next_rto_number(db: Session, package_number: str) -> str:
    """Generate the next RTO number for a *package*: {package}.RTO.NNN where
    NNN is the highest existing trailing-digit suffix + 1, zero-padded.

    The new (post-Slice-B) numbering scheme keys RTOs to packages, so each
    external package owns its own RTO sequence. v1 expects exactly one RTO
    per package, but the NNN suffix leaves room for re-tenders / replacement
    RTOs without a schema change.
    """
    rows = db.execute(
        select(RTO.rto_number).where(RTO.package_number == package_number)
    ).all()
    max_n = 0
    for (rto_number,) in rows:
        m = _RTO_SUFFIX_RE.search(rto_number)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"{package_number}.RTO.{max_n + 1:03d}"


def get_for_package(db: Session, package_number: str) -> RTO | None:
    """Return the most recent RTO for a package, or None."""
    return (
        db.query(RTO)
        .filter_by(package_number=package_number)
        .order_by(RTO.id.desc())
        .first()
    )


def linked_po_total(db: Session, rto_id: int) -> float:
    row = db.execute(
        text("""
            SELECT COALESCE(SUM(p.amount), 0) AS linked_po_total
            FROM po_rto_links l
            JOIN po_lines p ON p.po_number = l.po_number AND p.voided = 0
            WHERE l.rto_id = :rto_id
        """),
        {"rto_id": rto_id},
    ).fetchone()
    return float(row.linked_po_total or 0) if row else 0.0


def package_commercial_status(db: Session, pkg: Package) -> dict[str, float | int | str | None]:
    """Return the package's derived commercial state.

    The package is the origin of the RTO, but the PO link lives in the
    project-level commitments register. This helper keeps that status derived
    from the linked records instead of duplicating editable fields on Package.
    """
    rto = get_for_package(db, pkg.package_number)
    if rto is None:
        return {
            "status": "Awarded" if pkg.is_contracted else "Not Awarded",
            "rto_number": None,
            "rto_status": None,
            "po_count": 0,
            "linked_po_total": 0.0,
        }

    linked_pos = linked_po_total(db, rto.id)
    po_count_row = db.execute(
        text("SELECT COUNT(*) AS po_count FROM po_rto_links WHERE rto_id = :rto_id"),
        {"rto_id": rto.id},
    ).fetchone()
    po_count = int(po_count_row.po_count or 0) if po_count_row else 0
    return {
        "status": "Committed" if po_count else "Awaiting PO",
        "rto_number": rto.rto_number,
        "rto_status": rto.status,
        "po_count": po_count,
        "linked_po_total": linked_pos,
    }


def linked_pos(db: Session, rto_id: int) -> list[dict]:
    """Return per-PO summary rows for POs currently linked to an RTO."""
    rows = db.execute(
        text("""
            SELECT
                l.po_number,
                l.is_original,
                MIN(p.date)              AS first_date,
                MAX(p.vendor)            AS vendor,
                COALESCE(SUM(p.amount),         0) AS order_amount,
                COALESCE(SUM(p.actual_amount),  0) AS actual_amount,
                COALESCE(SUM(p.remaining),      0) AS remaining_amount
            FROM po_rto_links l
            LEFT JOIN po_lines p ON p.po_number = l.po_number AND p.voided = 0
            WHERE l.rto_id = :rto_id
            GROUP BY l.po_number, l.is_original
            ORDER BY l.is_original DESC, first_date
        """),
        {"rto_id": rto_id},
    ).fetchall()
    return [dict(row._mapping) for row in rows]


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
