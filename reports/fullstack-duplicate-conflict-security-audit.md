# Full-Stack Duplicate / Conflict / Security Audit

## 1. Repo Map and Entry Points

### Repository Structure (Key Items)
- **Frontend** (`/frontend`)
  - **Entry**: `src/main.tsx` → `src/App.tsx` → `src/routes.tsx`
  - **Core**: `src/api/`, `src/context/`, `src/layouts/`
  - **Pages**: `src/pages/` (Login, Landing, SelectPortfolio)
- **Backend** (`/backend`)
  - **Entry**: `app/main.py`
  - **Auth/Security**: `app/core/security.py`, `app/api/auth.py`, `app/api/deps.py`
  - **Models**: `app/models/` (SQLModel definitions)

### Entry Points & Lifecycle
- **Frontend Boot**: `main.tsx` initializes `AuthProvider`, `Theme`, and `Router`.
- **Backend Boot**: `uvicorn` runs `app.main:app`. `on_startup` validates security config and initializes DB.

## 2. Sources of Truth (Current)

| Concern | Source of Truth | Notes |
|---|---|---|
| **Authentication** | FE: `AuthContext.tsx` / BE: `api/auth.py` + `deps.py` | Token stored in `localStorage`. |
| **API Client** | FE: `src/api/client.ts` | Central `authenticatedFetch` wrapper handles token injection and 401s. |
| **Tenancy (Portfolios)** | FE: `PortfolioContext.tsx` / BE: `deps.py` (`get_valid_portfolio`) | Frontend caches active portfolio; Backend validates access per request. |
| **Layouts** | FE: `layouts/ToolpadShell.tsx` (Protected) / `PublicLayout.tsx` (Public) | Clear separation of concerns. |
| **Database Schema** | BE: `app/models/` | SQLModel classes define both DB schema and basic Pydantic validation. |

## 3. Duplicate and Conflicting Implementations

| Area | Duplicate/Conflict | Paths | Which is Used | Risk | Recommendation |
|---|---|---|---|---|---|
| **API Calls** | Minimal | Service files (`api/*.ts`) use `client.ts`. Contexts use service files. | `client.ts` -> Service -> Context | Low | Keep as is. Structure is clean. |
| **State Management** | Context vs SessionStorage | `PortfolioContext` syncs with `sessionStorage`. `AuthContext` syncs with `localStorage`. | Both (synced) | Low | Standard pattern for persistence. |
| **Layouts** | `ToolpadShell` vs `PublicLayout` | `PublicLayout.tsx` used in Login/SelectPortfolio. `ToolpadShell` used in Protected routes. | Correctly separated | None | Good separation. |

**Observation**: The codebase is surprisingly clean of duplication. Iterate development seems to have refactored legacy patterns effectively.

## 4. Dead Code and Fragmentation Candidates

### 4.1 Frontend
- **Unused Components**: None found in `pages/` or `layouts/` (all referenced in `routes.tsx` or used by pages).
- **Potential unused hooks**: `useDataFetch` is defined but needs to be verified if widely used (referenced in grep).
- **Config**: `charts.config.ts` exists but no charts are currently visible in the mapped pages (likely reserved for Milestone G).

### 4.2 Backend
- **Reserved Model**: `app/models/financial_note.py`.
  - **Status**: Reserved for future implementation. Currently unused but structure is defined.
- **Unused Modules**: `app/models/mixins` (Audit, Workflow) are good abstractions, but verify consumption.

## 5. Security Findings

### 5.1 Code-Level Risks
- **Secrets Management**: Good. `security.py` uses `os.getenv("JWT_SECRET")` with a check_validity function.
- **Auth Flow**: standard JWT Bearer flow. `deps.py` correctly validates token signature and expiration.
- **CORS**: `main.py` allows configuration via `BACKEND_CORS_ORIGINS`. Default is localhost, which is safe for dev.
- **Tenancy Enforcement**: `deps.py` -> `get_request_context` and `get_valid_portfolio` enforce portfolio access scoping and company isolation. This is a robust pattern.

### 5.2 Config & Secret Hygiene
- `frontend/src/config/core.ts` uses `import.meta.env` (Safe).
- `docker-compose.yml` (not analyzed deep content, but presence suggests containerization).
- **No hardcoded secrets** found in source files (grep for "password", "secret", "key" returned only variable names/tests).

### 5.3 Dependency Hygiene (Best Effort)
- **Frontend**: `@mui/x-data-grid-pro` requires a license key. Ensure it is not committed to repo (checked `config/license.ts` - usually env var).
- **Backend**: `passlib[argon2]` is strong. `python-jose` is standard. warning: `python-jose` is in maintenance mode, consider `pyjwt` for future proofing, but not a vulnerability yet.

## 6. Frontend↔Backend Contract Consistency

> [!WARNING]
> **Major Finding**: strict Enum Contracts are missing in Frontend.

- **Backend**: `UserRole` (Enum) = `Admin`, `CompanyAdmin`, `User`.
- **Frontend**: `User` interface (`types/auth.ts`) defines `role: string`.
- **Risk**: Frontend logic comparing `user.role === 'company_admin'` (snake_case) vs Backend `'CompanyAdmin'` (PascalCase) will fail silently or cause permission bugs.
- **Missing Enums**: `UserRole`, `PortfolioRole`, `WorkflowStatus` are defined in Backend `enums.py` but have no corresponding value-enum in Frontend `types/`.

## 7. Prioritized Remediation Plan (Do Not Execute)

### P0 (Security / Critical)
- None identified.

### P1 (High - Contract & Reliability)
- **Fix UserRole Enum mismatch**:
  - Export `UserRole` values to Frontend.
  - Update `types/auth.ts` to use a string union type or Enum matching Backend exactly.
  - Verify all role checks in Frontend (e.g. `PermissionGate.tsx`) match Backend values.

### P2 (Medium - Cleanup)
- **Standardize Types**: Generate TypeScript types from Pydantic models (using tools or manual sync) to prevent drift.

### P3 (Low - Refactoring)
- **Documentation**: ensuring `API_CONFIG` usage is documented for new developers.

## 8. Verdict

- **Status**: **PASS** (with cleanup recommendations)
- **Blockers**: None.

The architectural integrity is high. The separation of concerns between `Auth`, `Tenancy`, and `Data` layers is consistent. The main risk is the loose typing of Enums between Frontend and Backend.
