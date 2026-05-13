"""Seed control_accounts and projects master data.

C-19 (2026-05-04) — active project list moved out of this file into
`app/inputs/active_projects.txt`. Budget figures moved into
`app/inputs/project_budgets.csv`. Both are loaded at startup.
"""
import csv
from sqlalchemy.orm import Session
from .config import ACTIVE_PROJECTS_FILE, PROJECT_BUDGETS_FILE
from .models import (
    BudgetReserveSubAccount,
    ControlAccount,
    IndirectL2Account,
    PlantArea,
    Project,
    WorkType,
)

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


# Canonical package lifecycle stages — matches the four-stage definition in
# every Schedule Estimation Standard (Construction, Design, Services, Supply,
# all V02+). The stages are universal across package types.
# "On Hold" / "Cancelled" are terminal-modifier states layered on top of the
# four lifecycle stages.
PACKAGE_STAGES = ("Definition", "Procurement", "Execution", "Close-out", "On Hold", "Cancelled")

# Legacy stage labels mapped onto the canonical set. Used by the seed
# migration and by packages_ingest when reading older Package Register
# markdown that still uses pre-Standards-aligned terminology.
_LEGACY_STAGE_REMAP = {
    "Planned":  "Procurement",  # the old generic placeholder used to mean
                                # "between Definition and Execution"
    "Closeout": "Close-out",    # spelling-only normalisation
    "Complete": "Close-out",    # treat fully-finished packages as Close-out
}


def normalise_package_stage(stage: str) -> str:
    """Map a legacy / unhyphenated stage label onto the canonical Standards
    value. Unknown stages pass through unchanged (so "On Hold" / "Cancelled"
    aren't mangled, and any custom stage stays as-is)."""
    return _LEGACY_STAGE_REMAP.get(stage, stage)

ESTIMATION_STANDARD_BY_TYPE: dict[str, str] = {
    "Design Package":                          "Design Package Schedule Estimation Standard",
    "Services Package":                        "Services Package Schedule Estimation Standard",
    "Supply Package":                          "Supply Package Schedule Estimation Standard",
    "Construction Package Labour & Materials": "Construction Package Schedule Estimation Standard",
    "Engineering Construction Package":        "Construction Package Schedule Estimation Standard",
}

SCHEDULE_STAGES = ("Definition", "Procurement", "Execution", "Close-out")

PRICING_BASES = {
    "BOQ": "Bill of Quantities",
    "AS": "Activity Schedule",
    "TC": "Target Cost",
    "DC": "Defined Cost",
    "PL": "Price List",
    "TM": "Time & Materials",
    "LS": "Lump Sum",
}

WORK_TYPES = [
    ("NewBuild", "New Build", False, "Capitalises to new PPE (IAS 16.7)"),
    ("TieIn", "Tie-in", True, "Capitalises to existing PPE (IAS 16.13)"),
    ("Upgrade", "Upgrade", True, "Capitalises to existing PPE (IAS 16.13)"),
    ("Replacement", "Replacement", True, "Capitalises and derecognises replaced component (IAS 16.70)"),
    ("MajorOverhaul", "Major Overhaul", True, "Conditional capitalisation (IAS 16.14)"),
    ("Maintenance", "Maintenance", False, "Expensed repair and maintenance (IAS 16.12)"),
    ("Indirect", "Indirect", False, "Allocated per directly-attributable cost rules where applicable"),
]

INDIRECT_L2_ACCOUNTS = [
    ("102.001", "Engineering", "102"),
    ("102.002", "Construction management", "102"),
    ("102.003", "Procurement & expediting", "102"),
    ("102.099", "EPCM - provisional sums", "102"),
    ("103.001", "Site establishment & accommodation", "103"),
    ("103.002", "Insurance & bonds", "103"),
    ("103.003", "Permits, surveys & legal", "103"),
    ("103.099", "Preliminaries - provisional sums", "103"),
]

BUDGET_RESERVE_SUBACCOUNTS = [
    ("101.01", "Unallocated", "Free pool - approved budget not yet committed"),
    ("101.02", "Provisional Allocation", "Planned-but-not-awarded package values"),
]

COST_ITEM_LIBRARY_DIRECT = (
    "Supply",
    "Installation",
    "Spares",
    "Design & engineering",
    "Inspection",
    "Testing & commissioning",
    "Delivery & logistics",
    "Commissioning",
    "Provisional sum",
)

COST_ITEM_LIBRARY_INDIRECT = (
    "Engineering hours",
    "Construction management hours",
    "Procurement & expediting hours",
    "Site establishment",
    "Insurance",
    "Bonds & guarantees",
    "Legal & professional",
    "Permits & approvals",
    "Provisional sum",
)

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

# Source: `.Collab/Inputs/RST Area Clasifications/RST Area Clasifications.pptx`.
# Hierarchy agreed for the app: Facility Group -> Plant Unit -> Area.
# Source numbering corrections applied:
# - Arc 03 duplicate 2102 resolved by shifting Taphole onwards to 2103-2108.
# - Process Support level-3 items corrected to match their level-2 parents.
AREA_CLASSIFICATIONS = (
    ("1000", "Raw Materials Handling Facilities", (
        ("1100", "Raw Materials Receiving", (
            ("1101", "Road Truck Weighing and Sampling Station"),
            ("1102", "Raw Materials Unloading & Storage"),
        )),
        ("1200", "Raw Materials Processing", (
            ("1201", "Feedstock Agglomeration"),
            ("1202", "Feedstock Drying"),
            ("1203", "Reductants Drying"),
            ("1204", "Pre-Smelting Materials Storage"),
            ("1205", "Pre-Smelting Materials Batching"),
        )),
    )),
    ("2000", "Smelting Facilities", (
        ("2100", "Arc 03 Furnace", (
            ("2101", "Arc 03 Furnace Proper"),
            ("2102", "Arc 03 Hearth Cooling"),
            ("2103", "Arc 03 Taphole Infrastructure"),
            ("2104", "Arc 03 Electrode"),
            ("2105", "Arc 03 Furnace Feed"),
            ("2106", "Arc 03 Furnace Hydraulics"),
            ("2107", "Arc 03 Off Gas Conditioning"),
            ("2108", "Arc 03 Cooling Water"),
        )),
        ("2200", "Arc 04 Furnace", (
            ("2201", "Arc 04 Furnace Proper"),
            ("2202", "Arc 04 Materials Batching"),
            ("2203", "Arc 04 Off Gas Conditioning"),
            ("2204", "Arc 04 Cooling Water"),
        )),
        ("2300", "Arc 05 Furnace", (
            ("2301", "Arc 05 Furnace Proper"),
            ("2302", "Arc 05 Materials Batching"),
            ("2303", "Arc 05 Off Gas Conditioning"),
            ("2304", "Arc 05 Cooling Water"),
        )),
    )),
    ("3000", "Remelting Facilities", (
        ("3100", "MK 07 Furnace", (
            ("3101", "MK 07 Furnace Proper"),
            ("3102", "MK 07 Furnace Hydraulics"),
            ("3103", "MK 07 Off Gas Conditioning"),
            ("3104", "MK 07 Cooling Water"),
        )),
        ("3200", "MK 10 Furnace", (
            ("3201", "MK 10 Furnace Proper"),
            ("3202", "MK 10 Furnace Hydraulics"),
            ("3203", "MK 10 Off Gas Conditioning"),
            ("3204", "MK 10 Cooling Water"),
        )),
    )),
    ("4000", "Alloy Refining Facilities", (
        ("4100", "CLU Converter", (
            ("4101", "CLU Proper"),
            ("4102", "CLU Hydraulics"),
            ("4103", "CLU Gas Mixing Station"),
            ("4104", "CLU Super-Heated Steam"),
            ("4105", "CLU Materials Batching"),
            ("4106", "CLU Off Gas Conditioning"),
            ("4107", "CLU Cooling Water"),
        )),
    )),
    ("5000", "Final Product Handling", (
        ("5100", "Granshot", (
            ("5101", "Granshot Proper"),
            ("5102", "Granshot Cooling Water"),
        )),
        ("5200", "Final Product Processing", (
            ("5201", "Final Product Drying"),
            ("5202", "Final Product Crushing & Bagging"),
        )),
    )),
    ("8000", "Process Support Facilities", (
        ("8100", "Ancillaries", (
            ("8101", "Alloy & Slag Handling Infrastructure"),
            ("8102", "Slag Processing"),
            ("8103", "Analytical Testing Infrastructure"),
        )),
        ("8200", "Power Generation & Distribution", (
            ("8201", "HT Power Distribution"),
            ("8202", "LT Power Distribution & Control"),
            ("8203", "Earthing & Lightning Protection"),
        )),
        ("8400", "Process Automation", (
            ("8401", "Level 1: Process Control"),
            ("8402", "Level 2: Supervisory Systems"),
        )),
        ("8500", "Utilities", (
            ("8501", "Water Supply & Treatment"),
            ("8502", "Process Cooling Water"),
            ("8503", "Compressed Air"),
            ("8504", "Industrial Gases"),
            ("8505", "Fuel Gases"),
            ("8506", "Fuel Oils"),
        )),
    )),
    ("9000", "Infrastructure", (
        ("9100", "Operational Infrastructure", (
            ("9101", "General Site Infrastructure"),
            ("9102", "Buildings, Rooms & Common Structures"),
            ("9103", "Maintenance Machinery & Equipment"),
            ("9104", "Mobile Plant"),
            ("9105", "Overhead Cranes"),
            ("9106", "Waste Management"),
        )),
        ("9200", "Information Technology (IT) Infrastructure", (
            ("9201", "IT Hardware & Devices"),
            ("9202", "IT Software & Applications"),
            ("9203", "IT Networking & Communication"),
            ("9204", "IT Data Management & Security"),
            ("9205", "IT Cloud & Virtualization"),
            ("9206", "IT Integration & Connectivity"),
        )),
        ("9300", "Safety & Security", (
            ("9301", "Fire Protection Systems"),
            ("9302", "Emergency Response Systems"),
            ("9303", "Access Control & Security Systems"),
        )),
        ("9400", "Business Systems", (
            ("9401", "Operational Management Systems"),
            ("9402", "Compliance & Regulatory Systems"),
            ("9403", "Collaboration Systems"),
            ("9404", "Business Continuity Systems"),
        )),
    )),
)

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


def _upsert_plant_area(
    db: Session,
    *,
    code: str,
    name: str,
    level: int,
    parent_id: int | None,
) -> PlantArea:
    row = db.query(PlantArea).filter_by(code=code).one_or_none()
    if row is None:
        row = PlantArea(code=code, name=name, level=level, parent_id=parent_id, is_ppe=(level == 3))
        db.add(row)
        db.flush()
    else:
        row.name = name
        row.level = level
        row.parent_id = parent_id
        if level == 3:
            row.is_ppe = True
    return row


def seed_plant_area_hierarchy(db: Session) -> None:
    """Seed RST Facility Group -> Plant Unit -> Area hierarchy."""
    for facility_code, facility_name, plant_units in AREA_CLASSIFICATIONS:
        facility = _upsert_plant_area(
            db,
            code=facility_code,
            name=facility_name,
            level=1,
            parent_id=None,
        )
        for unit_code, unit_name, areas in plant_units:
            unit = _upsert_plant_area(
                db,
                code=unit_code,
                name=unit_name,
                level=2,
                parent_id=facility.id,
            )
            for area_code, area_name in areas:
                _upsert_plant_area(
                    db,
                    code=area_code,
                    name=area_name,
                    level=3,
                    parent_id=unit.id,
                )
    db.commit()


def seed_cost_control_master_data(db: Session) -> None:
    for code, label, requires_modifies_ppe, treatment in WORK_TYPES:
        row = db.get(WorkType, code)
        if row is None:
            db.add(WorkType(
                code=code,
                label=label,
                requires_modifies_ppe=requires_modifies_ppe,
                ifrs_treatment=treatment,
            ))
        else:
            row.label = label
            row.requires_modifies_ppe = requires_modifies_ppe
            row.ifrs_treatment = treatment

    for code, name, parent_l1 in INDIRECT_L2_ACCOUNTS:
        row = db.get(IndirectL2Account, code)
        if row is None:
            db.add(IndirectL2Account(code=code, name=name, parent_l1=parent_l1))
        else:
            row.name = name
            row.parent_l1 = parent_l1

    for code, name, role in BUDGET_RESERVE_SUBACCOUNTS:
        row = db.get(BudgetReserveSubAccount, code)
        if row is None:
            db.add(BudgetReserveSubAccount(code=code, name=name, role=role))
        else:
            row.name = name
            row.role = role

    seed_plant_area_hierarchy(db)
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
