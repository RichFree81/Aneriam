# app/CLAUDE.md — Cost Control MVP

Read `/CLAUDE.md` at the repo root first. This file covers the Cost Control MVP only.

## What this app is

A tactical Windows desktop tool used inside RST for project cost reconciliation. It ingests NetSuite PMO exports (`.xls` SpreadsheetML files), classifies transactions against control accounts, and renders a portfolio + per-project view of actual / committed / capitalised cost.

**Audience:** single user (the cost controller) on their own PC. Not multi-tenant. No auth. No network. Runs as a portable `cost_control.exe` that the user double-clicks.

**Independence:** this app **does not share code, types, schemas, migrations, or auth with the Aneriam platform** in `/frontend` and `/backend`. Don't import from there. Don't export to there. The two are separate by design.

## Stack

- **Web framework:** FastAPI (server-rendered, no SPA).
- **Templates:** Jinja2 — `app/templates/*.html`.
- **DB:** SQLite (`app/cost_control.db`) accessed via SQLModel / SQLAlchemy 2.x.
- **Schema migrations:** **none.** Schema is created via `Base.metadata.create_all()` at startup, plus a hand-rolled `ALTER TABLE` list in `app/costcontrol/app.py`. There is no Alembic. Adding a column means appending a `CREATE TABLE`/`ALTER TABLE` string to that list.
- **Packaging:** PyInstaller spec at `app/cost_control.spec` produces `cost_control.exe`. Build via `rebuild_exe.bat`.
- **Entry point:** `app/run.py` — picks a free port from 8090, starts uvicorn, opens the browser.

## File layout

```
app/
├── CLAUDE.md                  # This file
├── pyproject.toml
├── run.py                     # Launcher (browser auto-open, free-port detection)
├── cost_control.spec          # PyInstaller build spec
├── rebuild_exe.bat            # Local build helper
├── cost_control.exe           # Built artefact (gitignored)
├── cost_control.db            # SQLite (gitignored)
├── inputs/
│   ├── active_projects.txt    # Seed: project_number — project_name, one per line
│   └── project_budgets.csv    # Seed: current_budget, planned_fy2027, approved_capex
├── templates/                 # Jinja2 — main, project, package_detail, import, etc.
└── costcontrol/
    ├── app.py                 # All routes + startup migrations + SQL queries
    ├── ingest.py              # NetSuite .xls parsers + run_import()
    ├── models.py              # SQLModel tables
    ├── seed.py                # seed_projects, seed_control_accounts
    ├── packages_ingest.py     # Package register seeding
    ├── database.py            # SessionLocal, engine, get_db
    └── config.py              # Paths + capitalisation keywords
```

## The golden rules

1. **NetSuite exports are SpreadsheetML, not BIFF.** They have `.xls` extensions but are XML. `ingest._parse_rows` already handles this — don't try to use `xlrd` / `openpyxl`.
2. **Transactions table is the source of truth for money.** All portfolio / project / drilldown SQL groups directly off `transactions`. Don't introduce a separate aggregate table.
3. **Capitalisation detection lives in one place.** `_build_capitalisation_clauses()` in `app.py` produces `_IS_CAP_SQL` / `_NOT_CAP_SQL`. Use them — don't inline `LIKE '%Capitalised%'` checks. They are unprefixed boolean fragments — interpolate as `CASE WHEN {_NOT_CAP_SQL} THEN ... END`, **not** `t.{_NOT_CAP_SQL}`.
4. **Tenant isolation does not apply here.** This is a single-user app — no `company_id`, no `get_valid_portfolio`. Don't copy patterns from `backend/app/api/deps.py`.
5. **Audit log writes are explicit.** `_write_audit_log(db, node, action)` is called by every cost-node mutation route. If you add a new write path, call it; don't rely on column defaults.
6. **Ingest is idempotent at the batch level, not the row level.** Each `run_import` creates a fresh `ImportBatch` and replaces all transactions. Re-running an import is safe but discards prior batches' rows.
7. **Don't hand-edit `cost_control.db`.** It's regenerated from inputs + the most recent NetSuite import. To change seed projects or budgets, edit `inputs/active_projects.txt` / `inputs/project_budgets.csv` and restart.
8. **Schema changes need both a model edit and a startup-migration string.** Adding a column to `models.py` alone won't update existing DBs — append the corresponding `ALTER TABLE` to the list in `app.py` (search for `cost_node_audit_log` for an example).

## Key behaviours and codes

The codebase uses short tags `C-1`, `C-7`, `C-13`, `C-16`, etc. as inline comments to mark deliberate decisions made during the MVP build. Treat them as permanent — they correspond to operational rules agreed with the cost controller. If you want to change one, surface it first; don't quietly rewrite around it.

Notable ones:
- **C-7:** vendor-bill actuals join PO lines on `(po, project, po_memo)` where `po_memo` is the PO line's per-line memo (column "PO Memo" on bills, "Memo" on PO Detailed).
- **C-13/C-14:** capitalisation is detected by `Account: Account Full Name` containing one of the configured keywords, **not** by control-account code 901/902.
- **C-16:** closed POs have zero live commitment; their `Remaining` value becomes an "agreed shortfall" disclosed separately on the PO modal.
- **C-19:** active projects and budgets live in flat files under `inputs/`, not in code.

## Files agents must never touch without explicit user approval

- `cost_control.spec` and `rebuild_exe.bat` — packaging recipe; a bad change here breaks the user's distribution.
- `inputs/*.csv` and `inputs/*.txt` — these are operational data the cost controller maintains, not code.
- `cost_control.db` — never edit by hand; only modify via the running app or by re-running `run_import`.

## What "done" looks like

1. `python run.py` starts the server cleanly and the home page (`GET /`) returns 200.
2. If schema changed: existing DBs upgrade cleanly (i.e., the `ALTER TABLE` string survives `IF NOT EXISTS` / column-already-exists conditions).
3. If ingest changed: a re-run of `run_import` against the canonical NetSuite files in `Collab/Inputs/Cost Control Data/Data/` completes without error and the totals on the home page look sane.
4. If the exe is the deliverable, `rebuild_exe.bat` produces a working `cost_control.exe` and double-clicking it opens the browser.

## How to start a session in `app/`

1. Read this file.
2. If the task involves SQL: read `app/costcontrol/app.py` for query patterns.
3. If the task involves NetSuite parsing: read `app/costcontrol/ingest.py` (especially `_parse_rows`, the per-source parsers, and `run_import`).
4. If the task involves cost-build-up UI: read `app/templates/package_detail.html` and the `cost_*` routes in `app.py`.
5. Don't introduce React, Tailwind, or any frontend framework. This app is intentionally simple HTML + a small amount of vanilla JS in templates.
