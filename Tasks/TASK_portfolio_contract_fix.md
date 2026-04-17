# Task: Fix the Portfolio frontend-backend contract mismatch

## Context

This task resolves the three High-severity contract mismatches documented in `BACKEND_AUDIT.md` §5 items #1–#4. The frontend currently expects fields on `Portfolio` that the backend does not provide (`description`, `logo`, `updated_at`), and the backend requires a field on create that the frontend does not know about (`code`). This will break any Portfolio UI the moment it tries to render or create a portfolio with those fields.

This is also the first meaningful task executed since `CLAUDE.md`, `frontend/CLAUDE.md`, and `backend/CLAUDE.md` were introduced. The conventions in those files are binding.

## Before you start

Read, in this order:

1. `CLAUDE.md` at the repo root
2. `backend/CLAUDE.md`
3. `frontend/CLAUDE.md`
4. `BACKEND_AUDIT.md` §5 items #1–#4 (for context on the mismatch)
5. `backend/app/models/portfolio.py` (the current model)
6. `backend/app/schemas.py` (specifically the `Portfolio`, `PortfolioCreate`, `PortfolioUpdate`, `PortfolioRead` schemas)
7. `backend/app/api/portfolios.py` (the routes)
8. `frontend/src/types/portfolio.ts` (the frontend type)
9. `frontend/src/api/portfolios.ts` (the frontend API module)
10. At least two existing Alembic migrations under `backend/alembic/versions/` — pick recent ones — to match the style and conventions used in this project.

Do not skim. The CLAUDE.md files contain hard rules that will reject your work if violated.

## Objective

Make the backend Portfolio model, Pydantic schemas, API responses, database schema, and frontend TypeScript types all consistent with each other. After this task, all of these are true:

- The `portfolio` database table has `description` (nullable TEXT), `logo` (nullable TEXT), and `updated_at` (non-null TIMESTAMP, default NOW) columns in addition to its existing columns.
- The `Portfolio` SQLModel class in `backend/app/models/portfolio.py` has matching fields.
- The `PortfolioCreate` schema accepts `description` and `logo` as optional. `code` remains required with its 1–50 length constraint.
- The `PortfolioUpdate` schema accepts `description`, `logo`, and (continuing existing pattern) all other fields as optional.
- The `PortfolioRead` / `Portfolio` response schema returns `id`, `name`, `code`, `description`, `logo`, `company_id`, `created_at`, `updated_at`, `deleted_at`.
- `updated_at` is automatically set on every UPDATE, either via SQLAlchemy's `onupdate=func.now()` or via the existing `AuditMixin` pattern if appropriate — check how `updated_at` is handled on the `project` table and follow that convention.
- A new Alembic migration adds the three columns with a working `downgrade()`. The migration backfills `updated_at` to `created_at` for existing rows before making it NOT NULL.
- The frontend `Portfolio` TypeScript type in `frontend/src/types/portfolio.ts` includes `code` (required).
- The frontend `PortfolioCreate` type (or equivalent request shape in `frontend/src/api/portfolios.ts`) includes `code` (required) and `description`, `logo` (optional).
- Existing tests still pass (`pytest` in `backend/`).
- New tests cover: creating a portfolio with and without `description`/`logo`; reading a portfolio and seeing all new fields; updating a portfolio and verifying `updated_at` advances.

## What you must NOT do

- Do not edit `backend/app/api/deps.py`, `backend/app/core/security.py`, or any existing file under `backend/alembic/versions/`. These are on the "never touch" list.
- Do not introduce any new dependencies, libraries, or tools. No `sqlalchemy-utils`, no new Pydantic validators from third-party packages.
- Do not normalize the existing asymmetric authorization on `/projects` POST/PATCH/DELETE — that's a separate decision the user has not made.
- Do not "fix" any of the other known warts documented in the CLAUDE.md "known warts" section. Stay focused on Portfolio.
- Do not switch styling approaches, state management, form libraries, or any stack decision on the frontend.
- Do not regenerate `frontend/src/api/generated.ts` as part of this task — the OpenAPI → TypeScript generation is not set up yet. Update `frontend/src/types/portfolio.ts` and `frontend/src/api/portfolios.ts` by hand for now. Make a note in your final summary that these hand-edits will be replaced by generated types once `openapi-typescript` is wired up.
- Do not hand-edit the `down_revision` chain of migrations. Use `alembic revision -m "add_description_logo_updated_at_to_portfolio"`.

## Scope boundaries — files you may modify

You may modify:

- `backend/app/models/portfolio.py`
- `backend/app/schemas.py` (only the Portfolio-related schemas)
- `backend/app/api/portfolios.py` (only if needed to surface new fields — the routes themselves shouldn't need changes if response_model is used correctly)
- `backend/alembic/versions/` (ADD one new migration file only)
- `backend/tests/` (add tests to an existing file if appropriate, or create `test_portfolio_contract.py`)
- `frontend/src/types/portfolio.ts`
- `frontend/src/api/portfolios.ts`

You may NOT modify anything else. If you believe you need to, stop and ask.

## Step-by-step plan you should follow

1. **Read everything listed under "Before you start."** Do not skip this.
2. **Inspect the `project` table's `updated_at` pattern** — understand whether it uses `AuditMixin`, a direct `onupdate=func.now()`, or something else. Match that pattern on `Portfolio`.
3. **Update `backend/app/models/portfolio.py`** — add `description: Optional[str] = None`, `logo: Optional[str] = None`, and `updated_at` following the pattern you found in step 2.
4. **Generate the migration**: `cd backend && alembic revision -m "add_description_logo_updated_at_to_portfolio"`.
5. **Edit the new migration file** to:
   - Add `description` (Text, nullable) in `upgrade()`.
   - Add `logo` (Text, nullable) in `upgrade()`.
   - Add `updated_at` nullable first, backfill `UPDATE portfolio SET updated_at = created_at WHERE updated_at IS NULL`, then `ALTER COLUMN updated_at SET NOT NULL` with server default `NOW()`.
   - `downgrade()` drops all three columns in reverse order.
6. **Run `alembic upgrade head`** against the local dev database to verify the migration works. If it fails, fix it. Then run `alembic downgrade -1` to verify the downgrade works. Then `alembic upgrade head` again.
7. **Update the Pydantic schemas in `backend/app/schemas.py`:**
   - `PortfolioCreate`: add `description: Optional[str] = None`, `logo: Optional[str] = None`. Keep `code` required with existing constraints.
   - `PortfolioUpdate`: add `description` and `logo` as optional.
   - `Portfolio` / `PortfolioRead` (response): add all three new fields as returned.
8. **Update `backend/app/api/portfolios.py`** only if needed — if `response_model` is declared and the underlying model has the fields, FastAPI should serialize them automatically. Verify.
9. **Add tests** covering:
   - Creating a portfolio WITHOUT `description`/`logo` — still works.
   - Creating a portfolio WITH `description`/`logo` — fields persist and return.
   - Reading a portfolio — all new fields are present (even if null).
   - Updating a portfolio — `updated_at` advances past `created_at`.
   - The existing `test_tenancy.py` tests still pass unchanged.
10. **Run `pytest`** — all tests must pass. If any fail, fix the underlying issue.
11. **Update `frontend/src/types/portfolio.ts`:**
    - Add `code: string` (required) to the `Portfolio` interface.
    - Confirm `description?: string`, `logo?: string`, `updated_at: string` are present (the frontend audit said they were; verify).
12. **Update `frontend/src/api/portfolios.ts`:**
    - If there's a `PortfolioCreate` or equivalent request type, add `code: string` (required), `description?: string`, `logo?: string`.
    - Ensure any list/get/update/create function signatures align with the new types.
13. **Run `cd frontend && npm run build`** — or whatever the frontend build command is — to verify TypeScript still compiles. If it doesn't, fix the usage site (some page or component is probably using the old `Portfolio` type without `code`).
14. **Write a summary of what you changed** (see final deliverable below).

## If you hit a decision you cannot make

Stop and summarize the decision cleanly. Do not guess. Example of the right behavior:

> "The `project` table uses `AuditMixin` for `updated_at`, which also provides `created_by_user_id` and `updated_by_user_id`. Adding `AuditMixin` to `Portfolio` would also add these audit fields — which are not in scope for this task. I can either:
> (a) add `updated_at` directly via `Field(..., sa_column_kwargs={'onupdate': func.now()})` without the full mixin,
> (b) add the full `AuditMixin` to Portfolio (scope expansion),
> (c) create a lightweight `TimestampMixin` that only provides `created_at` + `updated_at`.
> Which do you prefer?"

That's the kind of question worth stopping for.

## Final deliverable

When the task is complete, write a file at the repo root called `TASK_RESULT_portfolio_contract_fix.md` containing:

1. A one-paragraph summary of what was changed.
2. A list of every file modified, with a one-line description of the change.
3. The test results (number passing, number failing — should be all passing).
4. Any decisions you made along the way that the user should be aware of.
5. Any known warts introduced, caveats, or follow-ups the user should track.
6. A specific note: "Frontend types were hand-edited; these should be replaced by types generated from `openapi-typescript` once that tooling is wired up."

This file is what the user reviews when they come back to the session.

## Success criteria recap

The task is complete when all of these are true:

- [ ] `alembic upgrade head` runs cleanly from an empty DB and ends with the `portfolio` table having `description`, `logo`, `updated_at` columns.
- [ ] `alembic downgrade -1` reverses the new migration cleanly.
- [ ] `pytest` in `backend/` passes with the new tests included.
- [ ] `npm run build` (or `tsc -b`) in `frontend/` passes.
- [ ] No files outside the "may modify" list have been changed.
- [ ] `TASK_RESULT_portfolio_contract_fix.md` exists at repo root.
- [ ] The mismatches in `BACKEND_AUDIT.md` §5 items #1–#4 are genuinely resolved (not worked around).
