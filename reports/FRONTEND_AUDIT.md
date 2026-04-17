# Frontend Audit — Aneriam

**Auditor:** Claude (read-only investigation)
**Date:** 17 April 2026
**Scope:** `/frontend` only (React + TypeScript SPA). Backend untouched.
**Verdict (one sentence):** The foundation is genuinely solid — keep it, tidy it up, and add an agent-guidance file. Do **not** start over.

---

## 1. Executive Summary

The frontend is small (roughly 50 source files, ~3.5k lines) but well-architected. It runs on a modern, mainstream stack (React 19 + MUI v7 + Vite + TypeScript strict) and demonstrates clear intent: a centralized theme, typed route/navigation configs, five purposeful contexts, a custom `useDataFetch` hook that mirrors documented lifecycle rules, and — rare for a project this small — an ESLint policy that actively rejects raw hex colors, raw rgba strings, and unlabeled IconButtons. Drift is low: one inline `style` attribute, one non-theme rgba, zero CSS modules, zero `!important`, zero stray console logs, zero TODO markers.

The risks are not structural; they are coverage and maturity risks. Several pages are stubs (`Landing`, `ProfileSettings`, `SecuritySettings` are 12-13 lines each), `PortfolioModuleSettings` and `ProjectModuleSettings` are near-verbatim copy-pastes of each other, and the documented standards in `/docs/frontend/` partially outpace reality (the "Golden Screens" test routes don't exist, and the forms story relies on raw `useState` — there is no form library). There is also no `CLAUDE.md`, `.cursorrules`, or `AGENTS.md` at the root, which is the single cheapest, highest-ROI gap to close before you let more agent-authored code land.

**Recommendation: (a) minor tidy-up + add `CLAUDE.md`.** You do not have a rework problem. You have a "finish what you started and write the rules down for collaborators" problem.

---

## 2. Stack Overview

Taken from `frontend/package.json`:

- **Framework:** React 19.2.0 + ReactDOM 19.2.0
- **Language:** TypeScript ~5.9.3 (strict mode on, `noUnusedLocals`, `noUnusedParameters`, `noUncheckedSideEffectImports`)
- **Build tool:** Vite 7.2.4 (`@vitejs/plugin-react` 5.1.1)
- **UI library:** `@mui/material` 7.3.7, `@mui/icons-material` 7.3.7
- **Data grid:** `@mui/x-data-grid-pro` 8.27.0 (Pro tier — licensed)
- **Shell/dashboard:** `@toolpad/core` 0.16.0 (provides `AppProvider` + `DashboardLayout`)
- **Styling:** `@emotion/react` 11.14.0, `@emotion/styled` 11.14.1 (via MUI)
- **Routing:** `react-router-dom` 7.12.0
- **Charts:** `recharts` 3.7.0
- **Forms:** none (raw `useState` + controlled MUI inputs)
- **Data fetching:** none (raw `fetch` inside a custom `authenticatedFetch` wrapper + `useDataFetch` hook)
- **State management:** React Context only (5 providers)
- **Linting:** ESLint 9.39.1 + typescript-eslint 8.46.4 + custom governance rules (see §6)

No Redux, Zustand, Jotai, react-query, SWR, Formik, react-hook-form, Zod, Yup, axios, tailwind, CSS modules, or styled-components. That is a deliberate — and, for this app size, defensible — minimalism.

---

## 3. Project Structure

```
frontend/
├── index.html                    # CSP-locked entry
├── vite.config.ts                # Plain Vite+React config
├── eslint.config.js              # Custom governance rules (see §6)
├── tsconfig.app.json             # Strict TS
├── public/                       # Only vite.svg
├── scripts/
└── src/
    ├── App.tsx                   # ErrorBoundary + Router
    ├── main.tsx                  # Theme + 5 context providers
    ├── routes.tsx                # All routes in one place, PrivateRoute wrapper
    ├── index.css / App.css       # Empty shells; min-width:1024px global
    ├── api/                      # 5 files — fetch wrapper + per-domain modules
    ├── assets/                   # Logo
    ├── components/               # Mixed: layout/, charts/, dashboard/, dialogs/,
    │                             #   forms/, grid/, common/ + loose files
    ├── config/                   # Routes, navigation, core, license, charts
    ├── context/                  # 5 providers (auth/portfolio/filter/actions/notifications)
    ├── hooks/                    # useDataFetch, useFeatureFlag, usePermission, useRegisterAction
    ├── layouts/                  # ToolpadShell, SettingsShell, PublicLayout
    ├── pages/                    # 9 pages (3 stubs, 2 copy-paste duplicates)
    ├── templates/                # ModuleTabsLayout (unused)
    ├── theme/                    # index, palette, typography, components, settingsTheme
    ├── types/                    # auth, enums, module, portfolio, project
    ├── ui/                       # feedback/ (4) + typography/ (5 thin wrappers)
    └── utils/                    # format.ts only
```

Two observations worth calling out now:

1. `components/` and `ui/` are **both** "reusable UI" buckets. The distinction (`ui/` = headless feedback + typography; `components/` = app-aware widgets) is defensible, but it is not explained anywhere and new contributors will dump things in the wrong folder.
2. `templates/ModuleTabsLayout.tsx` exists but is imported by zero files — dead code that was probably intended to solve the `PortfolioModuleSettings` / `ProjectModuleSettings` duplication (see §7).

---

## 4. Shell & Layout Assessment

**Rating: Usable (leaning toward Solid).**

Three shells exist, each clearly purposed:

- **`layouts/ToolpadShell.tsx`** (123 lines) — wraps all authenticated in-app routes. Uses `@toolpad/core`'s `AppProvider` + `DashboardLayout`, wires React Router into Toolpad's router shape, renders a fixed-center logo, a breadcrumb showing `{portfolio} / {project filter}`, a global Add menu, a project-filter IconButton, and a settings IconButton. Hooks into four contexts (`useAuth`, `usePortfolio`, `useProjectFilter`, plus dialog state). Clean.
- **`layouts/SettingsShell.tsx`** (101 lines) — near-identical to `ToolpadShell` but with `SETTINGS_NAVIGATION`, a different breadcrumb (`{company} / Settings`), a slate-coloured `settingsTheme`, and no project filter. The comment on line 55 literally says "SAME AS APPLICATION SHELL." Most of the logo block (lines 56–67) is duplicated verbatim between the two shells.
- **`layouts/PublicLayout.tsx`** (34 lines) — a centered full-height wrapper for `Login` and `SelectPortfolio`. Correct `component="main"`. Minimal and fine.

There is also a **page-level primitive**: `components/layout/PageLayout.tsx` (127 lines). This is the real workhorse — it renders the full-bleed header (title, breadcrumbs, optional tabs), uses `'standard'` (24px) or `'utility'` (16px) spacing contexts per `docs/frontend/page-spacing-spec.md §4.2`, and exposes a content area. All in-app pages except the public/auth ones compose `PageLayout` inside the shell. That is the correct pattern.

**What's good**
- Clear three-shell split (app / settings / public).
- Design-token-driven spacing contexts are documented AND implemented.
- `PrivateRoute` wrapper in `routes.tsx` cleanly handles auth + portfolio gating with no redirect loops.
- Accessibility primitives are in place: `aria-label="breadcrumb"`, `aria-label` on filter/settings IconButtons, `component="main"` on `PublicLayout`.

**What's missing or rough**
- `ToolpadShell` and `SettingsShell` share ~30 lines of logo/branding code that should live in one place.
- `PageLayout` uses a **magic fractional margin**: `mb: -1 / 8` (line 106) — a hand-tuned pixel nudge to sit tabs exactly on a border. Works, but the next person to touch this file will either delete it or break it.
- There is no shared `Container`/`Section` primitive below `PageLayout`. Pages hand-roll `<Grid container spacing={2}>` every time.
- `index.css` sets `body { min-width: 1024px }` — the app is **explicitly desktop-only**. This is a product decision, not a bug, but it should be surfaced before market launch (see §9).

---

## 5. Component Inventory

Counts below are **direct imports of the component from elsewhere in `src/`**.

| # | Component | Path | Purpose | Used in (count) | Duplicates? | Quality |
|---|---|---|---|---|---|---|
| 1 | `ToolpadShell` | `layouts/ToolpadShell.tsx` | Authenticated app shell | 1 (routes) | Shares 30+ lines w/ SettingsShell | Good |
| 2 | `SettingsShell` | `layouts/SettingsShell.tsx` | Settings-context shell | 1 (routes) | Near-dup of ToolpadShell | Okay |
| 3 | `PublicLayout` | `layouts/PublicLayout.tsx` | Centered wrapper for Login/SelectPortfolio | 2 | — | Good |
| 4 | `PageLayout` | `components/layout/PageLayout.tsx` | In-page header + tabs + content | 6 | — | Good |
| 5 | `ModuleTabsLayout` | `templates/ModuleTabsLayout.tsx` | Tab-based module layout | **0 (dead)** | Overlaps PageLayout | Okay |
| 6 | `DataView` | `components/DataView.tsx` | Loading/error/empty/success switch | 1 | — | Good |
| 7 | `DataToolbar` | `components/DataToolbar.tsx` | Search + filters row | 0 | — | Okay |
| 8 | `StandardDataGrid` | `components/grid/StandardDataGrid.tsx` | MUI DataGridPro wrapper | 1 | — | Okay |
| 9 | `ErrorBoundary` | `components/ErrorBoundary.tsx` | App-level error boundary | 1 (App.tsx) | — | Good |
| 10 | `PermissionGate` | `components/PermissionGate.tsx` | Permission-based conditional render | 1 | — | Okay (inline `style` on L87) |
| 11 | `BaseChartContainer` | `components/charts/BaseChartContainer.tsx` | Chart lifecycle wrapper | 4 | — | Good (1 rgba drift) |
| 12 | `TimeSeriesChart` | `components/charts/TimeSeriesChart.tsx` | Recharts line chart | 1 | — | Good |
| 13 | `CategoryBarChart` | `components/charts/CategoryBarChart.tsx` | Recharts bar chart | 1 | — | Good |
| 14 | `DistributionPieChart` | `components/charts/DistributionPieChart.tsx` | Recharts pie/donut | 1 | — | Good |
| 15 | `ChartTooltip` | `components/charts/ChartTooltip.tsx` | Shared Recharts tooltip | 0 direct (used via charts) | — | Okay |
| 16 | `KpiCard` | `components/dashboard/KpiCard.tsx` | Metric card with trend | 1 | — | Good |
| 17 | `ProjectCreateDialog` | `components/dialogs/ProjectCreateDialog.tsx` | Create-project form dialog | 0 | — | Okay |
| 18 | `ProjectSelectionDialog` | `components/dialogs/ProjectSelectionDialog.tsx` | Project multi-select dialog | 1 (ToolpadShell) | — | Poor (mixes UI + logic) |
| 19 | `FormSection` | `components/forms/FormSection.tsx` | Field group w/ title | 0 | — | Good |
| 20 | `FormGlobalError` | `components/forms/FormGlobalError.tsx` | Form-level error alert | 0 | — | Good |
| 21 | `SettingsSection` | `components/common/SettingsSection.tsx` | Edit-mode settings card | 2 (the duplicate pages) | — | Okay (hardcoded `grey.50`, `height:32`) |
| 22 | `GlobalAddMenu` | `components/common/GlobalAddMenu.tsx` | Toolbar add menu (action registry-driven) | 2 (both shells) | — | Okay |
| 23 | `TabPanel` | `components/common/TabPanel.tsx` | A11y tab panel | 2 | — | Good |
| 24 | `ConfirmDialog` | `ui/feedback/ConfirmDialog.tsx` | Yes/no confirmation dialog | 0 | — | Good |
| 25 | `EmptyState` | `ui/feedback/EmptyState.tsx` | "No data" placeholder | 1 (DataView) | — | Good |
| 26 | `ErrorState` | `ui/feedback/ErrorState.tsx` | Error placeholder w/ retry | 1 (DataView) | — | Good |
| 27 | `LoadingState` | `ui/feedback/LoadingState.tsx` | 3-variant spinner | 1 (DataView) | — | Good |
| 28 | `PageTitle` / `SectionTitle` / `SubsectionTitle` | `ui/typography/*.tsx` | `<Typography variant=...>` wrappers | 0 each | Just wrap MUI Typography | Okay — thin/unused |
| 29 | `BodyText` / `HelpText` | `ui/typography/*.tsx` | Typography wrappers | 0 each | — | Poor — never used; delete or adopt |

**Summary:** 29 components (ignoring `index.ts` barrels). Nothing is a catastrophe. Notable issues:
- **4 unused components**: `ModuleTabsLayout`, `ConfirmDialog`, `ProjectCreateDialog`, `DataToolbar`, `FormSection`, `FormGlobalError`, and all five `ui/typography/*` wrappers have zero or near-zero usage. Some are scaffolding for pages that haven't been built yet (`FormSection`, `FormGlobalError` are explicitly referenced in `docs/frontend/forms-standards.md`) — so "unused" partly means "the consumer doesn't exist yet." Fine, but it adds noise.
- **1 poor component**: `ProjectSelectionDialog.tsx` (132 lines) mixes UI, fetch-like filtering, and business logic. It's the best candidate for extraction when you do the first refactor pass.
- **2 near-duplicate shells**: `ToolpadShell` + `SettingsShell` (see §4).

---

## 6. Design System Audit

**This is the codebase's strongest area.** There is not much drift because the ESLint config won't allow it.

### Defined tokens (all in `src/theme/`)

- **Palette** (`theme/palette.ts`): primary `#1976d2`, secondary `#9c27b0`, text primary `#1a1a1a`, text secondary `#666666`, bg default `#f5f5f5`, bg paper `#ffffff`, divider `rgba(0,0,0,0.12)`. Plus a second palette in `settingsTheme.ts` (slate `#475569/#334155/#64748b`, white bg).
- **Typography** (`theme/typography.ts`): one override — `h4: 1.19rem`. Everything else inherits MUI defaults. Thin.
- **Components** (`theme/components.ts`): one override — `MuiTab.root.textTransform: 'none'`. Thin.
- **Shape**: `borderRadius: 4` (applied twice, in both themes).
- **Shadows**: never redefined — always referenced as `theme.shadows[n]`.

### Governance (ESLint)

`frontend/eslint.config.js` encodes real rules, not aspirations:

- No raw `#hex` literals anywhere except `src/theme/palette.ts` and `docs/**`.
- No raw `rgb()/rgba()` literals.
- No pixel strings in `boxShadow`.
- `IconButton` must have `aria-label` or `title`.

This is the single biggest reason the foundation is solid. Most small codebases have no enforcement at all.

### Drift metrics (as observed)

| Dimension | Distinct values found | Interpretation |
|---|---|---|
| Colors (hex) | 10 unique, **all in theme files** except 0 outside | Excellent |
| Colors (rgba) | 2 total — 1 in theme (divider), 1 drift in `BaseChartContainer.tsx:30` (`rgba(255,255,255,0.8)` — also flagged by ESLint) | Near-excellent; 1 known drift |
| Inline `style={{...}}` | **1** (`PermissionGate.tsx:87` `style={{ display: 'inline-block' }}`) | Excellent |
| Raw pixel strings in `sx` | **3** (`CategoryBarChart.tsx:68`, `TimeSeriesChart.tsx:66` — both `paddingTop:'10px'`; plus `index.css` `min-width:1024px`) | Near-excellent |
| Distinct `fontSize` values | 6 (`0.75rem`, `1.19rem`, `1.25rem`, `12`, `48`, `{xs:'4rem',sm:'6rem'}`, plus `"small"/"large"` MUI props) | Moderate — mostly in charts & the 404 page |
| Distinct `borderRadius` values | 4 (`1`, `2`, `4`, `'50%'`) — all theme-scaled | Excellent |
| `boxShadow` values | 3 (`theme.shadows[2]`, `theme.shadows[4]`, `'none'`) — zero hardcoded strings | Excellent |
| CSS modules (`*.module.css`) | 0 | Excellent — no mixed styling systems |
| `!important` | 0 | Excellent |
| `console.log/warn/info/debug` | 0 | Excellent |
| `TODO` / `FIXME` / `HACK` | 0 | Excellent |

**Consistency scores (my judgment, backed by the counts above):**

| Area | Score |
|---|---|
| Colors | 9/10 — 1 rgba drift in charts (and it's already lint-flagged) |
| Spacing | 9/10 — MUI tokens used; 2 raw px strings in charts |
| Typography | 7/10 — six distinct sizes is fine, but `theme/typography.ts` is nearly empty. Most variants are "whatever MUI ships." |
| Border radius | 10/10 |
| Shadows | 10/10 |

**Aggregate drift score: very low.** This is rarer than it sounds.

### Specific inconsistencies worth citing

- `components/charts/BaseChartContainer.tsx:30` — `backgroundColor: 'rgba(255, 255, 255, 0.8)'`. Should be `alpha(theme.palette.background.paper, 0.8)`. ESLint already warns on this.
- `components/common/SettingsSection.tsx` — uses `grey.50` (line ~45) rather than a semantic token; hardcoded `height: 32` for the header stack.
- `components/DataToolbar.tsx:78` — hardcoded search width `240`.
- `components/grid/StandardDataGrid.tsx:114` — hardcoded `minHeight: 400`.
- `components/dialogs/ProjectSelectionDialog.tsx:97` — hardcoded `maxHeight: 400`.
- `components/layout/PageLayout.tsx:106` — the `-1/8` magic margin.

None of these break the app. They're the kind of thing a passing cleanup pass resolves in an afternoon.

---

## 7. Anti-Patterns Found

| Severity | Issue | Location | Why it matters |
|---|---|---|---|
| **High** | **Copy-paste duplication of an entire page.** `pages/settings/PortfolioModuleSettings.tsx` (142 lines) and `pages/settings/ProjectModuleSettings.tsx` (142 lines) are ~95% identical — same structure, same tabs, same two `SettingsSection`s, same edit-state pattern. Only the labels, default values, and one select's options differ. | `pages/settings/PortfolioModuleSettings.tsx`, `pages/settings/ProjectModuleSettings.tsx` | Every future change has to be made twice. The fix — a single `ModuleSettingsPage` that takes a config object — is probably 50 lines. |
| **High** | **Three stub pages in production routing.** `pages/Landing.tsx` (12 lines — renders "Dashboard content to be rebuilt."), `pages/settings/ProfileSettings.tsx` (13 lines — "Profile settings content to be rebuilt."), `pages/settings/SecuritySettings.tsx` (13 lines — "Security content to be rebuilt."). | See paths | They are currently reachable in production routing. A market-ready build should either feature-flag these or replace them. |
| **High** | **Shell duplication.** `ToolpadShell.tsx` and `SettingsShell.tsx` share ~30 lines of branding/logo/router-adapter code. | `layouts/*Shell.tsx` | Two places to change when the brand moves, the logo changes, or Toolpad changes API. |
| Medium | **Stale lint output and stale file references.** `frontend/lint-output.txt` (6 errors, 1 warning — last captured on Windows `C:\Dev\Aneriam\`) references `src/context/ShellContext.tsx`, which no longer exists. | `frontend/lint-output.txt` | Minor, but suggests lint isn't routinely run in CI. The current codebase still has lint errors: `typography.ts:1` `@ts-ignore`; the `any` types in four chart components. |
| Medium | **Inline `style={{}}` attribute.** | `components/PermissionGate.tsx:87` | Violates stated policy ("Use the `sx` prop or theme tokens"). |
| Medium | **Hardcoded non-theme rgba.** `rgba(255,255,255,0.8)` | `components/charts/BaseChartContainer.tsx:30` | Violates ESLint rule; already flagged. |
| Medium | **Dead template.** `templates/ModuleTabsLayout.tsx` imported by nothing. | `templates/ModuleTabsLayout.tsx` | Confuses contributors — did the duplication in Portfolio/ProjectModuleSettings happen *despite* this template, or *before* it? |
| Medium | **Unused typography wrappers.** `BodyText`, `HelpText`, `PageTitle`, `SectionTitle`, `SubsectionTitle` have 0 imports. | `ui/typography/*.tsx` | Either adopt them and forbid raw `<Typography variant=...>` in pages, or delete them. |
| Medium | **Magic margin.** `mb: -1 / 8` | `components/layout/PageLayout.tsx:106` | Undocumented fractional spacing value — brittle. |
| Medium | **Inline ternary bg toggle in settings TextFields.** `sx={{ bgcolor: editIdentity ? 'background.paper' : 'transparent' }}` | `pages/settings/PortfolioModuleSettings.tsx` and `ProjectModuleSettings.tsx` (many lines) | Repeated 10+ times across two files; should be a variant on `SettingsSection` / `TextField`. |
| Medium | **No-form-library forms.** All forms (Login; both ModuleSettings pages) use raw `useState`. No validation library, no schema, no async-submit abstraction. | `pages/Login.tsx`, both `*ModuleSettings.tsx` | Will not scale. Settings forms have no `onSave` wired yet — you don't have a form-submission story. |
| Medium | **`NotFound` page rolls its own layout.** | `pages/NotFound.tsx` | Bypasses `PublicLayout`, violates `docs/frontend/` standards. |
| Low | **`components/` vs `ui/` split is undocumented.** | n/a | New files will end up in the wrong one. |
| Low | **`@ts-ignore` usage.** | `theme/typography.ts:1`, `components/PermissionGate.tsx:90` | Should be `@ts-expect-error`; ESLint already flags. |
| Low | **`any` types in chart props.** | `CategoryBarChart.tsx:23`, `ChartTooltip.tsx:32`, `TimeSeriesChart.tsx:17` | Recharts typing is awkward; fine short-term, tech debt long-term. |

---

## 8. State, Data & Forms

### Data fetching (consistent — and minimal)

- Single entry point: `api/client.ts`. It exports `authenticatedFetch(path, options)` with Bearer-token injection from `localStorage`, a 30s `AbortSignal` timeout, a single-attempt refresh via `/auth/refresh` on 401, and a typed `ApiError` class.
- Per-domain modules (`api/auth.ts`, `portfolios.ts`, `projects.ts`, `modules.ts`) wrap `authenticatedFetch` with a thin typed surface.
- Consumption is standardized through `hooks/useDataFetch.ts` — a homemade replacement for `react-query` that implements the app's own documented lifecycle rules (4 states: idle/loading/success/error; 300ms loading-delay per spec D-02; `AbortController` cleanup on unmount per D-08; `isEmpty` detection).
- **No caching, no dedupe, no background refresh.** Every page navigation re-fetches. For a project-management app at current size that's fine; when you add real dashboards it will hurt.

### Client state (consistent, justified)

Five contexts, wrapped in order in `main.tsx`: Auth → Portfolio → ProjectFilter → ActionRegistry → Notification.

- `AuthContext` (~82 lines) — user + token + login/logout. Justified.
- `PortfolioContext` (~121 lines) — active portfolio + list, persists active portfolio in `sessionStorage`. Justified.
- `ProjectFilterContext` (~129 lines) — project list + filter mode. Borderline — could be module state, but the shell reads it for the breadcrumb.
- `ActionRegistryContext` (~52 lines) — global registry that `GlobalAddMenu` consumes. Justified only if many components register actions.
- `NotificationContext` (~135 lines) — snackbar/toast queue. Justified.

No Redux / Zustand / Jotai. Good call at this size.

### Forms (not consistent — not really handled at all)

- `Login.tsx` uses controlled `useState`, validates inline, uses the auth context's `login()`.
- `ProjectCreateDialog.tsx` uses `useState` + inline `api/projects.ts` calls (no validation, no submit error handling).
- `PortfolioModuleSettings.tsx` / `ProjectModuleSettings.tsx` use `useState` to toggle edit mode per section — **with no `onSave` handler actually wired**. They toggle edit off when you click Save, but nothing is submitted.
- No validation library. No schema. No form library. No submit abstraction.
- `docs/frontend/forms-standards.md` describes validation triggers (`onBlur` / `onSubmit`), `error`/`helperText` usage, `FormSection` grouping, and `FormGlobalError` for global errors. Those components exist. They are **not used** in any page.

This is the biggest *feature* gap. The design system says "forms look like this"; the forms themselves don't exist yet.

### Loading / error states

- Where present (`Login`, `SelectPortfolio`), the pattern is consistent: `CircularProgress` while loading; MUI `Alert severity="error"` on failure; inputs disabled during submit.
- Where absent (all settings pages), it's because there is no async work — yet.
- `components/DataView.tsx` + `ui/feedback/{Loading,Error,Empty,}State.tsx` are purpose-built for the 4-state lifecycle but are only used in one place (`DataView` itself). When you build real data pages, the primitives are already waiting for you.

---

## 9. Accessibility & Responsive

### Accessibility — pass with notes

- **Semantic HTML:** `PublicLayout` uses `component="main"`. `Login` uses `<form>`. Breadcrumbs use `aria-label="breadcrumb"`. IconButtons on both shells have `aria-label`. ESLint actively enforces `aria-label` on `IconButton` (see §6).
- **Fails / thin spots:**
    - `pages/NotFound.tsx` uses `<Box>` divs only — no `<main>`, no heading hierarchy.
    - `SelectPortfolio` avatar buttons have no descriptive label beyond initials.
    - `ModuleSettings` cards have clickable areas with icon-only context.
    - Settings `TextField`s don't announce their edit/read-only state.
    - No `skip-to-content` link, no `aria-live` region (the `NotificationContext` renders toasts — worth checking that MUI Snackbar is configured politely).
    - Keyboard navigation: should work by virtue of using MUI primitives; I did not instrument it.
- `docs/frontend/accessibility.md` exists as a checklist but there is no automated a11y test (no jest-axe, no Playwright + axe) in the repo.

### Responsive — **explicitly desktop-only**

- `src/index.css:19` sets `body { min-width: 1024px; overflow-x: auto }`. Below 1024px the app horizontally scrolls.
- `docs/frontend/responsive.md` contains patterns for mobile (360px minimum, drawer collapse, etc.) — which contradicts the actual CSS.
- `ToolpadShell` and `SettingsShell` use `display: { xs: 'none', md: 'flex' }` to hide the logo on mobile — implying some mobile intent — but the `min-width` kills it regardless.
- `ConfirmDialog` responds with `fullScreen` on mobile breakpoints — which is unreachable in the current build.

**Verdict:** The code is mobile-aware in pockets, but the global CSS says "desktop only." Before you ship to market, decide whether that's a feature (enterprise PMO tool for big screens — totally reasonable) or a bug, and align docs + CSS accordingly. Right now the docs lie.

---

## 10. Top 10 Concrete Issues (ranked by impact)

| # | Issue | Where | Why it matters | Fix size |
|---|---|---|---|---|
| 1 | **No `CLAUDE.md` / `AGENTS.md` / `.cursorrules` at project root.** | `/` | You're about to deploy to market. Every future agent session rediscovers conventions from scratch and risks introducing drift that your ESLint rules don't cover (component placement, forms approach, naming, etc.). Highest leverage fix in this audit. | S |
| 2 | **Two near-identical `*ModuleSettings` pages.** | `pages/settings/PortfolioModuleSettings.tsx`, `ProjectModuleSettings.tsx` | 284 lines that should be one parameterized page. Every future settings change has to be done twice. | S–M |
| 3 | **Three stub pages routed in production.** | `Landing.tsx`, `ProfileSettings.tsx`, `SecuritySettings.tsx` | "Content to be rebuilt" shown to users on market launch is not acceptable. Either feature-flag them or gate the deploy. | S (gate) / L (implement) |
| 4 | **No form-submission story.** | all forms | Settings pages look editable but nothing saves. You have `FormSection`, `FormGlobalError`, and docs — and no page that uses them. Before launch, pick a form library (react-hook-form + Zod is the boring, correct choice) and build *one* form end-to-end. | M |
| 5 | **`ToolpadShell` vs `SettingsShell` duplication.** | `layouts/` | ~30 lines of branding copied between them. Extract a `<ShellBranding>` component or a `useShellChrome()` helper. | S |
| 6 | **Desktop-only CSS contradicts "mobile" docs.** | `src/index.css`, `docs/frontend/responsive.md` | Either remove `min-width: 1024px` and actually support mobile, or rewrite `responsive.md` to say "desktop primary." Decide before users ask. | S (doc) / L (real mobile) |
| 7 | **Stale lint output + existing lint errors.** | `frontend/lint-output.txt`, `theme/typography.ts:1`, chart components (`any`) | File references non-existent `ShellContext.tsx`; current code has 6 errors / 1 warning. Lint should be CI-gating. | S |
| 8 | **`ProjectSelectionDialog.tsx` mixes UI + business logic.** | `components/dialogs/ProjectSelectionDialog.tsx` | Poorest single component. Extract selection + search to a hook; keep the dialog presentational. | M |
| 9 | **Unused typography wrappers + dead `ModuleTabsLayout` template.** | `ui/typography/*.tsx`, `templates/ModuleTabsLayout.tsx` | Either adopt and enforce, or delete. Today they just add surface area for contributors to misuse. | S |
| 10 | **No data caching / dedupe.** | `hooks/useDataFetch.ts` | Acceptable today, will bite you when dashboards land. Plan to adopt `@tanstack/react-query` before the first data-heavy module, not after. | M when you need it |

---

## 11. What's Actually Good

Don't miss the forest. This is the shortlist of things to **preserve** through any refactor:

- **Strict TypeScript + lean scripts.** `tsconfig.app.json` has `strict`, `noUnusedLocals`, `noUnusedParameters`, `noUncheckedSideEffectImports`. Build is `tsc -b && vite build`. That is the right baseline.
- **Governance via ESLint, not vibes.** The `no-restricted-syntax` rules banning raw hex/rgba and enforcing `IconButton` `aria-label` are genuinely protecting the design system. Keep this and extend it.
- **Centralised theme with two deliberate variants.** `theme/index.ts` + `settingsTheme.ts` share `palette`, `typography`, `components`, `shape`. Overriding only primary + background for the Settings context is tasteful — and a real use of MUI's theme system.
- **A thin, documented shell layer.** `ToolpadShell`, `SettingsShell`, `PublicLayout`, with `PageLayout` as the in-page header primitive. Three clean abstractions.
- **`useDataFetch` hook that mirrors the docs.** The 300ms loading delay, AbortController cleanup, and 4-state model map directly onto documented rules. Few apps this size have that discipline.
- **Typed routes and navigation config.** `config/routes.config.ts` centralizes route strings; `config/navigation.config.tsx` drives both shells' menus. No stringly-typed hrefs scattered through pages.
- **Purposeful context stack.** Five providers, no Redux, no prop drilling, each context < 140 lines.
- **Real documentation at `docs/frontend/`.** `page-layout-standard.md`, `page-spacing-spec.md`, `ui-theme-policy.md`, `forms-standards.md`, `accessibility.md`, `responsive.md`, `ui-standards-index.md`. Detailed, specific, enforceable. Mostly implemented.
- **Locked CSP in `index.html`.** Decent default. (Loosen `'unsafe-inline'` / `'unsafe-eval'` later, but it's a start.)
- **Error boundary at the root.** `App.tsx` wraps the whole router in `ErrorBoundary`. Correct.
- **Near-zero drift metrics.** 0 CSS modules, 0 `!important`, 0 stray console logs, 0 TODO markers, 1 inline `style`, 1 non-theme rgba. Very clean for a real app.

---

## 12. Recommended Path Forward

**Option (a): minor tidy-up + add `CLAUDE.md`.** This is my recommendation.

Rationale. The architecture is sound, the design-system governance is real, the stack is mainstream and current, and the drift is already low. There is no structural problem to solve. The gaps are (i) pages that haven't been built yet, (ii) one copy-paste that should be a parameterised component, (iii) a handful of stale artefacts, and (iv) the absence of written conventions for future contributors. Options (b) or (c) would throw away working governance and documented standards for no gain.

### Cleanup items, in order

1. **Write `CLAUDE.md` at the repo root.** Include: the shell / PageLayout pattern; the `ui/` vs `components/` distinction; the "theme tokens only" rule; the "no raw hex/rgba" rule; the `useDataFetch` + `DataView` lifecycle contract; the "forms use `FormSection` + `FormGlobalError` (eventually react-hook-form)" plan; and the list of files never to touch (`theme/palette.ts`, `eslint.config.js`) without explicit permission. Also write `AGENTS.md` pointing at it if you want OpenAI-family tools to find it too. **~1 hour. Biggest single win.**
2. **Merge the two `*ModuleSettings` pages.** Create one `ModuleSettingsPage` that takes `{ title, idPrefix, defaultSelectOptions, singular, plural, description }` as props. Delete the `142+142` duplicate. **~2 hours.**
3. **Decide the fate of the three stub pages.** Either feature-flag them behind `enableDarkMode`-style flags (you already have `useFeatureFlag`), or build minimum-viable versions. Don't ship "content to be rebuilt" to paying users. **~half a day (gate) or ~a week (build).**
4. **Fix the existing lint errors and delete `lint-output.txt`.** Replace `@ts-ignore` with `@ts-expect-error` in `theme/typography.ts`; type the `any`s in the four chart components (use Recharts' exported types or `unknown`); remove the stale Windows-path output file; add `npm run lint` to CI. **~2 hours.**
5. **Reconcile the desktop-only decision.** Either remove `min-width: 1024px` from `index.css` and own the mobile work, or update `docs/frontend/responsive.md` to say the app is desktop-primary. **~15 minutes to pick; longer to execute if you go mobile.**

### Second wave (do these within the next month, not before launch)

- Extract `<ShellBranding>` and deduplicate `ToolpadShell` + `SettingsShell`.
- Adopt react-hook-form + Zod and build one real end-to-end form (recommend: `ProfileSettings` — small, high-value).
- Refactor `ProjectSelectionDialog` into a presentational dialog + a `useProjectSelection()` hook.
- Delete unused typography wrappers OR adopt them and add a lint rule forbidding raw `variant=` outside `ui/`.
- Delete `templates/ModuleTabsLayout.tsx` (it has zero usages).
- Replace the `BaseChartContainer.tsx:30` rgba with `alpha(theme.palette.background.paper, 0.8)`.

### Not now — but plan for it

- Adopt `@tanstack/react-query` before the first data-heavy module ships. `useDataFetch` is serviceable today but will not scale.
- Write one Playwright smoke test + jest-axe run in CI. You have an a11y checklist; you have no automated a11y check.
- Tighten the CSP when the auth flow stabilizes.

---

### Closing note

If this were a large legacy codebase with 400 components and a decade of drift, my answer would be different. This is a small, intentional, early-stage codebase that has *already* made most of the hard decisions correctly: one theme, one shell pattern, one data-fetch hook, lint-enforced tokens, typed routes, documented standards. The work remaining is finishing features and writing the conventions down — not rebuilding foundations.

Ship the tidy-up, add `CLAUDE.md`, and keep going.
