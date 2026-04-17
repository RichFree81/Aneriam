# Frontend CLAUDE.md — Aneriam

Read `/CLAUDE.md` at the repo root first. This file covers frontend-specific rules.

## Stack (pinned — do not switch)

- React 19.2 + ReactDOM 19.2
- TypeScript ~5.9 (strict, noUnusedLocals, noUnusedParameters, noUncheckedSideEffectImports)
- Vite 7.2 (`@vitejs/plugin-react` 5.1)
- MUI v7.3 (`@mui/material`, `@mui/icons-material`)
- `@mui/x-data-grid-pro` 8.27 — Pro tier, licensed
- `@toolpad/core` 0.16 — provides `AppProvider` + `DashboardLayout`
- `@emotion/react` + `@emotion/styled` (via MUI)
- `react-router-dom` 7.12
- `recharts` 3.7
- `react-hook-form` + `zod` — planned; use when adding forms
- `@tanstack/react-query` — planned; not yet installed

Do not introduce new UI libraries, styling systems, state management libraries, or data-fetching libraries without user approval. The stack is deliberate.

## File structure

```
src/
├── api/                # API client + per-domain modules + generated types
│   ├── client.ts       # authenticatedFetch wrapper
│   ├── generated.ts    # GENERATED — do not edit by hand
│   ├── auth.ts         # Per-domain wrappers — import types from generated.ts
│   ├── portfolios.ts
│   ├── projects.ts
│   └── modules.ts
├── components/         # App-aware UI (knows about domain, contexts, data)
│   ├── charts/         # BaseChartContainer + specific chart wrappers
│   ├── common/         # Cross-cutting (SettingsSection, GlobalAddMenu, TabPanel)
│   ├── dashboard/      # Dashboard widgets (KpiCard, etc.)
│   ├── dialogs/        # Domain dialogs (ProjectCreateDialog, ProjectSelectionDialog)
│   ├── forms/          # Form primitives (FormSection, FormGlobalError)
│   ├── grid/           # StandardDataGrid wrapper
│   ├── layout/         # PageLayout — the in-page primitive
│   ├── DataView.tsx    # 4-state lifecycle switch
│   ├── DataToolbar.tsx
│   ├── ErrorBoundary.tsx
│   └── PermissionGate.tsx
├── ui/                 # Headless primitives (no domain knowledge)
│   ├── feedback/       # LoadingState, ErrorState, EmptyState, ConfirmDialog
│   └── typography/     # Typography wrappers
├── layouts/            # ToolpadShell, SettingsShell, PublicLayout
├── pages/              # Route-level components, one per route
├── context/            # 5 providers — Auth, Portfolio, ProjectFilter, ActionRegistry, Notification
├── hooks/              # useDataFetch, useFeatureFlag, usePermission, useRegisterAction
├── theme/              # index, palette, typography, components, settingsTheme
├── types/              # Hand-written domain types (enums, non-API types)
├── config/             # routes, navigation, feature flags, license
└── utils/              # format.ts (Decimal, date, currency helpers)
```

## `components/` vs `ui/` — the split

This distinction is important. New contributors (human or AI) put things in the wrong bucket.

**`ui/` is for headless primitives.** Components that take props and render UI with zero knowledge of the domain. A `LoadingState` with a spinner. An `EmptyState` with a title and icon. A `ConfirmDialog` that renders yes/no. These never import contexts, never call APIs, never reference business entities like "portfolio" or "project".

**`components/` is for app-aware components.** A `ProjectSelectionDialog` that knows about the portfolio context. A `KpiCard` that formats financial values. A `PermissionGate` that reads the current user's roles. These can import contexts, domain types, and API modules.

When in doubt: if the component name contains a domain noun (Portfolio, Project, User, Financial), it belongs in `components/`. Otherwise, `ui/`.

## Theme tokens — the only source for colors, spacing, shadows

**Color:** Every color in the app comes from `theme.palette`. Defined in `theme/palette.ts` (primary `#1976d2`, secondary `#9c27b0`, text primary `#1a1a1a`, text secondary `#666666`, bg default `#f5f5f5`, bg paper `#ffffff`, divider `rgba(0,0,0,0.12)`). The Settings shell uses a parallel `settingsTheme.ts` palette (slate variants). These two files are the **only** places in the codebase where hex codes are allowed.

**Spacing:** MUI's default 8px base. Use `sx={{ p: 2 }}`, `sx={{ mb: 3 }}`. Never use `sx={{ padding: '16px' }}`. Never invent fractional values (`mb: -1/8` in `PageLayout.tsx:106` is a known wart — do not copy this pattern).

**Typography:** Use MUI variants (`variant="h1"` through `variant="caption"`, `body1`, `body2`). One theme override exists: `h4` is `1.19rem`. Do not add inline `fontSize` or `fontWeight` unless the variant system genuinely cannot express what you need.

**Shadows:** Reference `theme.shadows[n]`. Never write `box-shadow: 0 2px 8px rgba(...)`.

**Border radius:** `theme.shape.borderRadius` is 4. Use `borderRadius: 1` (4px), `borderRadius: 2` (8px). For cards use `rounded` shapes via `sx={{ borderRadius: 1 }}`.

**For transparency:** Use MUI's `alpha()` helper: `alpha(theme.palette.background.paper, 0.8)`. Never write `rgba()` literals.

ESLint enforces most of this. If the linter complains, fix the code — do not disable the rule.

## Shells — when to use which

Three shells, one per user context:

- **`layouts/ToolpadShell`** — wraps all authenticated in-app routes. Sidebar nav, logo, breadcrumb showing `{portfolio} / {project filter}`, global Add menu, project-filter button, settings button. All authenticated app pages use this.
- **`layouts/SettingsShell`** — wraps settings routes. Slate theme, different breadcrumb (`{company} / Settings`). Use for any route under `/settings`.
- **`layouts/PublicLayout`** — centered full-height wrapper. Used by Login and SelectPortfolio only.

The routing in `routes.tsx` uses `PrivateRoute` to gate authenticated routes. Do not bypass it.

## PageLayout — the in-page primitive

Every authenticated page composes `components/layout/PageLayout` inside the shell. It provides:

- Page title + optional subtitle
- Optional breadcrumbs
- Optional tabs
- A content slot for the page body
- Two spacing contexts: `'standard'` (24px — default) and `'utility'` (16px — dense settings pages)

See `docs/frontend/page-layout-standard.md` and `docs/frontend/page-spacing-spec.md` for the full spec. Do not roll a custom page header.

## Data fetching — current and planned

**Today:** `hooks/useDataFetch` — a 4-state lifecycle (idle/loading/success/error) with 300ms loading delay, AbortController cleanup, isEmpty detection. Pair with `components/DataView` which switches between LoadingState / ErrorState / EmptyState / content. Documented in `docs/frontend/` with rules D-01 through D-08.

Pattern:
```tsx
const { state, data, error, refetch } = useDataFetch(() => portfolios.list(), []);
return (
  <DataView state={state} data={data} error={error} onRetry={refetch}>
    {(items) => <PortfolioList items={items} />}
  </DataView>
);
```

**Planned:** `@tanstack/react-query` when the first data-heavy module ships. When that happens, `useDataFetch` gets replaced module-by-module, not in one big bang. Do not introduce react-query ad-hoc — coordinate with the user first.

## API access

All API calls go through `api/client.ts` (`authenticatedFetch`). Never call `fetch()` directly from a component or page. Per-domain API modules (`api/auth.ts`, `api/portfolios.ts`, etc.) wrap `authenticatedFetch` with typed surfaces — new domains get new modules.

Types imported from `api/generated.ts` (produced by `openapi-typescript` from the backend OpenAPI spec). **Never write request/response types by hand that duplicate what's in the backend.** If the type isn't in `generated.ts`, regenerate or update the backend schema.

## Forms — the mandated pattern (when you build them)

No form in production yet uses this pattern. The first one we build sets the precedent for all others.

- Form library: `react-hook-form`.
- Validation schema: `zod`, integrated via `@hookform/resolvers/zod`.
- Field groups: `components/forms/FormSection` (title + children).
- Form-level errors: `components/forms/FormGlobalError` (Alert at top of form on submit failure).
- Field-level errors: MUI TextField's `error` + `helperText` props.
- Submit disabled while in-flight; button label changes to "Saving..." during submit.
- On success: either navigate away, show a Snackbar via `NotificationContext`, or reset the form — decide per feature.
- Spec reference: `docs/frontend/forms-standards.md`.

Do not write forms with raw `useState` for production. The existing Login form predates this rule and will be migrated.

## Permissions

The frontend does **not** enforce security — the backend does. Frontend permission checks are for UI affordance only (hiding buttons the user can't use).

- `hooks/usePermission` reads roles from `AuthContext`.
- `components/PermissionGate` conditionally renders children.
- Role values must match backend enums exactly: `Admin`, `CompanyAdmin`, `User` (from `types/enums.ts`).

If you find yourself hiding a button for security reasons without also ensuring the backend rejects the action, that's a security bug.

## Accessibility — the baseline

- Use semantic HTML (`<main>`, `<nav>`, `<button>`). `PublicLayout` already uses `component="main"`.
- Every `IconButton` needs an `aria-label` — ESLint enforces this.
- Breadcrumbs use `aria-label="breadcrumb"`.
- Heading hierarchy: one `h1` per page (handled by `PageLayout`).
- Do not use `onClick` on non-interactive elements (`<div onClick>`).
- Spec reference: `docs/frontend/accessibility.md`.

## Responsive — current state

The app currently enforces `min-width: 1024px` in `src/index.css`. This is a known tradeoff for the foundation phase. Mobile responsiveness is planned.

When writing new code: use MUI breakpoints (`sx={{ width: { xs: '100%', md: 600 } }}`), avoid hardcoded pixel widths, prefer `Stack` over `Grid` for simple layouts. This prepares the codebase for mobile work without requiring you to test every new component at mobile sizes today.

Do not remove `min-width: 1024px` without coordinating — that's a product decision, not a code cleanup.

## ESLint governance — it enforces real rules

The ESLint config in `frontend/eslint.config.js` is not decorative. It blocks:

- Raw hex literals (`#fff`, `#1976d2`) outside `theme/palette.ts` and `docs/`.
- Raw `rgb()` / `rgba()` literals anywhere.
- Pixel strings in `boxShadow`.
- `IconButton` without `aria-label` or `title`.

When it fails, fix the code — do not add `// eslint-disable-next-line`. If you believe a rule is wrong, raise it with the user; do not silently bypass.

## Testing (aspirational — not enforced yet)

Frontend tests do not currently exist. When they're added:
- Unit tests via Vitest (matches Vite).
- Component tests via React Testing Library.
- A11y via `jest-axe` or Playwright + axe.

Don't retrofit tests onto existing code as a side-quest. When you add a new complex component or hook, add a test alongside.

## Known warts (do not copy-paste these patterns)

- `PageLayout.tsx:106` — `mb: -1/8` fractional margin. Works, ugly, will be removed.
- `components/charts/BaseChartContainer.tsx:30` — hardcoded `rgba(255,255,255,0.8)`. Replace with `alpha(theme.palette.background.paper, 0.8)`.
- `components/PermissionGate.tsx:87` — inline `style={{}}` attribute. Should use `sx`.
- `components/common/SettingsSection.tsx` — `grey.50` hardcoded; `height: 32` magic number.
- `pages/settings/PortfolioModuleSettings.tsx` / `ProjectModuleSettings.tsx` — 95% duplicate; should be one parameterized page.
- `templates/ModuleTabsLayout.tsx` — dead code, delete on sight.
- `ui/typography/*.tsx` — five unused typography wrappers, delete unless adopted with an ESLint rule that forbids raw `Typography variant=` in pages.

## When adding a new page

1. Determine the shell: in-app (`ToolpadShell`), settings (`SettingsShell`), or public (`PublicLayout`).
2. Add the route in `src/config/routes.config.ts` (typed) and wire it in `src/routes.tsx`.
3. If in a shell, wrap the page body in `PageLayout`.
4. If it fetches data, use `useDataFetch` + `DataView`.
5. If it has forms, use `react-hook-form` + `zod`.
6. If it has permission-gated UI, use `PermissionGate`.
7. Do not copy-paste from another page wholesale. Identify the patterns, reuse the primitives, write the specifics.

## When adding a new reusable component

1. First check: does it already exist? Grep `src/components` and `src/ui`.
2. Decide `components/` vs `ui/` per the rule above.
3. Props typed, no `any`.
4. Use theme tokens.
5. Add a one-line entry to this file's relevant section if it's significant enough that other agents should know about it.
