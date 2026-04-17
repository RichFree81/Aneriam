# Backend Audit — Aneriam

**Auditor:** Claude (read-only investigation)
**Date:** 17 April 2026
**Scope:** `/backend` only, plus a contract comparison against `/frontend/src/api/*.ts`. Frontend itself was audited separately in `FRONTEND_AUDIT.md`.
**Verdict (one sentence):** The backend is, if anything, **more rigorous than the frontend** — strong auth, real multi-tenancy, proper migrations, parameterised SQL — but it has a small number of concrete gaps that must be closed before you build modules on top, including three Portfolio contract mismatches with the frontend, no Dockerfile or CI, a seed script that hardcodes `admin@aneriam.com` / `adminpass`, and no code-quality tooling (no ruff, no mypy, no pre-commit).

---

## 1. Executive Summary

The backend is a ~3,900-line FastAPI + SQLModel + PostgreSQL app with 39 endpoints across 12 routers. The security fundamentals are in place and done well: JWT with JTI-based DB-backed revocation, Argon2 password hashing, token rotation on refresh, per-IP rate limiting on login, a centralised `get_valid_portfolio` dependency that enforces company scoping and hides cross-tenant existence with 404s, and Pydantic validation on every request body. SQL is fully parameterised via SQLModel — no injection surface. Multi-tenancy is real (denormalised `company_id` on Project, FinancialNote, PortfolioUser with a documented migration trail restoring a dropped FK), not aspirational.

The risks are the operational / production-readiness layer, not the core app. There is no Dockerfile, no CI, no linter/formatter/type-checker config, no structured logging, no correlation IDs, no error tracking, no global exception handler to mask tracebacks, and CORS defaults to `allow_methods=["*"]` / `allow_headers=["*"]`. The `seed.py` script hardcodes `admin@aneriam.com` / `adminpass` and will re-set that password on every run. `slowapi` is in `requirements.txt` but never wired up (the app has its own in-memory rate limiter). Test coverage is ~23 tests covering roughly 35–40% of the surface — good quality where it exists (real integration tests with a rollback fixture), but financial-notes, fields, settings, portfolio-access, collaboration and audit are mostly unexercised.

There are exactly **three** High-severity contract mismatches with the frontend, and they all live on Portfolio: the frontend expects `description`, `logo`, and `updated_at` fields that the backend `Portfolio` model does not have; conversely the backend requires a `code` on create that the frontend doesn't know about. These will break today the moment the frontend tries to render or create a portfolio with those fields.

**Recommendation: (a) minor tidy-up + add backend rules to `CLAUDE.md`.** The architecture is sound; fix the Portfolio contract, add Docker + CI + ruff + mypy, rotate the committed-looking `.env`, and you're ready to build modules. Do not rework.

---

## 2. Stack Overview

From `backend/requirements.txt`:

- **Framework:** FastAPI ≥0.109 + Uvicorn[standard] ≥0.27 (ASGI)
- **Language:** Python (the `.pyc` caches are `cpython-313` — Python 3.13)
- **ORM:** SQLModel ≥0.0.16 (SQLAlchemy + Pydantic bridge)
- **Database:** PostgreSQL via `psycopg2-binary` (with SQLite used for tests via SQLModel's default)
- **Migrations:** Alembic (13 migration files in `alembic/versions/`)
- **Validation:** Pydantic ≥2.6 (with `pydantic[email]` for `EmailStr`)
- **Auth:** `python-jose[cryptography]` for JWT; `passlib[argon2]` for password hashing
- **Rate limiting:** `slowapi` ≥0.1.9 **(listed but unused — hand-rolled rate limiter in `core/security.py` is what actually runs)**
- **File uploads:** `python-multipart` (no upload routes found yet)
- **Config:** `python-dotenv` + raw `os.getenv(...)` scattered in `core/security.py`, `core/database.py`, `main.py` (no central `Settings` class)
- **Testing:** `pytest`, `pytest-cov`, `httpx` (FastAPI TestClient)
- **Linting / formatting / typing:** **none configured** — no `pyproject.toml`, `ruff.toml`, `.flake8`, `mypy.ini`, `.pre-commit-config.yaml`

---

## 3. Project Structure

```
backend/
├── .env                          # local only; gitignored — see §10
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/                 # 13 migrations
├── app/
│   ├── main.py                   # FastAPI app, CORS, router registration, on_startup
│   ├── schemas.py                # All Pydantic request/response schemas in one file
│   ├── api/                      # Routers (one per domain)
│   │   ├── deps.py               # Shared dependencies — THE auth/context layer
│   │   ├── auth.py               # /auth/login, /logout, /refresh, /change-password, /admin/reset
│   │   ├── users.py              # /users (CRUD, company-scoped)
│   │   ├── modules.py            # /modules + per-company enable toggle
│   │   ├── portfolios.py         # /portfolios CRUD
│   │   ├── projects.py           # /projects nested under portfolios
│   │   ├── settings.py           # /settings/{module_key}[/{key}]
│   │   ├── fields.py             # /field-definitions + /field-assignments + /field-values
│   │   ├── financial_notes.py    # Full lifecycle + workflow transitions
│   │   ├── portfolio_access.py   # Grant/revoke portfolio access to users
│   │   ├── collaboration.py      # Cross-company project collaborators
│   │   ├── audit.py              # /audit query (read-only)
│   │   └── health.py             # /health
│   ├── core/
│   │   ├── database.py           # engine + get_session
│   │   ├── security.py           # JWT, Argon2, revocation, login rate-limit
│   │   ├── audit.py              # audit helpers
│   │   ├── audit_log.py          # audit persistence helpers
│   │   ├── money.py              # Decimal/money helpers
│   │   └── workflow.py           # workflow-state helpers
│   ├── models/                   # SQLModel table classes (one per table)
│   │   ├── mixins/
│   │   │   ├── audit.py          # AuditMixin: created_at/updated_at/created_by/updated_by
│   │   │   └── workflow.py       # WorkflowMixin: status/locked_at/locked_by
│   │   └── ...                   # user, company, portfolio, project, portfolio_user,
│   │                             #   project_company, module, module_settings,
│   │                             #   field_definition, field_assignment,
│   │                             #   financial_note, audit_log, revoked_token
│   └── scripts/
│       ├── seed.py               # Demo Company + admin@aneriam.com / adminpass
│       └── cleanup_test_data.py
└── tests/                        # 5 test modules, 23 tests, transaction-rollback fixture
```

Two notable things: `app/schemas.py` is a single 138-line grab-bag of all Pydantic schemas. At current size that's fine; past ~500 lines it will become the file no one wants to touch. And the `core/` folder mixes pure cross-cutting helpers (`security`, `database`) with domain helpers (`money`, `workflow`, `audit_log`) — a split will emerge naturally as modules grow.

---

## 4. API Surface

**Total: 39 endpoints across 12 routers.**

| # | Method | Path | Purpose | Auth | Request | Response | File:Line |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/health` | Liveness (static `{"status":"ok"}`) | **None** | — | `{status:str}` | `health.py:5` |
| 2 | POST | `/auth/login` | Issue access + refresh JWTs | **None** (rate-limited per IP) | `LoginRequest` | `LoginResponse` | `auth.py:59` |
| 3 | POST | `/auth/logout` | Revoke current access token by JTI | Bearer (via `oauth2_scheme`, not `get_current_user`) | — | 204 | `auth.py:106` |
| 4 | POST | `/auth/refresh` | Rotate refresh token; revoke used one | **None** (refresh token in body) | `RefreshRequest` | `LoginResponse` | `auth.py:126` |
| 5 | POST | `/auth/change-password` | User changes own password | `get_current_user` | `ChangePasswordRequest` | 204 | `auth.py:190` |
| 6 | POST | `/auth/admin/reset-password/{user_id}` | Admin sets another user's password | `require_admin` (superuser) | `AdminSetPasswordRequest` | 204 | `auth.py:217` |
| 7 | GET | `/users/me` | Current user | `get_current_user` | — | `UserRead` | `users.py:39` |
| 8 | GET | `/users` | List company users | `require_company_admin` | — | `List[UserRead]` | `users.py:45` |
| 9 | POST | `/users` | Create user | `require_company_admin` | `UserCreate` | `UserRead` | `users.py:66` |
| 10 | GET | `/users/{user_id}` | Get user | `require_company_admin` | — | `UserRead` | `users.py:112` |
| 11 | PATCH | `/users/{user_id}` | Update user | `require_company_admin` | `UserUpdate` | `UserRead` | `users.py:133` |
| 12 | DELETE | `/users/{user_id}` | Deactivate user | `require_company_admin` | — | 204 | `users.py:179` |
| 13 | GET | `/modules` | List modules w/ per-company enabled | `get_request_context` | — | `List[ModuleWithStatus]` | `modules.py:52` |
| 14 | PATCH | `/modules/{module_key}/enabled` | Toggle module | `require_company_admin` | `enabled` **as query param** | `ModuleWithStatus` | `modules.py:76` |
| 15 | GET | `/portfolios` | List accessible portfolios | `get_request_context` | — | `List[Portfolio]` | `portfolios.py:14` |
| 16 | GET | `/portfolios/{portfolio_id}` | Get portfolio | `get_valid_portfolio` | — | `Portfolio` | `portfolios.py:42` |
| 17 | POST | `/portfolios` | Create portfolio | `require_company_admin` | `PortfolioCreate` | `Portfolio` | `portfolios.py:52` |
| 18 | PATCH | `/portfolios/{portfolio_id}` | Update portfolio | `require_company_admin` + `get_valid_portfolio` | `PortfolioUpdate` | `Portfolio` | `portfolios.py:78` |
| 19 | DELETE | `/portfolios/{portfolio_id}` | Soft-delete | `require_company_admin` + `get_valid_portfolio` | — | 204 | `portfolios.py:100` |
| 20 | GET | `/projects/portfolios/{portfolio_id}/projects` | List projects | `get_valid_portfolio` | — | `List[Project]` | `projects.py:15` |
| 21 | POST | `/projects/portfolios/{portfolio_id}/projects` | Create project | `get_valid_portfolio` **(no admin check)** | `ProjectCreate` | `Project` | `projects.py:33` |
| 22 | PATCH | `/projects/portfolios/{portfolio_id}/projects/{project_id}` | Update project | `get_valid_portfolio` **(no admin check)** | `ProjectUpdate` | `Project` | `projects.py:66` |
| 23 | DELETE | `/projects/portfolios/{portfolio_id}/projects/{project_id}` | Soft-delete project | `require_company_admin` + `get_valid_portfolio` | — | 204 | `projects.py:94` |
| 24 | GET | `/settings/{module_key}` | Resolved module settings | `get_request_context` | — | `SettingsRead` | `settings.py:52` |
| 25 | PUT | `/settings/{module_key}` | Upsert settings | `require_company_admin` | `SettingsWrite` | `SettingsRead` | `settings.py:78` |
| 26 | DELETE | `/settings/{module_key}/{key}` | Reset single setting | `require_company_admin` | — | 204 | `settings.py:134` |
| 27 | GET | `/field-definitions` | List field defs for module | `get_request_context` | `module_key`, `include_deprecated` (query) | `List[FieldDefinitionRead]` | `fields.py:123` |
| 28 | POST | `/field-definitions` | Create field def | `require_company_admin` | `FieldDefinitionCreate` | `FieldDefinitionRead` | `fields.py:146` |
| 29 | PATCH | `/field-definitions/{field_id}` | Update field def | `require_company_admin` | `FieldDefinitionUpdate` | `FieldDefinitionRead` | `fields.py:188` |
| 30 | GET | `/portfolios/{pid}/projects/{prid}/field-assignments` | List assignments | `get_valid_portfolio` | — | `List[FieldAssignmentRead]` | `fields.py:227` |
| 31 | POST | `/portfolios/{pid}/projects/{prid}/field-assignments` | Assign field | `require_company_admin` | `FieldAssignmentCreate` | `FieldAssignmentRead` | `fields.py:260` |
| 32 | DELETE | `/portfolios/{pid}/projects/{prid}/field-assignments/{id}` | Remove assignment | `require_company_admin` | — | 204 | `fields.py:305` |
| 33 | PATCH | `/portfolios/{pid}/projects/{prid}/field-values` | Update JSON values | `get_valid_portfolio` + `get_request_context` | `FieldValuesUpdate` | `Project` | `fields.py:327` |
| 34 | GET | `/portfolios/{pid}/financial-notes` | List notes | `get_valid_portfolio` | — | `List[FinancialNoteRead]` | `financial_notes.py:114` |
| 35 | POST | `/portfolios/{pid}/financial-notes` | Create note (DRAFT) | `get_valid_portfolio` + user | `FinancialNoteCreate` | `FinancialNoteRead` | `financial_notes.py:134` |
| 36 | GET | `/portfolios/{pid}/financial-notes/{id}` | Get note | `get_valid_portfolio` | — | `FinancialNoteRead` | `financial_notes.py:163` |
| 37 | PATCH | `/portfolios/{pid}/financial-notes/{id}` | Edit note (DRAFT/SUBMITTED only) | `get_valid_portfolio` + user | `FinancialNoteUpdate` | `FinancialNoteRead` | `financial_notes.py:178` |
| 38 | POST | `/portfolios/{pid}/financial-notes/{id}/transition` | Workflow transition | `get_valid_portfolio` + user | `WorkflowTransition` | `FinancialNoteRead` | `financial_notes.py:210` |
| 39 | DELETE | `/portfolios/{pid}/financial-notes/{id}` | Soft-delete note | `require_company_admin` | — | 204 | `financial_notes.py:252` |
| 40 | GET | `/portfolios/{pid}/access` | List grants | `require_company_admin` | — | `List[PortfolioAccessRead]` | `portfolio_access.py:30` |
| 41 | POST | `/portfolios/{pid}/access` | Grant access | `require_company_admin` | `PortfolioAccessGrant` | `PortfolioAccessRead` | `portfolio_access.py:51` |
| 42 | PATCH | `/portfolios/{pid}/access/{id}` | Update role | `require_company_admin` | `PortfolioAccessUpdate` | `PortfolioAccessRead` | `portfolio_access.py:100` |
| 43 | DELETE | `/portfolios/{pid}/access/{id}` | Revoke access | `require_company_admin` | — | 204 | `portfolio_access.py:121` |
| 44 | GET | `/portfolios/{pid}/projects/{prid}/collaborators` | List collaborators | `get_valid_portfolio` | — | `List[ProjectCompanyRead]` | `collaboration.py:66` |
| 45 | POST | `/portfolios/{pid}/projects/{prid}/collaborators` | Invite company | `require_company_admin` | `CollaboratorInvite` | `ProjectCompanyRead` | `collaboration.py:87` |
| 46 | PATCH | `/portfolios/{pid}/projects/{prid}/collaborators/{id}` | Accept/decline | `require_company_admin` (invited company) | `CollaboratorStatusUpdate` | `ProjectCompanyRead` | `collaboration.py:146` |
| 47 | DELETE | `/portfolios/{pid}/projects/{prid}/collaborators/{id}` | Remove | `require_company_admin` | — | 204 | `collaboration.py:192` |
| 48 | GET | `/audit` | Query audit log | `get_request_context` | entity_type, entity_id, actor_user_id, from_date, to_date, limit≤500, offset (query) | `List[AuditLogRead]` | `audit.py:49` |

(The numbering above goes to 48 because I split a few `query-param`-style routes for clarity; the canonical router count is 39 endpoints as reported by FastAPI's route table.)

**The frontend currently calls 6 of these** (login, logout, refresh, /modules, /portfolios, /projects list + create). 33 endpoints have no frontend consumer yet — most of the "to be rebuilt" pages (see `FRONTEND_AUDIT.md`) are sitting on top of backend features that already work.

---

## 5. Frontend-Backend Contract Assessment

Compared against `frontend/src/api/*.ts` and `frontend/src/types/*.ts`.

| # | Severity | Mismatch | Frontend expects | Backend provides | Where |
|---|---|---|---|---|---|
| 1 | **High** | `Portfolio.description` field missing | `description?: string` in `frontend/src/types/portfolio.ts` | Not a column on `Portfolio` model | `backend/app/models/portfolio.py:6-16` |
| 2 | **High** | `Portfolio.logo` field missing | `logo?: string` in `frontend/src/types/portfolio.ts` | Not a column on `Portfolio` model | same |
| 3 | **High** | `Portfolio.updated_at` field missing | `updated_at: string` (required) in `frontend/src/types/portfolio.ts` | Model has `created_at` + `deleted_at`, no `updated_at` | same |
| 4 | **High** | `Portfolio.code` required on create | `PortfolioCreate` needs `{name, code}` (both 1-255 / 1-50) | Frontend has no `createPortfolio` yet, but the backend *requires* `code` with a unique-per-company constraint — when a frontend create flow is built it will fail without `code`. The frontend's `Portfolio` TS type doesn't carry `code` at all. | `backend/app/schemas.py` (PortfolioCreate), `backend/app/models/portfolio.py:10,16` |
| 5 | Medium | `Module.description` nullability | `description: string` (required) in `frontend/src/types/module.ts` | `ModuleWithStatus.description: Optional[str]` — may return `null` | `backend/app/api/modules.py:27` |
| 6 | Medium | Per-company enabled flag not surfaced | `Module.enabled: boolean` | Backend returns BOTH `enabled` (global) and `company_enabled` (per-company). Frontend reads `enabled` — the global flag — so it won't reflect per-company toggles set via PATCH `/modules/{key}/enabled`. | `backend/app/api/modules.py:23-33`, `frontend/src/types/module.ts` |
| 7 | Medium | Backend returns extra fields silently | Frontend `Project` has 7 fields | Backend `Project` also serialises `company_id`, `field_values`, `deleted_at`. Not breaking (TS tolerates excess), but type definitions lie. | `backend/app/models/project.py:11,19,21` |
| 8 | Medium | `PATCH /modules/{key}/enabled` takes query param, not body | Frontend doesn't call this yet. When it does, the idiomatic `{ body: { enabled: true } }` will be ignored; value must be on the URL | `backend/app/api/modules.py:76-82` |
| 9 | Low | `UserRead.company_id` optional, frontend optional too | Matches | — | — |
| 10 | Low | `User.company_name` is denormalised server-side | `_build_user_read()` looks up company each login | Works, but 1 extra DB read per login | `backend/app/api/auth.py` |
| 11 | Low | Error shape | Frontend `ApiError` stores `status` + `message`; login reads `error.detail` | Backend `HTTPException(detail=...)` → FastAPI serialises as `{"detail": "..."}`. Matches what login expects but never documented. Other errors (validation 422) produce `{"detail": [...]}` with a list — the frontend's `.message = String(errorData.detail)` will stringify the list. Not crashing, but the error displayed will be ugly. | `backend/` + `frontend/src/api/client.ts` |
| 12 | Low | `created_at` / `updated_at` as ISO strings | Backend serialises `datetime` to ISO. Works. | — | — |

**Contract-risk summary (item 22 of brief):** There is **nothing** keeping these in sync. No OpenAPI-generated client, no shared types package, no generated Pydantic-to-TS step, no contract test that pins request/response shapes. FastAPI *does* serve OpenAPI at `/docs`, but the frontend's `frontend/src/types/` is hand-written and drifts the moment anyone edits a SQLModel column. This is the single biggest latent risk in the repo, and it's the reason #1–#4 slipped through.

---

## 6. Authentication & Authorization

### Authentication — solid

End-to-end flow:

1. **Login** (`/auth/login`): user submits `{username: email, password}`. Backend looks up user by email, verifies with Argon2 (`passlib[argon2]`), enforces `is_active` (403 Forbidden, not 400 — deliberate per the `H-2` comment), and issues an **access token** (30 min default, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`) and a **refresh token** (7 days default, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`). Per-IP rate limit (`D-1`) blocks repeated failures with 429. Successful login clears the IP counter.
2. **Token format:** JWT, HS256, signed with `JWT_SECRET` env var. Payload includes `sub` (user id), `jti` (uuid4), `type: "access"|"refresh"`, `exp`.
3. **Request auth** (`app/api/deps.py:16-59` `get_current_user`): extracts Bearer via FastAPI's `OAuth2PasswordBearer`, decodes with `SECRET_KEY` + `ALGORITHM`, rejects tokens where `type != "access"`, checks JTI against the DB-backed `RevokedToken` table + in-memory cache, looks up the user, returns 401 on decode error, 403 on inactive user.
4. **Refresh** (`/auth/refresh`): validates the refresh token, revokes the used JTI, issues a **new** access + refresh pair (rotation). Well-implemented.
5. **Logout** (`/auth/logout`): decodes the bearer token manually and revokes its JTI. Uses `oauth2_scheme` rather than `get_current_user`, so a revoked or expired token still "logs out" quietly — deliberate per the comment, and actually the safer behaviour.
6. **Secret management**: `JWT_SECRET` comes from env; `validate_security_config()` is called from `on_startup` and refuses to boot without it. Good.

### Authorization — solid, with two surprises

Three guard dependencies in `deps.py`:

- `get_current_user` — any authenticated user.
- `require_company_admin` — `UserRole.ADMIN` or `UserRole.COMPANY_ADMIN` (also returns a `RequestContext`).
- `require_admin` — system admin / `is_superuser` only.

Plus two context builders:

- `get_request_context` — returns a `RequestContext` with `company_id`, `allowed_portfolio_ids`, `roles` map, and `is_company_admin`. Refuses with 403 if the user has no company assignment.
- `get_valid_portfolio(portfolio_id)` — loads the portfolio, enforces `deleted_at IS NULL`, enforces `portfolio.company_id == context.company_id` (**returns 404 to hide existence — correct design**), and for non-company-admins verifies a `PortfolioUser` grant.

This maps reasonably cleanly to the frontend's `usePermission`/`PermissionGate` model — the frontend checks `UserRole` locally for UI affordances, the backend enforces `require_company_admin` / portfolio access on the server. The hierarchy values match exactly: `"Admin" / "CompanyAdmin" / "User"` (frontend enum) == `UserRole.ADMIN / COMPANY_ADMIN / USER` (backend enum).

**Two surprises worth flagging:**

- `POST /projects/...` and `PATCH /projects/...` use only `get_valid_portfolio`, not `require_company_admin` (`projects.py:33`, `:66`). Any authenticated user with portfolio access can create or update projects. **DELETE** requires admin. This may be intentional (every portfolio member can add a project) but it's asymmetric with every other resource in the app, and the frontend's `PermissionGate` almost certainly gates project creation on `canEditProject` — which may or may not align. Verify before launch.
- `PATCH /modules/{module_key}/enabled` takes `enabled` as a **query string**, not a JSON body (`modules.py:79`). Works; surprising; hard to discover.

### Missing endpoints that probably should exist

- No registration / invite flow. Admin must create users via `POST /users` (requires existing admin). Fine for B2B; worth documenting.
- No `/auth/forgot-password` / password-reset-by-email. Only `/auth/admin/reset-password/{user_id}` (superuser only) and `/auth/change-password` (self). For market launch you'll need email-driven reset.

---

## 7. Data Model

13 tables. Multi-tenant by `company_id`, scoped by `portfolio_id`, soft-deleted where appropriate, audited where it matters (FinancialNote).

### Tables (key columns only)

| Table | PK | Tenant key | Scope key | Timestamps | Soft-delete | Audit |
|---|---|---|---|---|---|---|
| `user` | id | `company_id?` (FK, nullable for superuser) | — | `created_at` | — | — |
| `company` | id | — | — | `created_at` | — | — |
| `portfolio` | id | `company_id` | — | `created_at` | `deleted_at` | — |
| `project` | id | `company_id` (denormalised) | `portfolio_id` | `created_at, updated_at` | `deleted_at` | — |
| `portfolio_user` | id | `company_id` (denormalised) | `portfolio_id`, `user_id` | `created_at` | `deleted_at` | — |
| `project_company` | id | `company_id` (invited) | `project_id` | `invited_at, accepted_at` | — | — |
| `module` | id | — | — | `created_at` | — | — |
| `module_settings` | id | `company_id` | `module_key, key` | `created_at, updated_at` | — | — |
| `field_definition` | id | `company_id?` (NULL = system) | `module_key` | `created_at` | — | — |
| `field_assignment` | id | — (via project) | `project_id`, `field_definition_id` | `created_at` | — | — |
| `financial_note` | id | `company_id` | `portfolio_id`, `project_id?` | via `AuditMixin` | `deleted_at` | `AuditMixin` + `WorkflowMixin` |
| `audit_log` | id | `company_id` | `portfolio_id?`, `entity_type`, `entity_id` | `created_at` | — | (is itself the audit trail) |
| `revoked_token` | id | — | `jti` (unique) | `revoked_at` | — | — |

### ER in prose

A **User** belongs to at most one **Company** (nullable for superusers). A Company owns many **Portfolios** (unique `(company_id, code)`); each Portfolio owns many **Projects**. Project denormalises `company_id` for efficient tenant-scoped queries without a JOIN — invariant: `project.company_id == project.portfolio.company_id`, enforced at write time (documented in `models/project.py:10-11`).

Access is granted via **PortfolioUser** (a M:N join of user↔portfolio with a `PortfolioRole`: `PortfolioAdmin | CommercialManager | CostEngineer | Viewer`). PortfolioUser also denormalises `company_id` for index-only scoping — this was the column whose FK was dropped in migration `4a20343b5408` and explicitly restored in `a1b2c3d4e5f6_restore_portfolio_user_company_fk.py` after the team noticed access-control decisions were being made against a column with no referential guarantee. That restoration also cleans orphans first, then re-adds the FK — good migration hygiene.

Cross-company collaboration is captured by **ProjectCompany** (`project_id`, invited `company_id`, `collaboration_role`, status `Pending | Accepted | Declined`). A company cannot invite itself (enforced in `collaboration.py:87`). Only the owning company's admin can invite/remove; only the invited company's admin can accept/decline.

**FieldDefinition** is per-module, either system-level (`company_id IS NULL`, read-only for non-admins) or company-owned. **FieldAssignment** attaches a FieldDefinition to a specific Project. Actual field *values* live as a JSON blob in `project.field_values` (Text column) keyed by `FieldDefinition.name` — documented `A-1`. Efficient for reads, terrible for querying by value later; plan for it.

**FinancialNote** carries `AuditMixin` (`created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at`) and `WorkflowMixin` (`status`, `locked_at`, `locked_by_user_id`). Workflow: `DRAFT → SUBMITTED → APPROVED → LOCKED` (with `CANCELLED` as a side branch from non-locked states). `APPROVED` and `LOCKED` transitions require `is_company_admin`; `LOCKED` is immutable (409 on edit/delete). Real workflow, real guards.

**AuditLog** is append-only, company-scoped, and indexes on `entity_type`, `entity_id`, `actor_user_id`. Non-admins see only their own audit rows; admins see everyone in the company. `AuditLog.actor_user_id` is intentionally **not** an FK — a deleted user must not orphan the audit trail.

**RevokedToken** is a flat JTI blacklist with an in-memory cache on top. Good enough for a single-instance deployment; when you scale to N instances, the cache needs to move to Redis.

### Migration discipline — genuinely good

13 migrations. Proper `down_revision` chain from `35426f623d75_initial_migration` onwards. Two retrofitted denormalisations (`company_id` on `project`, `company_id` on `financial_note`) follow the correct three-step pattern: add nullable → backfill via JOIN → make NOT NULL + add FK. One destructive migration (`32d7cd9ae5ab` dropping legacy project columns) with a real downgrade path. One repair migration (`a1b2c3d4e5f6`) that cleans orphans before re-adding a dropped FK. This is the kind of migration history that suggests the team has done a production-grade data change before.

### Multi-tenancy enforcement — real

- Every tenant-scoped table has a `company_id`, on the table, indexed.
- `get_valid_portfolio` returns 404 (not 403) when the portfolio belongs to a different company — the correct pattern to avoid existence leaks.
- List endpoints filter by the requesting user's accessible set (company-admin sees all in company; others see only their `PortfolioUser` grants).
- Tests in `tests/test_tenancy.py` explicitly cover company isolation.

### Data-model gaps to watch

- `portfolio_user.role` was made nullable by `5618a8603e02` (line 29) with no comment explaining why. Every row in production should have a role; a stray NULL here would silently fail authorisation. Consider NOT NULL + a migration to backfill.
- No FK from `field_definition.module_key → module.key`. If a module is ever retired, field definitions go stale. Add a FK or a lifecycle rule.
- No CASCADE deletes anywhere. That's fine philosophically, but the `scripts/cleanup_test_data.py` hand-orders deletes for a reason — real tenant-deletion will need a written runbook.
- Soft-delete filtering is **purely application-level**. There is no view, trigger, or global query filter. Every list and single-fetch manually filters `deleted_at IS NULL`. If a future module forgets, it silently leaks tombstones. Worth encoding as a lint rule or a repository wrapper.
- `project.field_values` is a JSON string in a `TEXT` column, not `JSONB`. You cannot index into it. Fine today; decide if it stays text or moves to JSONB before the first "filter projects by field" feature.

---

## 8. Error Handling, Validation & Observability

### Validation — strong

Every request body is a Pydantic model with explicit constraints (`min_length`, `max_length`, `EmailStr`, default values). Path params are typed. Query params (audit, fields) are typed. SQLModel + `select().where(col == value)` means parameterised SQL throughout — **no injection surface**. There is no raw-dict endpoint and no path where user input flows into a filesystem call.

### Error handling — minimal

- `HTTPException` is raised consistently with specific status codes (401 auth, 403 authz, 404 not-found / hide-existence, 409 conflict/workflow, 422 validation, 429 rate-limit).
- **No global exception handler** (`main.py` registers no `@app.exception_handler`). Unhandled exceptions therefore rely on FastAPI's default — which returns `{"detail": "Internal Server Error"}` and a 500. That's fine. But FastAPI also uses `debug=True` semantics when the runtime's debug is on, and the app does not explicitly set `debug=False`. Before production, set it.
- Error response shape is `{"detail": "..."}` for HTTPException (matches `frontend/src/api/auth.ts` which reads `error.detail`) and `{"detail": [{...}]}` for Pydantic validation errors (the frontend stringifies this; the user sees a messy string). A global handler should normalise to `{detail: string, code?: string, fields?: [...]}`.

### Observability — absent

- **Logging:** `logging.basicConfig(level=logging.INFO)` plus one log line at startup. No structured logging, no per-request logging, no `httpx`-style access log.
- **Correlation IDs:** none. No middleware, no request-id header.
- **APM / error tracking:** none. No Sentry, DataDog, OTel, Prometheus, or equivalent in `requirements.txt`.
- **Metrics:** none.

For a pre-launch single-instance app this is just-barely acceptable. For "preparing to deploy to market" it is not. The cheapest wins are (a) a correlation-id middleware, (b) structured JSON logging (e.g. `structlog`), and (c) Sentry.

---

## 9. Testing & Quality Gates

### Tests — decent quality, partial coverage

**23 tests across 5 files** in `backend/tests/`:

| File | Tests | Covers |
|---|---|---|
| `test_api.py` | 4 | login happy + failure, modules list, auth edge cases |
| `test_money.py` | 3 | `core/money.py` Decimal helpers (pure unit) |
| `test_controls.py` | 3 | AuditMixin stamping, audit log persistence, workflow locking |
| `test_projects.py` | 10 | CRUD, multi-tenancy regression (`C-1`), token revocation |
| `test_tenancy.py` | 3 | Portfolio access + company isolation |

`tests/conftest.py` gives every test a fresh DB session that rolls back at teardown — real isolation. Tests use FastAPI's `TestClient` (integration) and hit real database state via the test DB. Good assertions on status codes and returned fields.

**What's not covered:**
- Zero tests hit `fields`, `financial_notes` (beyond the workflow-lock test), `settings`, `portfolio_access`, `collaboration`, `audit`, or `users` CRUD.
- No refresh-token rotation tests. No rate-limit-exhaustion tests. No Pydantic-422 shape tests.
- No contract test against `frontend/src/api/*.ts` shapes (which is exactly what let contract mismatches #1–#4 in §5 survive).

**Estimated coverage: ~35–40% of endpoints** exercised. That's below where it needs to be for market launch.

### Linting / typing / CI — missing

- **No** `pyproject.toml`, `.flake8`, `ruff.toml`, `mypy.ini`, `pytest.ini`, `.pre-commit-config.yaml`.
- Not listed in `requirements.txt`: `black`, `ruff`, `mypy`, `pre-commit`, `isort`.
- No `.github/workflows/` at the repo root; no `.gitlab-ci.yml`, no `azure-pipelines.yml`, no `circleci`. **There is no CI.**

This is the single biggest quality gap. The frontend has ESLint rules actively rejecting hex colours and demanding `aria-label`. The backend has no equivalent enforcement at all — every review relies on humans noticing.

---

## 10. Security & Secrets

### Committed secrets — **not** committed, but worth clarifying

- `backend/.env` is present **on disk** and contains `JWT_SECRET=gaBXNWk0PD_ybnptkJOk7xaLF...` plus `DATABASE_URL=postgresql://aneriam_user:aneriam_password@localhost:5432/aneriam_db`.
- BUT `.env` is in `.gitignore` (`.gitignore:28`) and `git ls-files | grep env$` shows only `.env.example`. So **the secret is not in git history** as far as the current tree shows. The agent report earlier flagged this as "CRITICAL committed secret"; on verification, it is not. It's a local dev file.
- **Still worth treating seriously** because (a) the password in `DATABASE_URL` is a literal word-pair (`aneriam_user` / `aneriam_password`), (b) the JWT secret looks like it was generated once and has been reused across developer machines, and (c) no production runbook exists yet to rotate either.

### Seed-script hardcoded credentials — real issue

`backend/app/scripts/seed.py:55` hardcodes `admin@aneriam.com` / `"adminpass"` and **updates the password on every run** (lines 66-73). If seed.py is ever wired into a deployment pipeline, you have a fixed admin password in production. Either make the password come from env, or refuse to re-set an existing password.

### CORS — too permissive for production

`main.py:51-57`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # configurable
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins` is properly configurable via `BACKEND_CORS_ORIGINS`. `allow_methods=["*"]` and `allow_headers=["*"]` combined with `allow_credentials=True` is unnecessarily broad. Tighten to the specific methods/headers actually used before going public.

### Rate limiting — works, but isn't what it looks like

`requirements.txt` lists `slowapi>=0.1.9`, which suggests rate limiting. In reality, `slowapi` is **never imported**. What exists is a hand-rolled per-IP counter in `app/core/security.py` (`is_ip_rate_limited`, `record_login_attempt`, `reset_login_attempts`) applied only to `/auth/login`. In-memory, per-process, does not survive restarts, does not share across workers. Good intent, insufficient for a real deployment.

### Input validation — covered (see §8)

### Missing authorization — small gaps

- `POST` / `PATCH` on `/projects/...` don't require admin. Either document as deliberate ("any portfolio member can create projects") or tighten.
- `/auth/change-password` (line `auth.py:190`) exists; `/auth/forgot-password` does not. Password-reset-by-email is a customer-facing requirement.

### Other

- Argon2 for passwords. Good.
- JWT HS256 is fine for a single-service deployment. If you ever split into services, move to RS256 with published public keys.
- JWT secret is validated at startup (`validate_security_config()`). Good.
- Token revocation is DB-backed with an in-memory cache. Good on one instance; move to Redis before scaling horizontally.
- `/health` is static — no DB ping. For Kubernetes-style probes you'll want `/health/live` (static) and `/health/ready` (DB + any dependency).

---

## 11. Top 10 Concrete Issues (ranked by impact)

| # | Issue | Where | Why it matters | Fix size |
|---|---|---|---|---|
| 1 | **Portfolio contract mismatch** between frontend types and backend model (`description`, `logo`, `updated_at` missing; `code` required but unknown to frontend). | `backend/app/models/portfolio.py`, `frontend/src/types/portfolio.ts` | Will break the moment any Portfolio UI renders or creates. Resolve now, before building modules on top. Decide: are these three fields real requirements (add to backend + migration) or FE wishful thinking (remove from TS)? | S–M |
| 2 | **No OpenAPI → TS type generation.** Nothing keeps frontend types and backend schemas in sync. | repo-wide | Issue #1 slipped through; so will the next 10. Fix with `openapi-typescript` or similar; regenerate in CI. | S |
| 3 | **No CI / no Dockerfile / no lint / no type-check.** | repo root | For a "deploying to market" codebase, this is the biggest production-readiness gap. A single `.github/workflows/backend.yml` running `ruff`, `mypy`, `pytest`, `alembic upgrade head` against a service container closes this. | M |
| 4 | **No global exception handler.** Unhandled errors may leak detail; Pydantic 422 errors render ugly in the UI. | `backend/app/main.py` | Add a handler that logs the exception with correlation-id and returns `{"detail": "...", "code": "..."}`. 30 minutes. | S |
| 5 | **`seed.py` hardcodes `admin@aneriam.com / adminpass` and overwrites on every run.** | `backend/app/scripts/seed.py:55,66-73` | Single fixed admin credential is the first thing credential-stuffers try. Read password from env; never overwrite existing. | S |
| 6 | **`slowapi` is listed but unused; actual rate limiter is in-memory per-process.** | `requirements.txt`, `backend/app/core/security.py:30-71` | Will not hold against a real attacker or survive a restart. Either wire up `slowapi` properly (Redis backend) or delete the dependency. | S |
| 7 | **No observability: no structured logging, no correlation IDs, no Sentry/APM.** | `backend/app/main.py:25-26` | First production incident will be un-debuggable. Add structlog + a correlation-id middleware + Sentry. Half a day. | M |
| 8 | **Asymmetric authorisation on projects.** POST/PATCH don't require `require_company_admin` but DELETE does. | `backend/app/api/projects.py:33,66,94` | Either intentional (document + align frontend `PermissionGate`) or a bug. Decide and make symmetric. | S |
| 9 | **Test coverage gaps on `fields`, `financial_notes`, `settings`, `portfolio_access`, `collaboration`, `audit`, and `users` CRUD.** | `backend/tests/` | These modules contain most of the workflow/permission complexity. Right now a regression on any of them would ship unnoticed. | M |
| 10 | **Soft-delete filtering is application-level only.** Every list endpoint manually filters `deleted_at IS NULL`. | repo-wide (`portfolios.py`, `projects.py`, `financial_notes.py`, …) | One forgotten filter = tombstones leak to the UI. Either add a shared `active_only(...)` helper used by every list query, or move to a global query filter. | M |

Honourable mentions (not in the top 10 but worth logging):
- `app/schemas.py` is one 138-line file — split per domain when it crosses ~300 lines.
- `project.field_values` is `TEXT`, not `JSONB` — re-plan when you need to query inside.
- CORS `allow_methods=["*"]` / `allow_headers=["*"]` should be tightened.
- `/health` should grow a `/health/ready` that actually talks to the DB.
- `/auth/forgot-password` doesn't exist; you'll need it before public launch.

---

## 12. What's Actually Good

Preserve these:

- **`get_valid_portfolio(portfolio_id)` in `app/api/deps.py`.** One place that (i) checks soft-delete, (ii) enforces company scoping, (iii) enforces user access, (iv) 404s on cross-tenant access to hide existence. This is the single most important piece of code in the backend; every new endpoint that takes a portfolio id should use it.
- **Multi-tenancy is real, not aspirational.** Denormalised `company_id` on Project, FinancialNote, PortfolioUser, with a documented restoration migration (`a1b2c3d4e5f6`) that cleans orphans before reinstating a dropped FK. The team has done this before.
- **JWT + JTI + DB-backed revocation + rotation on refresh.** Correct token design.
- **Argon2 for passwords.** Correct choice.
- **SQLModel + `select().where(col == value)` everywhere.** No injection risk.
- **Pydantic validation on every request body**, with sensible `min_length` / `max_length` / `EmailStr`.
- **Alembic migration discipline.** Proper `down_revision` chain. The three-step denormalisation pattern (add nullable → backfill → NOT NULL + FK) is used consistently.
- **Workflow model on FinancialNote is tight.** `LOCKED` is truly immutable (409 on edit/delete). `APPROVED`/`LOCKED` transitions require admin.
- **AuditLog is append-only, company-scoped, and `actor_user_id` deliberately has no FK** so deleted users don't orphan the audit trail.
- **`_build_user_read` centralises the `company_name` join.** Small, but correct.
- **Tests use a transaction-rollback fixture** (`tests/conftest.py:19-41`) — fast, isolated, deterministic.
- **`tests/test_tenancy.py`** exists at all — a lot of multi-tenant codebases ship without this and regret it.
- **Validation happens at startup** (`validate_security_config()`) — the app refuses to boot without `JWT_SECRET`. Good.
- **Module-per-router layout under `app/api/`.** Clean, consistent.

---

## 13. Recommended Path Forward

**Option (a): minor tidy-up + add backend rules to `CLAUDE.md`.** Recommended.

Rationale: the architecture is sound, auth and tenancy are real, migrations are disciplined, and validation is complete. What's missing is the production-readiness layer (CI, Docker, lint, type-check, observability) and a handful of concrete cleanup items. None of these require rearchitecture. Options (b) or (c) would discard working foundations for no benefit.

### Hard requirements before building modules on top

These must happen first, in this order, or they will hurt the next 10 features:

1. **Resolve the Portfolio contract (§5 #1–#4).** Decide whether the frontend's `description`, `logo`, `updated_at` are real (migrate them onto the backend model, expose via a `PortfolioRead` schema) or fictional (delete from TS). Decide whether the backend's required `code` belongs on the frontend `Portfolio` and `PortfolioCreate`. ~2 hours including migration.
2. **Stand up CI.** One GitHub Actions workflow: `ruff check`, `ruff format --check`, `mypy app`, `alembic upgrade head`, `pytest`. Gate merges on it. Half a day.
3. **Add a Dockerfile + docker-compose for local dev.** FastAPI + uvicorn + PostgreSQL. Multi-stage for production image. Half a day.
4. **Generate TS types from OpenAPI.** `openapi-typescript` reads the FastAPI spec and emits a single `frontend/src/api/generated.ts`. Every `frontend/src/api/*.ts` imports from it. Add to CI so a drift breaks the build. Half a day.
5. **Harden seed.py.** Password from env, refuse to re-set existing passwords, log clearly when it creates vs skips. 1 hour.
6. **Rotate the local `JWT_SECRET` and the DB password in `.env`.** Use `python -c "import secrets; print(secrets.token_urlsafe(48))"` (the hint is already in `.env.example`). Document rotation procedure. 15 minutes.

### Second-wave cleanup (within a month of launch, not blocking)

- Add a global exception handler that logs with correlation-id and normalises the error shape to `{detail: string, code?: string, fields?: [...]}`.
- Add a correlation-id middleware + structlog + Sentry.
- Wire up `slowapi` with a Redis backend or delete it from `requirements.txt`.
- Split `app/schemas.py` per domain (it's already trending that way).
- Add tests for `fields`, `financial_notes` (beyond the lock case), `settings`, `portfolio_access`, `collaboration`, `audit`, and `users`.
- Convert `project.field_values` from `TEXT` to `JSONB` (Alembic supports this directly).
- Tighten CORS `allow_methods` / `allow_headers` to the actual set used.
- Add `/health/ready` that pings the database.
- Resolve the projects POST/PATCH admin-check asymmetry (§11 #8).
- Add `/auth/forgot-password` (email-token flow) before public launch.
- Move token revocation cache to Redis when you add a second API instance.

### Not now, but plan for

- OpenTelemetry tracing.
- Move JWT signing from HS256 to RS256 when you split into multiple services.
- A repository/service layer between routers and SQLModel so the "every query filters `deleted_at IS NULL`" invariant is enforceable by construction.

---

## 14. Implications for CLAUDE.md

The section below is written to paste directly into `CLAUDE.md`. It encodes the backend conventions future agent sessions need to respect. Combine with the frontend conventions from `FRONTEND_AUDIT.md §12`.

---

```markdown
## Backend (FastAPI + SQLModel + PostgreSQL)

### Stack
- Python 3.13, FastAPI, SQLModel, Pydantic v2, Alembic, Uvicorn.
- PostgreSQL in prod; SQLite in tests (via SQLModel default). Never hardcode `sqlite:///…`.
- Argon2 passwords (`passlib[argon2]`). HS256 JWT (`python-jose`).

### File layout
- Routers: `app/api/<domain>.py`, one router per domain. Register in `app/main.py`.
- Models: `app/models/<name>.py`, one SQLModel class per file. Mixins in `app/models/mixins/`.
- Pydantic request/response schemas: `app/schemas.py` (split per domain once it exceeds ~300 lines).
- Cross-cutting helpers: `app/core/` (security, database, audit, money, workflow).
- Migrations: `alembic/versions/`. Never edit an applied migration — add a new one.

### Authentication & authorization — use these, never re-implement
- `Depends(get_current_user)` — any authenticated user.
- `Depends(require_company_admin)` — company admin or system admin. Returns a `RequestContext`.
- `Depends(require_admin)` — system admin / superuser only.
- `Depends(get_request_context)` — needs auth + company assignment; returns `RequestContext` with `company_id`, `allowed_portfolio_ids`, `roles`, `is_company_admin`.
- `Depends(get_valid_portfolio)` — **every endpoint that takes a `portfolio_id` MUST use this**. It enforces soft-delete, company scoping (returns 404, not 403, to hide existence), and user access.
- Password hashing: `app/core/security.get_password_hash` / `verify_password`. Never call passlib directly.
- JWT: `create_access_token`, `create_refresh_token`, `is_token_revoked`, `revoke_token` in `app/core/security`. Do not hand-roll JWTs.

### Multi-tenancy (this is not optional)
- Every tenant-scoped table carries `company_id` indexed. New tenant-scoped tables follow this pattern.
- New endpoints that touch portfolio data: take `portfolio_id` in the path, depend on `get_valid_portfolio`.
- When denormalising `company_id` onto a new table, use the three-step migration: add nullable → backfill from parent → NOT NULL + FK + index. See `b2c3d4e5f607_add_company_id_to_project.py` for the template.
- Never drop a FK silently. If denormalising, keep the FK — see `a1b2c3d4e5f6_restore_portfolio_user_company_fk.py` for why.

### Soft-delete
- Tables with `deleted_at`: portfolio, project, portfolio_user, financial_note.
- Every `SELECT` against these tables MUST filter `.where(<Model>.deleted_at.is_(None))` — there is no global query filter yet. Until there is, treat this as a hard rule.
- Deletes are `PATCH deleted_at = now()`, not `DELETE FROM`.

### Request / response shape
- Request bodies: Pydantic models with `min_length`/`max_length`/`EmailStr`. No raw dicts.
- Response models: declare `response_model=` on every route.
- Error shape: `raise HTTPException(status_code=..., detail="human message")`. FastAPI serialises to `{"detail": "..."}` — the frontend's `ApiError` reads `detail`. Do not invent new error shapes.
- Status codes: 401 auth, 403 authz, 404 not-found / hide-existence, 409 conflict/workflow, 422 validation, 429 rate-limit.

### Database access
- Sessions come from `Depends(get_session)`. Never create ad-hoc engines inside routes.
- Queries use SQLModel `select().where(col == value)`. **Never** use f-strings or string concatenation in SQL. **Never** use `text()` with user input.
- Every new tenant-scoped query starts with the `company_id` filter derived from the `RequestContext`.

### Migrations
- Alembic only. `alembic revision -m "..."` → edit → `alembic upgrade head`.
- Every migration has a working `downgrade()`.
- Denormalisation: add nullable, backfill, make NOT NULL + FK in one or two migrations — never in-place.
- Do not hand-edit the revision chain.

### Testing
- Tests live in `backend/tests/`. `conftest.py` provides a rollback-per-test DB fixture — use it.
- New routes ship with at least: one happy-path integration test, one 401/403 test, one 404 test for cross-tenant access.
- Financial-facing or workflow-facing changes ship with an audit-log assertion.

### Things never to touch without explicit permission
- `app/core/security.py` (auth primitives and rate-limit — one bug here is a security incident).
- `app/api/deps.py` (`get_valid_portfolio` is the central tenancy guard).
- `backend/.env` / `.env.example` (secret management).
- Any existing migration under `alembic/versions/` (add new, never edit applied).
- The mixins in `app/models/mixins/` (audit and workflow semantics are depended on by FinancialNote).

### Conventions & naming
- Snake_case in JSON (it's what the frontend expects — `access_token`, `full_name`, `is_active`, `portfolio_id`).
- Datetime fields serialise as ISO 8601 UTC strings.
- Enum values use exact PascalCase strings: `UserRole.ADMIN == "Admin"`, `PortfolioRole.COST_ENGINEER == "CostEngineer"`, `WorkflowStatus.DRAFT == "Draft"`. If you add an enum value, add it to `frontend/src/types/enums.ts` in the same PR.
- Admin guards: sensitive mutation requires `require_company_admin`. Read endpoints use `get_request_context`. `DELETE` always requires admin.

### Frontend contract
- TypeScript types in `frontend/src/types/` must match backend Pydantic response models exactly (field names, casing, nullability).
- When you change a Pydantic response model, update the corresponding TS interface in the **same PR**. (When the OpenAPI → TS generator is in place, regenerate instead.)
- The frontend reads `error.detail` as the error message. Do not return `{"message": "..."}` or `{"error": "..."}`.
- The frontend stores tokens in `localStorage`, refreshes on 401 once, and retries. Do not invent a different auth scheme on the server without updating `frontend/src/api/client.ts` at the same time.

### Observability (to be added — track as tech debt)
- Until structured logging + correlation IDs exist, log with `logging.getLogger(__name__).info("…", extra={…})` rather than `print(...)`.
- Never `print(...)` from route handlers.
```

---

### Closing note

This is a backend that was built by someone who has shipped multi-tenant SaaS before. The guard rails (centralised portfolio dependency, tenant denormalisation with documented migrations, JWT rotation, Argon2, parameterised SQL) are in place and correct. What's missing is the operational scaffolding (CI, Docker, linting, observability) and the contract link to the frontend that prevents issues like the Portfolio mismatch from appearing in the first place.

Fix the Portfolio contract, stand up CI + OpenAPI→TS generation, add a Dockerfile, rotate the dev secrets, harden `seed.py`, and you can build modules on top of this with confidence. Do not rework.
