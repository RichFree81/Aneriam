"""External package procurement routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dependencies import DbDep
from ..lookups import get_package_or_404, get_project_or_404
from ..models import BidDocument, BidEvaluation, Bidder, EvaluationCriterion, Package, RTO, Tender
from .. import rto as rto_helpers
from .. import tender as tender_helpers
from ..templates import templates


router = APIRouter()


# ---------------------------------------------------------------------------
# RTO routes — see RTO_SPEC.md
# ---------------------------------------------------------------------------

def _rto_for_package_redirect(project_number: str, package_number: str):
    return RedirectResponse(
        f"/project/{project_number}/packages/{package_number}/rto",
        status_code=303,
    )


def _get_external_package_or_404(db: Session, project_number: str, package_number: str) -> Package:
    pkg = get_package_or_404(db, project_number, package_number)
    if not pkg.is_external:
        raise HTTPException(
            status_code=404,
            detail="Procurement workflow is not available for internal packages",
        )
    return pkg


@router.get("/project/{project_number}/rtos")
def project_rtos_legacy_redirect(project_number: str):
    """The project-level RTOs tab is gone (Slice B). Bookmarks land on the
    Packages list, where each external package now exposes its own RTO."""
    return RedirectResponse(f"/project/{project_number}/packages", status_code=301)


@router.get("/project/{project_number}/packages/{package_number}/rto")
def package_rto_view(project_number: str, package_number: str, request: Request, db: DbDep):
    """Procurement landing for a package: shows the RTO if one exists, or a
    'Create RTO' empty-state otherwise. Available for any package; the
    package_detail tab gates visibility on `is_external`."""
    project = get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    rto = rto_helpers.get_for_package(db, package_number)

    if rto is None:
        return templates.TemplateResponse("rto_detail.html", {
            "request": request,
            "project": project,
            "package": pkg,
            "rto": None,
            "linked_pos": [],
            "linked_po_total": 0.0,
            "variance": None,
            "valid_targets": [],
            "can_delete": False,
        })

    linked_pos = rto_helpers.linked_pos(db, rto.id)
    linked_po_total = sum(p["order_amount"] for p in linked_pos)
    variance = linked_po_total - float(rto.total_amount or 0) if linked_pos else None
    valid_targets = sorted(rto_helpers.ALLOWED_TRANSITIONS.get(rto.status, set()))
    return templates.TemplateResponse("rto_detail.html", {
        "request": request,
        "project": project,
        "package": pkg,
        "rto": rto,
        "linked_pos": linked_pos,
        "linked_po_total": linked_po_total,
        "variance": variance,
        "valid_targets": valid_targets,
        "can_delete": rto_helpers.can_delete(rto.status),
    })


@router.get("/project/{project_number}/packages/{package_number}/rto/new")
def package_rto_new_form(project_number: str, package_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    if not pkg.is_contracted:
        raise HTTPException(status_code=400, detail="Create the RTO after selecting the awarded baseline")
    next_number = rto_helpers.next_rto_number(db, package_number)
    existing_rto = rto_helpers.get_for_package(db, package_number)
    suggested_rto = {
        "vendor_name": pkg.awarded_vendor_name or "",
        "description": pkg.description,
        "total_amount": float(pkg.awarded_amount or 0),
        "request_date": datetime.now().date(),
        "originator": "",
        "notes": (
            "Created from the package awarded baseline. "
            "PO matching is completed under Project Commitments > Purchase Orders."
        ),
    }
    return templates.TemplateResponse("rto_form.html", {
        "request": request,
        "project": project,
        "package": pkg,
        "rto": None,
        "existing_rto": existing_rto,
        "suggested_rto": suggested_rto,
        "next_number": next_number,
        "mode": "create",
    })


@router.post("/project/{project_number}/packages/{package_number}/rto/new")
def package_rto_create(
    project_number: str,
    package_number: str,
    db: DbDep,
    vendor_name: str = Form(""),
    description: str = Form(""),
    total_amount: str = Form("0"),
    request_date: str = Form(""),
    originator: str = Form(""),
    notes: str = Form(""),
):
    get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    if not pkg.is_contracted:
        raise HTTPException(status_code=400, detail="Create the RTO after selecting the awarded baseline")
    rto_number = rto_helpers.next_rto_number(db, package_number)
    now = datetime.now()
    try:
        amount = float(total_amount) if total_amount else 0.0
    except ValueError:
        amount = 0.0
    try:
        req_date = datetime.strptime(request_date, "%Y-%m-%d").date() if request_date else now.date()
    except ValueError:
        req_date = now.date()
    rto = RTO(
        rto_number=rto_number,
        project_number=project_number,
        package_number=package_number,
        vendor_name=vendor_name.strip(),
        description=description.strip(),
        total_amount=amount,
        status=rto_helpers.STATUS_DRAFT,
        request_date=req_date,
        originator=originator.strip(),
        notes=notes.strip(),
        created_at=now,
        updated_at=now,
    )
    db.add(rto)
    db.commit()
    return _rto_for_package_redirect(project_number, package_number)


@router.get("/project/{project_number}/packages/{package_number}/rto/edit-form")
def package_rto_edit_form(project_number: str, package_number: str, request: Request, db: DbDep):
    project = get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    rto = rto_helpers.get_for_package(db, package_number)
    if rto is None:
        raise HTTPException(status_code=404, detail="No RTO for this package")
    return templates.TemplateResponse("rto_form.html", {
        "request": request,
        "project": project,
        "package": pkg,
        "rto": rto,
        "existing_rto": None,
        "suggested_rto": {},
        "next_number": rto.rto_number,
        "mode": "edit",
    })


@router.post("/project/{project_number}/packages/{package_number}/rto/edit")
def package_rto_edit(
    project_number: str,
    package_number: str,
    db: DbDep,
    vendor_name: str = Form(""),
    description: str = Form(""),
    total_amount: str = Form("0"),
    request_date: str = Form(""),
    originator: str = Form(""),
    notes: str = Form(""),
):
    _get_external_package_or_404(db, project_number, package_number)
    rto = rto_helpers.get_for_package(db, package_number)
    if rto is None or rto.project_number != project_number:
        raise HTTPException(status_code=404, detail="No RTO for this package")
    try:
        amount = float(total_amount) if total_amount else 0.0
    except ValueError:
        amount = 0.0
    try:
        req_date = datetime.strptime(request_date, "%Y-%m-%d").date() if request_date else rto.request_date
    except ValueError:
        req_date = rto.request_date
    rto.vendor_name = vendor_name.strip()
    rto.description = description.strip()
    rto.total_amount = amount
    rto.request_date = req_date
    rto.originator = originator.strip()
    rto.notes = notes.strip()
    rto.updated_at = datetime.now()
    db.commit()
    return _rto_for_package_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/rto/status")
def package_rto_status_change(
    project_number: str,
    package_number: str,
    db: DbDep,
    target_status: str = Form(...),
):
    _get_external_package_or_404(db, project_number, package_number)
    rto = rto_helpers.get_for_package(db, package_number)
    if rto is None or rto.project_number != project_number:
        raise HTTPException(status_code=404, detail="No RTO for this package")
    if not rto_helpers.can_transition(rto.status, target_status):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {rto.status} to {target_status}",
        )
    rto.status = target_status
    rto.updated_at = datetime.now()
    db.commit()
    return _rto_for_package_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/rto/delete")
def package_rto_delete(project_number: str, package_number: str, db: DbDep):
    _get_external_package_or_404(db, project_number, package_number)
    rto = rto_helpers.get_for_package(db, package_number)
    if rto is None or rto.project_number != project_number:
        raise HTTPException(status_code=404, detail="No RTO for this package")
    if not rto_helpers.can_delete(rto.status):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete RTO in status '{rto.status}' — cancel it first",
        )
    db.delete(rto)
    db.commit()
    return _rto_for_package_redirect(project_number, package_number)


# ---------------------------------------------------------------------------
# Tender routes — Slice C
# ---------------------------------------------------------------------------

def _tender_redirect(project_number: str, package_number: str):
    return RedirectResponse(
        f"/project/{project_number}/packages/{package_number}/tender",
        status_code=303,
    )


@router.get("/project/{project_number}/packages/{package_number}/tender")
def package_tender_view(project_number: str, package_number: str, request: Request, db: DbDep):
    """Tender sub-tab content. Shows the tender + bidders + documents, or a
    'Issue Tender' CTA if none exists yet."""
    project = get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    valid_targets = (
        sorted(tender_helpers.ALLOWED_TRANSITIONS.get(tender.status, set()))
        if tender else []
    )
    return templates.TemplateResponse("package_tender.html", {
        "request": request,
        "project": project,
        "package": pkg,
        "tender": tender,
        "valid_targets": valid_targets,
        "can_delete": tender_helpers.can_delete(tender.status) if tender else False,
        "next_tender_number": tender_helpers.next_tender_number(db, package_number, pkg.id) if tender is None else None,
    })


@router.post("/project/{project_number}/packages/{package_number}/tender/issue")
def package_tender_issue(
    project_number: str,
    package_number: str,
    db: DbDep,
    description: str = Form(""),
    issued_date: str = Form(""),
    closing_date: str = Form(""),
):
    get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    if tender_helpers.get_for_package(db, pkg.id) is not None:
        raise HTTPException(status_code=400, detail="A tender already exists for this package")
    now = datetime.now()
    try:
        d_issued = datetime.strptime(issued_date, "%Y-%m-%d").date() if issued_date else now.date()
    except ValueError:
        d_issued = now.date()
    try:
        d_closing = datetime.strptime(closing_date, "%Y-%m-%d").date() if closing_date else None
    except ValueError:
        d_closing = None
    tender = Tender(
        tender_number=tender_helpers.next_tender_number(db, package_number, pkg.id),
        package_id=pkg.id,
        description=description.strip(),
        issued_date=d_issued,
        closing_date=d_closing,
        status=tender_helpers.STATUS_DRAFT,
        created_at=now,
        updated_at=now,
    )
    db.add(tender)
    # Auto-advance Definition → Procurement on tender issue. The package can
    # only enter Procurement stage once a tender exists, so issuing one is the
    # canonical trigger. If the package is already in Procurement (or further),
    # leave it alone — the user may have advanced manually.
    if pkg.package_stage == "Definition":
        pkg.package_stage = "Procurement"
    db.commit()
    return _tender_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/tender/edit")
def package_tender_edit(
    project_number: str,
    package_number: str,
    db: DbDep,
    description: str = Form(""),
    issued_date: str = Form(""),
    closing_date: str = Form(""),
    adjudication_notes: str = Form(""),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    if tender is None:
        raise HTTPException(status_code=404, detail="No tender for this package")
    try:
        tender.issued_date = datetime.strptime(issued_date, "%Y-%m-%d").date() if issued_date else tender.issued_date
    except ValueError:
        pass
    try:
        tender.closing_date = datetime.strptime(closing_date, "%Y-%m-%d").date() if closing_date else None
    except ValueError:
        tender.closing_date = None
    tender.description = description.strip()
    tender.adjudication_notes = adjudication_notes.strip()
    tender.updated_at = datetime.now()
    db.commit()
    return _tender_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/tender/status")
def package_tender_status(
    project_number: str,
    package_number: str,
    db: DbDep,
    target_status: str = Form(...),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    if tender is None:
        raise HTTPException(status_code=404, detail="No tender for this package")
    if not tender_helpers.can_transition(tender.status, target_status):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition tender from {tender.status} to {target_status}",
        )
    tender.status = target_status
    tender.updated_at = datetime.now()
    # Tender sub-states (Issued / Closed / Adjudicating / etc.) live on the
    # Tender record itself — no longer mirrored onto Package.package_stage.
    # The package stays in 'Procurement' for the whole tender lifecycle and
    # only advances to 'Execution' on award (handled in _award_package_to_bidder).
    db.commit()
    return _tender_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/tender/delete")
def package_tender_delete(project_number: str, package_number: str, db: DbDep):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    if tender is None:
        raise HTTPException(status_code=404, detail="No tender for this package")
    if not tender_helpers.can_delete(tender.status):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tender in status '{tender.status}' — cancel it first",
        )
    db.delete(tender)
    # No longer auto-revert package_stage — the user controls it manually.
    # Deleting the tender doesn't undo whatever stage decision was made.
    db.commit()
    return _tender_redirect(project_number, package_number)


# ── Bidder CRUD ──────────────────────────────────────────────────────

@router.post("/project/{project_number}/packages/{package_number}/tender/bidders/add")
def package_bidder_add(
    project_number: str,
    package_number: str,
    db: DbDep,
    vendor_name: str = Form(...),
    bid_amount: str = Form(""),
    bid_received_date: str = Form(""),
    status: str = Form("Pending"),
    notes: str = Form(""),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    if tender is None:
        raise HTTPException(status_code=404, detail="No tender for this package")
    try:
        amount = float(bid_amount) if bid_amount.strip() else None
    except ValueError:
        amount = None
    try:
        d_received = datetime.strptime(bid_received_date, "%Y-%m-%d").date() if bid_received_date.strip() else None
    except ValueError:
        d_received = None
    next_order = (
        db.query(Bidder)
        .filter_by(tender_id=tender.id)
        .count()
    )
    db.add(Bidder(
        tender_id=tender.id,
        vendor_name=vendor_name.strip(),
        bid_amount=amount,
        bid_received_date=d_received,
        status=status if status in tender_helpers.BIDDER_STATUSES else "Pending",
        notes=notes.strip(),
        display_order=next_order,
    ))
    tender.updated_at = datetime.now()
    db.commit()
    return _tender_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/tender/bidders/{bidder_id}/edit")
def package_bidder_edit(
    project_number: str,
    package_number: str,
    bidder_id: int,
    db: DbDep,
    vendor_name: str = Form(...),
    bid_amount: str = Form(""),
    bid_received_date: str = Form(""),
    status: str = Form("Pending"),
    notes: str = Form(""),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    bidder = db.get(Bidder, bidder_id)
    if tender is None or bidder is None or bidder.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Bidder not found")
    try:
        bidder.bid_amount = float(bid_amount) if bid_amount.strip() else None
    except ValueError:
        pass
    try:
        bidder.bid_received_date = datetime.strptime(bid_received_date, "%Y-%m-%d").date() if bid_received_date.strip() else None
    except ValueError:
        bidder.bid_received_date = None
    bidder.vendor_name = vendor_name.strip()
    bidder.status = status if status in tender_helpers.BIDDER_STATUSES else bidder.status
    bidder.notes = notes.strip()
    tender.updated_at = datetime.now()
    db.commit()
    return _tender_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/tender/bidders/{bidder_id}/delete")
def package_bidder_delete(project_number: str, package_number: str, bidder_id: int, db: DbDep):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    bidder = db.get(Bidder, bidder_id)
    if tender is None or bidder is None or bidder.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Bidder not found")
    db.delete(bidder)
    tender.updated_at = datetime.now()
    db.commit()
    return _tender_redirect(project_number, package_number)


# ── Bid document CRUD ────────────────────────────────────────────────

@router.post("/project/{project_number}/packages/{package_number}/tender/bidders/{bidder_id}/documents/add")
def package_bid_document_add(
    project_number: str,
    package_number: str,
    bidder_id: int,
    db: DbDep,
    document_name: str = Form(...),
    document_ref: str = Form(...),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    bidder = db.get(Bidder, bidder_id)
    if tender is None or bidder is None or bidder.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Bidder not found")
    db.add(BidDocument(
        bidder_id=bidder.id,
        document_name=document_name.strip(),
        document_ref=document_ref.strip(),
        uploaded_at=datetime.now(),
    ))
    tender.updated_at = datetime.now()
    db.commit()
    return _tender_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/tender/documents/{doc_id}/delete")
def package_bid_document_delete(project_number: str, package_number: str, doc_id: int, db: DbDep):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    doc = db.get(BidDocument, doc_id)
    if tender is None or doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    bidder = db.get(Bidder, doc.bidder_id)
    if bidder is None or bidder.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    tender.updated_at = datetime.now()
    db.commit()
    return _tender_redirect(project_number, package_number)


# ---------------------------------------------------------------------------
# Adjudication routes — Slice D
# ---------------------------------------------------------------------------

def _adjudication_redirect(project_number: str, package_number: str):
    return RedirectResponse(
        f"/project/{project_number}/packages/{package_number}/adjudication",
        status_code=303,
    )


@router.get("/project/{project_number}/packages/{package_number}/adjudication")
def package_adjudication_view(project_number: str, package_number: str, request: Request, db: DbDep):
    """Show the criterion-x-bidder scoring matrix and weighted-total
    recommendation. Available once a tender exists; the parent tab is
    Procurement (visible only on external packages)."""
    project = get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)

    if tender is None:
        return templates.TemplateResponse("package_adjudication.html", {
            "request": request,
            "project": project,
            "package": pkg,
            "tender": None,
            "criteria": [],
            "bidders": [],
            "scores": {},
            "weighted_totals": {},
            "weight_sum": 0,
            "valid_targets": [],
        })

    criteria = (
        db.query(EvaluationCriterion)
        .filter_by(tender_id=tender.id)
        .order_by(EvaluationCriterion.display_order, EvaluationCriterion.id)
        .all()
    )
    bidders = sorted(tender.bidders, key=lambda b: b.display_order)

    # scores[bidder_id][criterion_id] = (score, evaluator, notes)
    scores: dict[int, dict[int, tuple[float, str, str]]] = {b.id: {} for b in bidders}
    rows = (
        db.query(BidEvaluation)
        .join(Bidder, Bidder.id == BidEvaluation.bidder_id)
        .filter(Bidder.tender_id == tender.id)
        .all()
    )
    for r in rows:
        scores.setdefault(r.bidder_id, {})[r.criterion_id] = (
            float(r.score or 0), r.evaluator or "", r.notes or "",
        )

    weights_by_id = {c.id: float(c.weight or 0) for c in criteria}
    weight_sum = sum(weights_by_id.values())

    weighted_totals: dict[int, float | None] = {}
    for b in bidders:
        bidder_scores = {cid: triple[0] for cid, triple in scores.get(b.id, {}).items()}
        weighted_totals[b.id] = tender_helpers.weighted_score(bidder_scores, weights_by_id)

    valid_targets = sorted(tender_helpers.ALLOWED_TRANSITIONS.get(tender.status, set()))
    return templates.TemplateResponse("package_adjudication.html", {
        "request": request,
        "project": project,
        "package": pkg,
        "tender": tender,
        "criteria": criteria,
        "bidders": bidders,
        "scores": scores,
        "weighted_totals": weighted_totals,
        "weight_sum": weight_sum,
        "valid_targets": valid_targets,
    })


@router.post("/project/{project_number}/packages/{package_number}/adjudication/criteria/add")
def package_criterion_add(
    project_number: str,
    package_number: str,
    db: DbDep,
    criterion_name: str = Form(...),
    weight: str = Form("0"),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    if tender is None:
        raise HTTPException(status_code=404, detail="No tender for this package")
    try:
        w = float(weight)
    except ValueError:
        w = 0.0
    next_order = (
        db.query(EvaluationCriterion).filter_by(tender_id=tender.id).count()
    )
    db.add(EvaluationCriterion(
        tender_id=tender.id,
        criterion_name=criterion_name.strip(),
        weight=max(0.0, w),
        display_order=next_order,
    ))
    tender.updated_at = datetime.now()
    db.commit()
    return _adjudication_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/adjudication/criteria/{criterion_id}/edit")
def package_criterion_edit(
    project_number: str,
    package_number: str,
    criterion_id: int,
    db: DbDep,
    criterion_name: str = Form(...),
    weight: str = Form("0"),
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    crit = db.get(EvaluationCriterion, criterion_id)
    if tender is None or crit is None or crit.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Criterion not found")
    try:
        crit.weight = max(0.0, float(weight))
    except ValueError:
        pass
    crit.criterion_name = criterion_name.strip()
    tender.updated_at = datetime.now()
    db.commit()
    return _adjudication_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/adjudication/criteria/{criterion_id}/delete")
def package_criterion_delete(
    project_number: str,
    package_number: str,
    criterion_id: int,
    db: DbDep,
):
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    crit = db.get(EvaluationCriterion, criterion_id)
    if tender is None or crit is None or crit.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Criterion not found")
    db.delete(crit)
    tender.updated_at = datetime.now()
    db.commit()
    return _adjudication_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/adjudication/score")
async def package_scores_save(
    project_number: str,
    package_number: str,
    request: Request,
    db: DbDep,
):
    """Bulk save: form fields named `score_{bidder_id}_{criterion_id}` and
    `evaluator_{bidder_id}_{criterion_id}`. Empty score deletes any existing
    BidEvaluation row for that cell so the weighted total recalculates
    correctly."""
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    if tender is None:
        raise HTTPException(status_code=404, detail="No tender for this package")

    form = await request.form()
    # Build {(bidder_id, criterion_id): (score_str, evaluator, notes)}
    cells: dict[tuple[int, int], dict[str, str]] = {}
    for key, value in form.items():
        if "_" not in key:
            continue
        prefix, _, rest = key.partition("_")
        try:
            bidder_id_str, criterion_id_str = rest.split("_", 1)
            bidder_id = int(bidder_id_str)
            criterion_id = int(criterion_id_str)
        except (ValueError, IndexError):
            continue
        cell = cells.setdefault((bidder_id, criterion_id), {})
        if prefix == "score":
            cell["score"] = value
        elif prefix == "evaluator":
            cell["evaluator"] = value
        elif prefix == "notes":
            cell["notes"] = value

    # Validate all bidder/criterion ids belong to this tender
    valid_bidder_ids = {b.id for b in tender.bidders}
    valid_criterion_ids = {
        c.id for c in db.query(EvaluationCriterion.id).filter_by(tender_id=tender.id).all()
    }

    for (bidder_id, criterion_id), data in cells.items():
        if bidder_id not in valid_bidder_ids or criterion_id not in valid_criterion_ids:
            continue
        score_str = (data.get("score") or "").strip()
        evaluator = (data.get("evaluator") or "").strip()
        notes = (data.get("notes") or "").strip()
        existing = (
            db.query(BidEvaluation)
            .filter_by(bidder_id=bidder_id, criterion_id=criterion_id)
            .first()
        )
        if not score_str:
            # Empty score -> remove any existing evaluation
            if existing is not None:
                db.delete(existing)
            continue
        try:
            score = float(score_str)
        except ValueError:
            continue
        score = max(0.0, min(100.0, score))
        if existing is None:
            db.add(BidEvaluation(
                bidder_id=bidder_id,
                criterion_id=criterion_id,
                score=score,
                evaluator=evaluator,
                notes=notes,
            ))
        else:
            existing.score = score
            existing.evaluator = evaluator
            existing.notes = notes

    tender.updated_at = datetime.now()
    db.commit()
    return _adjudication_redirect(project_number, package_number)


@router.post("/project/{project_number}/packages/{package_number}/adjudication/bidders/{bidder_id}/status")
def package_bidder_status(
    project_number: str,
    package_number: str,
    bidder_id: int,
    db: DbDep,
    target_status: str = Form(...),
):
    """Flip a bidder's status. Setting it to 'Awarded' triggers the package
    award flow (see _award_package_to_bidder); other transitions just update
    the bidder row."""
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    bidder = db.get(Bidder, bidder_id)
    if tender is None or bidder is None or bidder.tender_id != tender.id:
        raise HTTPException(status_code=404, detail="Bidder not found")
    if target_status not in tender_helpers.BIDDER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown bidder status: {target_status}")
    if target_status == "Awarded":
        _award_package_to_bidder(db, pkg, tender, bidder)
    else:
        bidder.status = target_status
        tender.updated_at = datetime.now()
        db.commit()
    return _adjudication_redirect(project_number, package_number)


def _award_package_to_bidder(db: Session, pkg: Package, tender: Tender, bidder: Bidder) -> None:
    """Apply the side-effects of awarding a package to a specific bidder:
    flip the awarded bidder + demote any other Awarded bidder, set Tender
    to Awarded, and copy bidder details onto the Package's awarded_*
    fields. is_contracted=True freezes the pre-award amounts on the cost
    nodes; package_stage advances to 'Execution' per the four-stage
    lifecycle in the Schedule Estimation Standards."""
    # Demote any previously-awarded bidder on this tender (re-award path).
    for b in tender.bidders:
        if b.id != bidder.id and b.status == "Awarded":
            b.status = "Shortlisted"
    bidder.status = "Awarded"
    tender.status = tender_helpers.STATUS_AWARDED
    now = datetime.now()
    tender.updated_at = now
    pkg.awarded_vendor_name = bidder.vendor_name
    pkg.awarded_amount = float(bidder.bid_amount or 0)
    pkg.awarded_date = now.date()
    pkg.is_contracted = True
    # Per the Schedule Estimation Standards, awarding a tender ends the
    # Procurement stage and starts Execution — the package transitions
    # automatically. The user can manually override on the package detail
    # if they want to defer the move.
    pkg.package_stage = "Execution"
    db.commit()


@router.get("/project/{project_number}/packages/{package_number}/award")
def package_award_view(project_number: str, package_number: str, request: Request, db: DbDep):
    """Read-only summary of the award outcome. Lives between Adjudication
    and Orders in the Procurement sub-nav so users have a clear stop on
    the workflow timeline. If no award is in place yet the page shows a
    'no award yet' state with a pointer back to Adjudication."""
    project = get_project_or_404(db, project_number)
    pkg = _get_external_package_or_404(db, project_number, package_number)
    tender = tender_helpers.get_for_package(db, pkg.id)
    awarded_bidder = None
    if tender is not None:
        awarded_bidder = next(
            (b for b in tender.bidders if b.status == "Awarded"),
            None,
        )

    # Slice F — variance roll-up: sum order_amount of every PO linked to
    # any RTO of this package. Variance = committed − awarded so a positive
    # number is over-spend (red), negative is under-spend (green).
    committed_row = db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN l.is_original = 1 THEN p.amount ELSE 0 END), 0) AS original_total,
                COALESCE(SUM(CASE WHEN l.is_original = 0 THEN p.amount ELSE 0 END), 0) AS variation_total,
                COALESCE(SUM(p.amount), 0)                                              AS committed_total
            FROM rto r
            JOIN po_rto_links l ON l.rto_id = r.id
            JOIN po_lines     p ON p.po_number = l.po_number AND p.voided = 0
            WHERE r.package_number = :pkg
        """),
        {"pkg": package_number},
    ).fetchone()
    original_total = float(committed_row.original_total or 0) if committed_row else 0.0
    variation_total = float(committed_row.variation_total or 0) if committed_row else 0.0
    committed_total = float(committed_row.committed_total or 0) if committed_row else 0.0
    awarded_amount = float(pkg.awarded_amount or 0)
    variance = (committed_total - awarded_amount) if pkg.awarded_amount is not None else None

    return templates.TemplateResponse("package_award.html", {
        "request": request,
        "project": project,
        "package": pkg,
        "tender": tender,
        "awarded_bidder": awarded_bidder,
        "original_total": original_total,
        "variation_total": variation_total,
        "committed_total": committed_total,
        "variance": variance,
    })
