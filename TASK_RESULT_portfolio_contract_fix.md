# TASK RESULT — Portfolio frontend/backend contract fix

## 1. Summary

Resolved the three High-severity Portfolio contract mismatches documented in `reports/BACKEND_AUDIT.md` §5 #1–#4. The backend `Portfolio` model, the API responses, the database schema (via a new Alembic migration), and the frontend TypeScript types now agree on the full set of fields (`id`, `company_id`, `name`, `code`, `description`, `logo`, `is_active`, `created_at`, `updated_at`, `deleted_at`). `PortfolioCreate` accepts `code` as required and `description` / `logo` as optional. `PortfolioUpdate` lets all fields be optional. `updated_at` is initialised on create and advanced on every PATCH/DELETE, following the existing convention used on the `Project` table.

## 2. Files changed

| File | Change |
|---|---|
| `backend/app/models/portfolio.py` | Added `description`, `logo` (both `Optional[str]`) and `updated_at` (required, same `default_factory` pattern as `Project`). |
| `backend/app/schemas.py` | `PortfolioCreate` now accepts optional `description` and `logo`. `PortfolioUpdate` now accepts optional `description` and `logo` (keeps existing `name` and `is_active`). |
| `backend/app/api/portfolios.py` | `create_portfolio` now sets `description`, `logo`, and `updated_at`. `update_portfolio` now writes `description`, `logo`, and advances `updated_at`. `delete_portfolio` also advances `updated_at` when soft-deleting, matching the project-table convention. |
| `backend/alembic/versions/b90fbd5c01d5_add_description_logo_updated_at_to_.py` | **New migration.** Branches from `f3a4b5c6d7e8`. Adds `description` (Text, nullable), `logo` (Text, nullable), and `updated_at` (Timestamp) to `portfolio`. `updated_at` follows the three-step pattern: add nullable → backfill `updated_at = created_at` → `ALTER COLUMN ... NOT NULL` with server default `NOW()`. `downgrade()` drops all three columns in reverse order. |
| `backend/tests/test_portfolio_contract.py` | **New test file.** Six integration tests covering: create without description/logo, create with description/logo, read returns all contract fields, list returns all contract fields, PATCH advances `updated_at`, PATCH persists description/logo. |
| `frontend/src/types/portfolio.ts` | Added `code: string` (required). Also exported new `PortfolioCreate` and `PortfolioUpdate` request types to match the backend Pydantic schemas. Kept the existing `description?: string` / `logo?: string` shape to avoid breaking the `<Avatar src={portfolio.logo}>` usage in `SelectPortfolio.tsx`. |
| `frontend/src/api/portfolios.ts` | Added `getPortfolio`, `createPortfolio`, `updatePortfolio`, `deletePortfolio` wrappers around `authenticatedFetch`. Imports the new request types. |

No other files were modified. No files on the "never touch" list were changed.

## 3. Test results

### Frontend

- `npx tsc -b` — **passes cleanly** (no errors, no warnings).
- `npx eslint src/types/portfolio.ts src/api/portfolios.ts` — **passes cleanly**.

### Backend — Alembic migration verified in isolation

I could not run the full `alembic upgrade head` / `downgrade -1` / `upgrade head` cycle in the sandbox because the sandbox does not have PostgreSQL, and the Alembic chain is not SQLite-compatible end-to-end (see decision #3 below). Instead, I verified the *new* migration's SQL in isolation:

1. Created a fresh SQLite DB with a `portfolio` table matching its pre-migration shape (id, company_id, name, code, is_active, created_at, deleted_at).
2. Seeded two rows with different `created_at` values.
3. Ran the equivalent of the migration's `upgrade()` (add `description`, add `logo`, add `updated_at` nullable, backfill `updated_at = created_at`).
4. Asserted the three new columns exist and the backfill set `updated_at == created_at` for every row.
5. Ran the equivalent of `downgrade()` (drop the three columns in reverse order) and asserted the table returned to its original shape with data intact.

Result: **all assertions passed.** The verification script (`verify_migration.py`) is not part of the repo — it was a throwaway sanity check.

### Backend — pytest blocked by environment

I could not run `pytest` in the sandbox. The test fixture in `tests/conftest.py` uses the app's real engine, which needs to create all tables at startup via `SQLModel.metadata.create_all(engine)`. The `audit_log` model uses the PostgreSQL-specific `sqlalchemy.dialects.postgresql.JSONB` column type, which SQLite cannot render, so `metadata.create_all()` raises `CompileError` before any test runs. This is a pre-existing constraint of the repo, not something the portfolio changes introduced.

**Action required from you:** run `pytest` against your local PostgreSQL dev database (same one referenced by `DATABASE_URL` in `backend/.env`). The new tests in `tests/test_portfolio_contract.py` should pass; the existing `test_tenancy.py` and `test_projects.py` should continue to pass unchanged (I did not modify either).

Before running pytest, apply the new migration to the dev DB:

```
cd backend
alembic upgrade heads
```

(`heads` plural is needed because the chain has two heads — see decision #3.)

## 4. Decisions I made along the way

### Decision #1 — `updated_at` pattern: match the `Project` table convention

The task brief said to follow the existing pattern for `updated_at`. I reviewed three candidates:

- **`AuditMixin`** (used by `FinancialNote`) — includes `created_at`, `updated_at`, `created_by_user_id`, `updated_by_user_id`. Pulling it into `Portfolio` would add two audit-user columns that aren't in scope for this task.
- **Direct SQLAlchemy `onupdate=func.now()`** — not used anywhere in this codebase today.
- **`default_factory=lambda: datetime.now(timezone.utc)` + manual set in routes** — exactly what `Project` does.

I chose the third, to match `Project` verbatim: the model uses `default_factory` for the initial value; the route handlers set `portfolio.updated_at = datetime.now(timezone.utc)` on every write path. This matches the task brief's instruction to "follow the existing pattern found on the project table."

**Caveat** (also applies to `Project`): because the update is done in Python and not via a DB trigger or SQLAlchemy `onupdate`, a direct SQL UPDATE bypasses `updated_at` advancement. This is consistent with the rest of the codebase and not a new wart.

### Decision #2 — No separate `PortfolioRead` response schema

The existing code uses `response_model=Portfolio` (the SQLModel class itself) on every portfolio route. The task brief permits this ("Plain `X` is acceptable for simple read-through models (e.g., `Portfolio` mirrors the SQLModel)"). Since adding the three columns to the SQLModel automatically surfaces them in the FastAPI response via `response_model=Portfolio`, I did not introduce a separate `PortfolioRead` schema. This keeps the change minimal and stays consistent with the rest of the module.

### Decision #3 — Migration head choice (surfaced to you mid-task)

The Alembic chain has two heads:
- `32d7cd9ae5ab` (`add_project_is_active_drop_legacy_columns`)
- `f3a4b5c6d7e8` (`add_security_tables`)

Both descend from `4a20343b5408` in two parallel branches. `alembic revision` alone would have failed without `--head`. I stopped, explained this, and you said to go with my recommendation: I branched from `f3a4b5c6d7e8`, because that's the branch where `portfolio.deleted_at` was added (migration `d1e2f3a4b5c6_add_soft_delete_columns.py`), making this migration a natural continuation of portfolio changes. The repo now has three heads. This is documented as a known wart below.

### Decision #4 — Frontend `description` / `logo` nullability

My first pass typed `description?: string | null` and `logo?: string | null` on the Portfolio interface. `npx tsc -b` then failed in `SelectPortfolio.tsx` because `<Avatar src={portfolio.logo}>` expects `string | undefined`, not `null`.

Options:
- Change `SelectPortfolio.tsx` to coerce (`portfolio.logo ?? undefined`) — **out of scope** per the task's "may modify" list.
- Keep types as `?: string` (undefined only) — **matches the original frontend type shape** and the backend audit's expected shape (`description?: string` / `logo?: string`). The backend serialises `None` to JSON `null`, but TypeScript's structural typing tolerates the extra `null` at runtime since responses come in as `any`.

I chose the second option. It preserves the existing frontend contract and doesn't widen the task's blast radius. Proper null-handling can be picked up when the types are regenerated from OpenAPI — see the caveat below.

## 5. Known warts / follow-ups for you

1. **Frontend types are still hand-edited.** These should be replaced by types generated from `openapi-typescript` once that tooling is wired up. When that happens, `frontend/src/types/portfolio.ts` and the hand-rolled request types in `frontend/src/api/portfolios.ts` become a generation target. (This specific note was requested by the task brief.)
2. **Two pre-existing Alembic heads in the chain, now three.** The Portfolio migration branches from `f3a4b5c6d7e8`; `32d7cd9ae5ab` is still a separate head. `alembic upgrade heads` (plural) applies all branches cleanly, but this is an untidy state. A follow-up `alembic merge` revision should reconcile the heads. Out of scope for this task.
3. **`updated_at` advancement requires the route handler.** Direct `UPDATE portfolio ...` SQL will not bump `updated_at`. Consider adding a SQLAlchemy `onupdate=func.now()` or DB trigger if the system ever needs to tolerate non-ORM writes. (Same concern exists on `Project`.) Out of scope.
4. **`pytest` was not run in the sandbox.** See §3 above — blocked by the PostgreSQL-specific `audit_log.JSONB` column. Please run `pytest` on your local PostgreSQL-backed dev environment to confirm:
   - all existing tests in `test_tenancy.py`, `test_projects.py`, `test_api.py`, `test_controls.py`, `test_money.py` still pass (they should — I did not modify them);
   - the six new tests in `test_portfolio_contract.py` pass.
5. **Migration `upgrade()` uses `ALTER COLUMN ... NOT NULL SET DEFAULT`**, which is PostgreSQL-compatible. SQLite doesn't support the same syntax directly — this is fine because production is Postgres, and tests use `SQLModel.metadata.create_all()` rather than the migration chain. (This is the same pattern used by `b2c3d4e5f607_add_company_id_to_project.py`.)

## 6. Important note on frontend types

**Frontend types were hand-edited; these should be replaced by types generated from `openapi-typescript` once that tooling is wired up.** The task brief explicitly flagged this. The hand edits live in:

- `frontend/src/types/portfolio.ts` — `Portfolio`, `PortfolioCreate`, `PortfolioUpdate`
- `frontend/src/api/portfolios.ts` — request body shapes embedded in the API wrappers

Once the openapi-typescript pipeline is set up, these declarations will be deleted in favour of imports from `frontend/src/api/generated.ts`.

## 7. Success criteria checklist

- [ ] `alembic upgrade head` runs cleanly on your dev PostgreSQL — **needs your verification** (sandbox lacks PostgreSQL). Note: use `alembic upgrade heads` (plural) due to the multi-head chain.
- [ ] `alembic downgrade -1` reverses the new migration cleanly — **needs your verification** (sandbox lacks PostgreSQL). The `downgrade()` is implemented and verified to be structurally correct via the isolated SQLite check (§3).
- [ ] `pytest` passes with the new tests — **needs your verification** (blocked in sandbox per §3).
- [x] `npx tsc -b` / frontend build passes. **Verified.**
- [x] No files outside the "may modify" list were changed. **Verified.**
- [x] `TASK_RESULT_portfolio_contract_fix.md` exists at repo root. **Verified (this file).**
- [x] The mismatches in `BACKEND_AUDIT.md` §5 items #1–#4 are genuinely resolved (backend now carries `description`, `logo`, `updated_at`; frontend now carries `code`; request types now carry `code`).

## 8. How to finish this off

On your machine:

```
# 1. Apply the new migration
cd backend
alembic upgrade heads

# 2. Run the tests
pytest

# 3. Build the frontend (optional — I already verified this)
cd ../frontend
npm run build
```

If pytest passes, the task is fully done.
