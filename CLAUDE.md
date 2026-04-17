# CLAUDE.md — Aneriam

This file is read at the start of every AI agent session. It defines the rules, conventions, and decisions for working in this codebase. Read it first. If a request conflicts with anything here, stop and ask before proceeding.

## What this project is

Aneriam is a multi-tenant portfolio and project management platform. Companies manage portfolios of projects, grant portfolio-level access to users, collaborate across company boundaries on shared projects, and attach structured financial and field-level data to projects. The platform is designed to host feature **modules** that plug into a common shell.

**Product stage:** foundation complete; building feature modules. Not yet launched to users.

## Architecture at a glance

- **Frontend:** React 19 + TypeScript (strict) + MUI v7 + Vite, served as an SPA. Lives in `/frontend`.
- **Backend:** FastAPI + SQLModel + PostgreSQL, Alembic migrations, JWT auth with refresh rotation. Lives in `/backend`.
- **Data contract:** the source of truth for types is the backend's Pydantic schemas, surfaced via FastAPI's OpenAPI document. Frontend TypeScript types are generated from that document using `openapi-typescript`. Hand-editing generated types is forbidden.
- **Multi-tenancy:** every tenant-scoped table carries `company_id`. Every portfolio-scoped endpoint routes through `get_valid_portfolio` (`backend/app/api/deps.py`) — this is the single chokepoint for tenant isolation.

## The golden rules

These rules override stylistic preferences, convenience, and "I'll just quickly...". If you must break one, stop and surface the tradeoff.

1. **Never break the frontend–backend contract.** If you change a Pydantic response model, regenerate `frontend/src/api/generated.ts` in the same change. If the generated types don't compile on the frontend, the change is incomplete.
2. **Never bypass `get_valid_portfolio`.** Any endpoint that takes a `portfolio_id` depends on it. Writing a custom portfolio lookup is a security regression.
3. **Never edit an applied Alembic migration.** Add a new migration. The `alembic/versions/` chain is append-only.
4. **Never hand-roll JWTs, password hashing, or token revocation.** Use the helpers in `backend/app/core/security.py`.
5. **Never introduce raw hex colors, `rgb()`, or `rgba()` in frontend code outside `src/theme/palette.ts`.** ESLint will fail the build. Use theme tokens (`theme.palette.primary.main`, `alpha(theme.palette.background.paper, 0.8)`).
6. **Never commit secrets.** `.env` is gitignored. `.env.example` is the template. If you find a hardcoded secret in source, treat it as an incident.
7. **Never skip soft-delete filtering.** Tables with `deleted_at` (portfolio, project, portfolio_user, financial_note) must filter `.where(Model.deleted_at.is_(None))` in every `SELECT`.
8. **Never ship UI that silently discards user input.** If a form has a Save button, it must submit to the backend or the button must be disabled with a visible reason.

## Project structure

```
/
├── CLAUDE.md                    # This file — project-wide rules
├── FRONTEND_AUDIT.md            # Reference: last frontend audit
├── BACKEND_AUDIT.md             # Reference: last backend audit
├── frontend/
│   ├── CLAUDE.md                # Frontend-specific rules
│   ├── src/
│   │   ├── api/                 # API client + per-domain modules + generated types
│   │   ├── components/          # App-aware UI (dashboard widgets, dialogs, etc.)
│   │   ├── ui/                  # Headless primitives (feedback, typography)
│   │   ├── layouts/             # Three shells: Toolpad, Settings, Public
│   │   ├── pages/               # Route-level components
│   │   ├── context/             # 5 React contexts: auth, portfolio, projectFilter, actions, notifications
│   │   ├── hooks/               # useDataFetch, useFeatureFlag, usePermission
│   │   ├── theme/               # MUI theme + tokens (palette, typography, components)
│   │   └── types/               # TS types (generated + hand-written domain types)
│   └── docs/frontend/           # Detailed UI standards (page layout, spacing, forms, a11y)
└── backend/
    ├── CLAUDE.md                # Backend-specific rules
    ├── app/
    │   ├── api/                 # Routers (one per domain) + deps.py (auth/tenancy)
    │   ├── core/                # security, database, audit, money, workflow
    │   ├── models/              # SQLModel tables + mixins
    │   ├── schemas.py           # Pydantic request/response schemas
    │   └── scripts/             # seed.py, cleanup
    ├── alembic/versions/        # Migration chain — append only
    └── tests/                   # pytest + rollback fixture
```

## How frontend and backend stay in sync

This is the single biggest risk in a full-stack codebase. Aneriam handles it in three layers:

**Layer 1 — Generated types.** The frontend's `src/api/generated.ts` is produced by running `openapi-typescript` against the backend's `/openapi.json`. Regenerate after any backend schema change. Per-domain API modules (`src/api/auth.ts`, `portfolios.ts`, etc.) import from `generated.ts` — they do not define their own request/response shapes.

**Layer 2 — Enum parity.** String enums appear in two places: `backend/app/models/` (Python enums) and `frontend/src/types/enums.ts` (TS enums). Values must match exactly (e.g., `UserRole.ADMIN == "Admin"`). When you add an enum value in one place, add it in the other in the same change.

**Layer 3 — Error shape.** Backend returns `{"detail": "human message"}` via FastAPI's `HTTPException`. Frontend `ApiError` reads `error.detail`. Do not invent alternate error shapes on either side.

If you find yourself writing a frontend type by hand that overlaps with a backend schema, stop. The type belongs in `generated.ts`.

## Decisions already made — do not relitigate without talking to a human

- **Stack:** React + MUI v7 on frontend; FastAPI + SQLModel + PostgreSQL on backend. Not switching.
- **Auth:** JWT with refresh rotation, JTI-based DB revocation, Argon2 password hashing. Not changing.
- **Multi-tenancy:** denormalized `company_id` on tenant-scoped tables, enforced at the dependency layer via `get_valid_portfolio`. Not changing.
- **Styling:** MUI `sx` prop + theme tokens only. No Tailwind, no CSS modules, no styled-components.
- **Forms plan:** `react-hook-form` + `zod` schemas. No Formik. No raw `useState` for production forms.
- **Data fetching today:** custom `useDataFetch` hook + `DataView` component. Planned migration to `@tanstack/react-query` when first data-heavy module ships — not before.
- **State management:** React Context only (5 providers). No Redux, Zustand, Jotai.
- **Desktop-first:** current `min-width: 1024px`. Mobile responsiveness is planned but not enforced. New components should use MUI breakpoints and avoid hardcoded widths so they're ready when mobile work begins.

## Files agents must never touch without explicit user approval

Modifying any of these without being asked is a violation of trust. If a task seems to require changing one, stop and ask first.

**Backend:**
- `backend/app/core/security.py` — JWT, Argon2, rate-limit. A bug here is a security incident.
- `backend/app/api/deps.py` — `get_valid_portfolio` is the central tenancy guard.
- `backend/app/models/mixins/` — AuditMixin and WorkflowMixin are depended on by FinancialNote.
- Any file under `backend/alembic/versions/` — migrations are append-only.
- `backend/.env` / `.env.example` — secret management.

**Frontend:**
- `frontend/src/theme/palette.ts` — the only file allowed to contain hex colors.
- `frontend/eslint.config.js` — the governance layer.
- `frontend/tsconfig.app.json` — strict typing decisions.
- `frontend/src/api/generated.ts` — regenerated from backend, not edited by hand.

## What "done" looks like for a task

A task is done when:

1. Code compiles (`tsc -b` on frontend, `mypy app` on backend).
2. Linters pass (`eslint .` on frontend, `ruff check` on backend).
3. Tests pass (`pytest` on backend; frontend tests when present).
4. If backend schemas changed, `generated.ts` was regenerated and the frontend still compiles.
5. If enums changed, both sides were updated.
6. If a new feature was added, at least one test covers it.
7. If authentication, tenancy, or migrations were touched, the relevant tests still pass and a human has reviewed.

"It works on my machine" is not done.

## How to start a new session

1. Read this file (you're doing it).
2. Read `frontend/CLAUDE.md` if touching frontend, `backend/CLAUDE.md` if touching backend. Read both if touching either.
3. If the task involves an endpoint or schema that already exists, read it before writing anything.
4. If the task involves a component that already exists, read it before creating a similar one.
5. Before writing a new component or endpoint, ask: does one like this already exist? If yes, extend or reuse; if no, follow the patterns in the existing code.

## When in doubt

Ask the human. An unnecessary clarifying question costs a minute. A confident wrong decision costs a day of rework and a broken contract.
