import sys
from pathlib import Path

# Both frozen (exe) and dev mode resolve APP_DIR to the app/ folder on disk.
# Frozen: sys.executable → app/cost_control.exe, parent == app/
# Dev:    __file__ → app/costcontrol/config.py, parent.parent == app/
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.parent.resolve()

# Templates and other data files are always loaded from disk alongside the exe.
# This means template changes take effect immediately without rebuilding the exe.
BUNDLE_DIR = APP_DIR

# Project root is always one level up from app/
PROJECT_ROOT = APP_DIR.parent

# SQLite database lives next to the exe / in app/ (on OneDrive)
DB_PATH = APP_DIR / "cost_control.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Package Register markdown files (Collab/Inputs/Package Register/)
REGISTER_DIR = PROJECT_ROOT / "Collab" / "Inputs" / "Package Register"

# C-13 — Account name substrings that flag a row as a capitalisation/expensing
# reversal. Detection is done in code via account_full_name.lower() containing
# any of these (lower-cased). List is configurable here so future PMO account
# renames don't require a code release.
CAPITALISATION_ACCOUNT_KEYWORDS = (
    "Project Costs Capitalised or Expensed",
)

# C-17 — set True to include voided po_lines / journal_lines / gl_lines in
# aggregations. False (the default) excludes them from totals — this matches
# the operational rule "voided is never spend".
INCLUDE_VOIDED = False

# C-19 — text file driving the active-projects list. One project per line in
# the format `<project_number> - <project name>`. Lines starting with `#` and
# blank lines are ignored. App will fail fast on startup if this file is
# missing.
ACTIVE_PROJECTS_FILE = APP_DIR / "inputs" / "active_projects.txt"

# C-19 — CSV with budget figures per project. Columns:
#   project_number, current_budget, planned_fy2027
# Optional: if missing, projects will load without budget figures (UI shows
# blanks rather than crashing).
PROJECT_BUDGETS_FILE = APP_DIR / "inputs" / "project_budgets.csv"

