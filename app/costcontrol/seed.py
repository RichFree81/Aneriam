"""Seed control_accounts and projects master data.

C-19 (2026-05-04) — active project list moved out of this file into
`app/inputs/active_projects.txt`. Budget figures moved into
`app/inputs/project_budgets.csv`. Both are loaded at startup.
"""
import csv
from sqlalchemy.orm import Session
from .config import ACTIVE_PROJECTS_FILE, PROJECT_BUDGETS_FILE
from .models import ControlAccount, Project

PACKAGE_TYPES = (
    "Design Package",
    "Services Package",
    "Supply Package",
    "Construction Package Labour & Materials",
    "Engineering Construction Package",
)

# Package types that default to external (procurement workflow applies).
# Design and Services default to internal (in-house) — user can override
# when a specific package is outsourced.
EXTERNAL_BY_DEFAULT: frozenset[str] = frozenset({
    "Construction Package Labour & Materials",
    "Engineering Construction Package",
    "Supply Package",
})


def default_is_external(package_type: str) -> bool:
    """Return the default is_external value for a given package type."""
    return package_type in EXTERNAL_BY_DEFAULT


PACKAGE_STAGES = ("Definition", "Planned", "Execution", "Complete", "On Hold", "Cancelled")

ESTIMATION_STANDARD_BY_TYPE: dict[str, str] = {
    "Design Package":                          "Design Package Schedule Estimation Standard",
    "Services Package":                        "Services Package Schedule Estimation Standard",
    "Supply Package":                          "Supply Package Schedule Estimation Standard",
    "Construction Package Labour & Materials": "Construction Package Schedule Estimation Standard",
    "Engineering Construction Package":        "Construction Package Schedule Estimation Standard",
}

SCHEDULE_STAGES = ("Definition", "Procurement", "Execution", "Close-out")

# Source: Control Accounts List sheet (as-is assessment § 13.1)
# C-13 (2026-05-04) — 901 and 902 flipped to excluded_from_capex=False.
# Capitalisation detection moved to PMO Account: Account Full Name (see
# `_is_capitalisation_row` in ingest.py). The codes remain in the table
# because they may still be valid CC codes for tagging purposes; the
# `excluded_from_capex` column is no longer driving any zeroing logic.
CONTROL_ACCOUNTS = [
    ("101", "101 - Budget Reserves",              False),
    ("102", "102 - EPCM",                         False),
    ("103", "103 - Preliminaries",                False),
    ("201", "201 - Equipment",                    False),
    ("202", "202 - Process Piping",               False),
    ("203", "203 - Electrical Reticulation",      False),
    ("204", "204 - Process Automation",           False),
    ("205", "205 - Structures",                   False),
    ("206", "206 - Yard Improvements",            False),
    ("901", "901 - Project Capitalisation",       False),
    ("902", "902 - Project Expensing",            False),
]

# C-19 — Active projects and budgets are now loaded from text/CSV files.
# See _load_active_projects() and _load_budgets() below.


def _load_active_projects() -> list[tuple[str, str]]:
    """Read app/inputs/active_projects.txt and return [(project_number, project_name), ...].

    Format: `<project_number> - <project name>`, one per line. Lines starting
    with `#` and blank lines are ignored. Fails fast with a clear error if
    the file is missing — the app cannot run without it.
    """
    if not ACTIVE_PROJECTS_FILE.exists():
        raise FileNotFoundError(
            f"active_projects.txt not found at {ACTIVE_PROJECTS_FILE} — "
            f"please create the file with one '<project_number> - <project name>' "
            f"line per active project."
        )
    projects: list[tuple[str, str]] = []
    with ACTIVE_PROJECTS_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " - " not in line:
                continue  # malformed line — skip silently
            number, name = line.split(" - ", 1)
            projects.append((number.strip(), name.strip()))
    return projects


def _load_budgets() -> dict[str, tuple[float | None, float | None, float | None]]:
    """Read app/inputs/project_budgets.csv and return
    {project_number: (current_budget, planned_fy2027, approved_capex)}.

    `approved_capex` is an optional column — if absent or blank, the field is
    None and the UI renders blank. Optional file overall — if missing,
    projects load with no budget figures.
    """
    if not PROJECT_BUDGETS_FILE.exists():
        return {}
    budgets: dict[str, tuple[float | None, float | None, float | None]] = {}
    with PROJECT_BUDGETS_FILE.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            num = (row.get("project_number") or "").strip()
            if not num:
                continue
            cb = (row.get("current_budget") or "").strip()
            pf = (row.get("planned_fy2027") or "").strip()
            ac = (row.get("approved_capex") or "").strip()
            budgets[num] = (
                float(cb) if cb else None,
                float(pf) if pf else None,
                float(ac) if ac else None,
            )
    return budgets


def seed_control_accounts(db: Session) -> None:
    existing = {ca.code for ca in db.query(ControlAccount).all()}
    for code, name, excluded in CONTROL_ACCOUNTS:
        if code not in existing:
            db.add(ControlAccount(code=code, name=name, excluded_from_capex=excluded))
        else:
            ca = db.query(ControlAccount).filter_by(code=code).one()
            ca.name = name
            ca.excluded_from_capex = excluded
    db.commit()


def seed_projects(db: Session) -> None:
    """C-19 — load active list from text file and budgets from CSV.

    Upserts each active project; flips `is_active=False` for any project not
    in the file (historic transactions are preserved).
    """
    active_list = _load_active_projects()
    budgets = _load_budgets()
    active_numbers = {num for num, _ in active_list}

    for number, name in active_list:
        cb, pf, ac = budgets.get(number, (None, None, None))
        proj = db.query(Project).filter_by(project_number=number).first()
        if proj is None:
            db.add(Project(project_number=number, project_name=name,
                           current_budget=cb, planned_fy2027=pf,
                           approved_capex=ac,
                           is_active=True))
        else:
            proj.project_name = name
            proj.current_budget = cb
            proj.planned_fy2027 = pf
            proj.approved_capex = ac
            proj.is_active = True

    for proj in db.query(Project).all():
        if proj.project_number not in active_numbers:
            proj.is_active = False

    db.commit()


def upsert_project(db: Session, project_number: str, project_name: str) -> None:
    """Insert a project discovered during import if it isn't already known.
    Auto-discovered projects start as inactive; only the seeded active list is shown."""
    existing = db.query(Project).filter_by(project_number=project_number).first()
    if existing is None:
        db.add(Project(project_number=project_number, project_name=project_name, is_active=False))
