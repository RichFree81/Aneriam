# Aneriam UI Standards

**Current Milestone**: F (Governance & Hardening)

## Core Policies (Implemented)
- **[Theme & Palette](./ui-theme-policy.md)** (Milestone A): Colors, typography, and surface rules. ✅ Implemented
- **Core Defaults** (Milestone B): Button, Input, and surface component default props. (See `frontend/src/theme/components.ts`) ✅ Implemented
- **[Page Layout](./page-layout-standard.md)**: Toolpad PageContainer, tabs, title sizing, and content area rules. ✅ Implemented

## Functional Standards
- **[Forms & Validation](./forms-standards.md)** (Milestone C)
- **Feedback & Dialogs** (Milestone D) — Implemented in `ui/feedback/` (LoadingState, ErrorState, EmptyState, ConfirmDialog)
- **Data Presentation** (Milestone E) — Implemented in `components/` (DataView, DataToolbar, StandardDataGrid, charts)

## Governance (Milestone F)
- **[Accessibility Checklist](./accessibility.md)**: Keyboard, labels, and contrast rules.
- **[Responsive Patterns](./responsive.md)**: Mobile adaptation rules.
- **[Golden Screens](./golden-screens.md)**: Reference pages for regression testing.

## Enforcement
To verify standards locally:
1. `npm run lint`: Checks for coding standard violations (raw colors, bad shadows, missing labels).
2. **Manual Check**: Visit [Golden Screens](./golden-screens.md) and verify behavior.
