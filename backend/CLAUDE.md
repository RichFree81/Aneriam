# Backend CLAUDE.md — Aneriam

Read `/CLAUDE.md` at the repo root first. This file covers backend-specific rules.

## Stack (pinned — do not switch)

- Python 3.13
- FastAPI + Uvicorn[standard]
- SQLModel (SQLAlchemy + Pydantic bridge)
- PostgreSQL (prod) / SQLite (tests, via SQLModel default)
- Alembic for migrations
- Pydantic v2 (with `pydantic[email]` for `EmailStr`)
- `python-jose[cryptography]` for JWT
- `passlib[argon2]` for password hashing
- `pytest` + `httpx` for tests

**Planned additions** (not yet installed):
- `ruff` — linting + formatting
- `mypy` — type checking
- `pre-commit` — hook runner
- `structlog` — structured logging
- `sentry-sdk` — error tracking

Do not switch frameworks, ORMs, or auth libraries. The stack is deliberate.

## File structure

```
backend/
├── .env                          # Gitignored; local dev only
├── .env.example                  # Template for required env vars
├── alembic.ini
├── alembic/versions/             # Migrations — APPEND ONLY
├── app/
│   ├── main.py                   # App init, CORS, router registration, startup validation
│   ├── schemas.py                # All Pydantic request/response schemas (split per domain when > 300 lines)
│   ├── api/
│   │   ├── deps.py               # Auth + tenancy dependencies — DO NOT REWRITE
│   │   ├── auth.py               # /auth/* routes
│   │   ├── users.py              # /users/* routes
│   │   ├── modules.py            # /modules/* routes
│   │   ├── portfolios.py         # /portfolios/* routes
│   │   ├── projects.py           # /projects/* routes (nested under portfolios)
│   │   ├── settings.py           # /settings/* routes
│   │   ├── fields.py             # /field-definitions, /field-assignments, /field-values
│   │   ├── financial_notes.py    # Full CRUD + workflow transitions
│   │   ├── portfolio_access.py   # Grant/revoke portfolio access
│   │   ├── collaboration.py      # Cross-company project collaborators
│   │   ├── audit.py              # /audit query
│   │   └── health.py             # /health
│   ├── core/
│   │   ├── database.py           # Engine + get_session
│   │   ├── security.py           # JWT, Argon2, revocation, rate limit — DO NOT REWRITE
│   │   ├── audit.py / audit_log.py  # Audit helpers
│   │   ├── money.py              # Decimal / money helpers
│   │   └── workflow.py           # Workflow state helpers
│   ├── models/
│   │   ├── mixins/               # AuditMixin, WorkflowMixin — DO NOT MODIFY SEMANTICS
│   │   └── *.py                  # One SQLModel class per file
│   └── scripts/
│       ├── seed.py               # Dev seed — must not overwrite existing credentials
│       └── cleanup_test_data.py
└── tests/                        # pytest + rollback fixture (conftest.py)
```

## Authentication dependencies — use these, never reimplement

All defined in `app/api/deps.py`. If you find yourself writing your own auth check, stop.

- **`Depends(get_current_user)`** — any authenticated user. Validates JWT, checks revocation, returns `User`.
- **`Depends(require_company_admin)`** — company admin OR system superuser. Returns a `RequestContext`.
- **`Depends(require_admin)`** — system superuser only (`is_superuser=True`).
- **`Depends(get_request_context)`** — authenticated + has a company assignment. Returns `RequestContext` with `company_id`, `allowed_portfolio_ids`, `roles`, `is_company_admin`.
- **`Depends(get_valid_portfolio)`** — the critical tenancy guard. Every endpoint that takes a `portfolio_id` MUST use this. It:
  - Enforces `deleted_at IS NULL`
  - Enforces `portfolio.company_id == context.company_id`
  - Returns **404 (not 403)** on cross-tenant access — to hide existence
  - For non-company-admins, verifies a `PortfolioUser` grant exists

**Password hashing:** use `app/core/security.get_password_hash` / `verify_password`. Never call passlib directly.

**JWT creation/validation:** use `create_access_token`, `create_refresh_token`, `is_token_revoked`, `revoke_token` from `app/core/security`. Never hand-roll JWTs.

## Multi-tenancy discipline

This is not optional. Violations are security bugs.

- Every tenant-scoped table carries `company_id`, indexed.
- Every endpoint that reads or writes tenant data filters by `company_id` from the `RequestContext`.
- Every endpoint that takes `portfolio_id` in the path depends on `get_valid_portfolio` — never look up a portfolio manually.
- The denormalization pattern for `company_id` (e.g., on `project`, `financial_note`, `portfolio_user`) is enforced at write time: `entity.company_id == entity.portfolio.company_id`. Preserve the invariant when adding write paths.

When creating a new tenant-scoped table:
1. Add `company_id: int = Field(foreign_key="company.id", index=True)`.
2. Add a migration following the three-step pattern if retrofitting (nullable → backfill → NOT NULL + FK). See `b2c3d4e5f607_add_company_id_to_project.py` for the template.
3. Never drop a foreign key without a restoration plan. See `a1b2c3d4e5f6_restore_portfolio_user_company_fk.py` for the cost of breaking this rule.

## Soft-delete discipline

Tables with `deleted_at`: `portfolio`, `project`, `portfolio_user`, `financial_note`.

- Every `SELECT` against these tables filters `.where(Model.deleted_at.is_(None))`.
- Deletes are updates: `entity.deleted_at = datetime.utcnow()` + commit. Never `DELETE FROM`.
- There is no global query filter yet. Until one exists, this is a hard-coded discipline.
- When adding a new list endpoint on a soft-deletable table, audit the query: if the filter is missing, tombstones leak to the UI.

## Error shape — one shape, everywhere

```python
raise HTTPException(status_code=..., detail="human-readable message")
```

FastAPI serializes to `{"detail": "..."}`. The frontend's `ApiError` reads `error.detail`. Do not invent `{"error": "..."}`, `{"message": "..."}`, or custom envelopes.

Status code conventions:
- **401** — unauthenticated (missing/invalid token)
- **403** — authenticated but forbidden (wrong role, inactive user)
- **404** — not found OR hiding cross-tenant existence (use 404 deliberately for the latter)
- **409** — conflict (workflow state, unique constraint, already-exists)
- **422** — Pydantic validation failure (automatic — FastAPI produces this)
- **429** — rate-limited

Pydantic 422 errors produce `{"detail": [...]}` with a list of field errors. Plan: a global exception handler will normalize these into a cleaner shape. Track this as tech debt in `CLAUDE.md` once the handler exists.

## Request and response schemas

- Request bodies: Pydantic models with explicit constraints (`min_length`, `max_length`, `EmailStr`). Never accept `dict` / `Any`.
- Response models: every route declares `response_model=` explicitly.
- Schemas live in `app/schemas.py` today. When that file exceeds ~300 lines, split per domain (`app/schemas/auth.py`, `app/schemas/portfolio.py`, etc.).

**Naming conventions for schemas:**
- `XCreate` — request body for POST
- `XUpdate` — request body for PATCH (fields all optional)
- `XRead` — response body
- Plain `X` is acceptable for simple read-through models (e.g., `Portfolio` mirrors the SQLModel)

## Database access

- Sessions come from `Depends(get_session)` — never create ad-hoc engines inside routes.
- Queries use SQLModel's `select(Model).where(Model.field == value)` syntax.
- **Never** use `f"SELECT ... {value}"` or string concatenation in SQL.
- **Never** pass user input to `text()`. If you must use raw SQL (you almost never must), parameterize via `bindparam`.
- Every tenant-scoped query starts with the `company_id` filter derived from `RequestContext`.

## Alembic migrations

- Migrations live in `alembic/versions/` and are append-only.
- Create via `alembic revision -m "add_description_to_portfolio"` — never hand-edit the `down_revision` chain.
- Every migration has a working `downgrade()`. Test it locally before merging.
- Denormalization retrofits follow the three-step pattern: add nullable → backfill via JOIN or script → `ALTER COLUMN ... NOT NULL` + add FK + index. Never in a single migration.
- Destructive migrations (dropping columns, renaming) require a real downgrade path. See `32d7cd9ae5ab` for an example.
- If a past migration broke an invariant (e.g., dropped a FK that should not have been dropped), add a repair migration. See `a1b2c3d4e5f6`.

## Testing

Tests live in `backend/tests/`. `conftest.py` provides a rollback-per-test DB fixture — use it.

Minimum test coverage for a new route:
1. One happy-path integration test (expected input → expected output).
2. One 401 test (missing/invalid auth).
3. One 403 test (if role-gated).
4. One 404 test specifically for cross-tenant access (user in company A cannot see portfolio in company B — must return 404, not 403).
5. For financial or workflow-facing changes, one test asserting an audit log row was written.

Run via `pytest` from the `backend/` directory. CI (once in place) will gate merges on green tests.

## Configuration and secrets

- `.env.example` lists every required env var with a placeholder value. Never commit a real `.env`.
- New config values: add to `.env.example` with a comment explaining what it does, then read via `os.getenv()` in the module that needs it.
- Required at startup: `JWT_SECRET`, `DATABASE_URL`, `BACKEND_CORS_ORIGINS`. `validate_security_config()` in `core/security.py` refuses to boot without `JWT_SECRET`.
- **Never log secrets.** Never include them in error messages. Never include them in audit logs.

## Logging

Today: plain `logging` module with module-level loggers.

```python
import logging
logger = logging.getLogger(__name__)
logger.info("user_created", extra={"user_id": user.id, "company_id": ctx.company_id})
```

Never `print(...)` from route handlers or business logic. `print` in tests or scripts is fine.

Structured logging (`structlog`) + correlation IDs is planned. Until it arrives, use the `extra=` dict pattern so the future migration preserves context.

## OpenAPI → TypeScript sync

The frontend generates its types from the OpenAPI document FastAPI exposes at `/openapi.json`.

- **Every schema change is a frontend change too.** After editing a Pydantic model, regenerate `frontend/src/api/generated.ts`.
- **Every enum value is a two-sided change.** Python enum in `app/models/` AND TypeScript enum in `frontend/src/types/enums.ts` — same commit.
- CI (once in place) will regenerate and fail the build on drift.

If you're about to change a schema without touching the frontend, stop and think about what the frontend currently expects.

## Known gaps — do not silently "fix" these, raise them

- **No CI** — planned. Don't wire up your own CI without coordination.
- **No Dockerfile** — planned. Don't wire up your own Dockerfile without coordination.
- **No ruff / mypy config** — planned. Don't introduce your own linting config without coordination.
- **`slowapi` in requirements.txt is unused** — the actual rate limiter is hand-rolled in `core/security.py` (login only, in-memory, per-process). Don't delete `slowapi` unless replacing with a working Redis-backed setup.
- **No global exception handler** — Pydantic 422 errors stringify ugly on the frontend. Planned.
- **No structured logging / correlation IDs / Sentry** — planned.
- **`POST`/`PATCH` on `/projects/*` don't require admin, but `DELETE` does** — intentional asymmetry to be confirmed with the user. Don't "fix" to symmetric without asking.
- **`PATCH /modules/{key}/enabled` takes `enabled` as a query param, not a body** — unusual but working. Don't change without coordinating the frontend update.
- **`seed.py` hardcodes `admin@aneriam.com / adminpass`** and overwrites on every run — fix planned (password from env, refuse to overwrite existing user).
- **CORS `allow_methods=["*"]` / `allow_headers=["*"]`** — tighten before production, not now.
- **No `/auth/forgot-password`** — needed before public launch, not now.

## Files never to touch without explicit approval

- `app/core/security.py` — JWT, Argon2, rate-limit. A bug here is a security incident.
- `app/api/deps.py` — `get_valid_portfolio` and the auth dependencies are the tenancy chokepoint.
- `app/models/mixins/` — AuditMixin and WorkflowMixin semantics are depended on by FinancialNote.
- Any file under `alembic/versions/` — migrations are append-only.
- `.env` and `.env.example` — secret management.

## When adding a new endpoint

1. Decide the router: existing domain or new? If new, create `app/api/<domain>.py` and register in `main.py`.
2. Decide auth: which dependency? If it touches a portfolio, it's `get_valid_portfolio`. If it's admin-only, `require_company_admin`. If it's authenticated, `get_request_context` or `get_current_user`.
3. Define request and response Pydantic models in `schemas.py`.
4. Write the route — SQLModel `select`, filter by `company_id`, filter by `deleted_at IS NULL` if applicable.
5. Declare `response_model=` on the route decorator.
6. Write tests (happy path, 401, 403 if role-gated, 404 for cross-tenant).
7. Regenerate the frontend's `generated.ts` and update any frontend API module that needs the new surface.

## When adding a new model / table

1. Add `app/models/<n>.py` with the SQLModel class. Include `company_id` if tenant-scoped.
2. Include `created_at` / `updated_at` (via `AuditMixin`) if change-tracked.
3. Include `deleted_at` if soft-deletable — update §7 of this file when you do.
4. `alembic revision --autogenerate -m "..."` — then review the generated migration carefully.
5. Test the `downgrade()` locally.
6. Update `schemas.py` with the corresponding Pydantic schemas.
7. Update the frontend's `generated.ts`.
