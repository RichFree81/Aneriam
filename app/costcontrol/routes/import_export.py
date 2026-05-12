"""Import and CSV export routes."""
from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import RedirectResponse

from ..dependencies import DbDep
from ..exports import portfolio_summary_csv, project_transactions_csv
from ..ingest import run_import
from ..lookups import get_project_or_404
from ..models import ImportBatch
from ..templates import templates


router = APIRouter()


@router.get("/import")
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


@router.post("/import/run")
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
        db.rollback()
        return RedirectResponse(
            f"/import?error={quote_plus(str(exc))}",
            status_code=303,
        )


@router.get("/project/{project_number}/export/csv")
def export_project_csv(project_number: str, db: DbDep):
    """C-20: per-project CSV export. Same shape as /export/csv but scoped."""
    get_project_or_404(db, project_number)
    return project_transactions_csv(db, project_number)


@router.get("/export/csv")
def export_csv(db: DbDep):
    return portfolio_summary_csv(db)
