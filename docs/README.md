# Documentation Governance Rules

## Directory Structure
- `/docs/frontend` — All frontend-related documentation (UI standards, theme, components)
- `/docs/backend` — All backend-related documentation (API, services, data models)
- `/docs/architecture` — Architecture decision records and system design
- `/docs/product` — Product specifications and requirements
- `/docs/operations` — Operations, deployment, and infrastructure docs
- `/docs/process` — Development process, workflows, and team conventions
- `/docs/decisions` — ADRs (Architecture Decision Records) and major technical decisions
- `/docs/archive` — Obsolete documentation (preserve for historical context)

## Governance Rules

### 1. All permanent documentation must live under `/docs`
Documentation should be organized by category (frontend, backend, architecture, etc.) and placed in the appropriate subfolder.

### 2. All AI-generated reports must live under `/reports`
Temporary analytical artifacts, audits, and reports belong in `/reports`, not `/docs`.

### 3. No standalone markdown files allowed at root except:
- `README.md` (project overview)
- `CHANGELOG.md` (release notes)

### 4. No documentation folders allowed under `/frontend` or `/backend` root
Documentation must be centralized in `/docs`. No `frontend/docs` or `backend/docs` folders.

### 5. No documentation inside `/src` folders
Source code folders should not contain governance documentation. Component-specific README files may exist for inline usage documentation.

### 6. Obsolete documentation must be archived under `/docs/archive`
Do not delete old documentation - preserve it for historical context by moving to `/docs/archive`.

## Adding New Documentation

When adding new documentation:

1. **Identify the correct category**: frontend, backend, architecture, product, operations, process, or decisions
2. **Place the file in the appropriate `/docs/*` subfolder**
3. **Update the relevant index file** if one exists (e.g., `ui-standards-index.md`)
4. **Use descriptive filenames** with kebab-case (e.g., `api-authentication.md`)
5. **If creating a new category**, add it to this governance document and explain its purpose

## Exception: Component-Specific README

Small README files MAY exist alongside components for inline documentation (e.g., `/src/components/MyComponent/README.md`) if they document component-specific usage patterns or API. These are NOT governance documentation and should be brief implementation guides only.

## Enforcement

Violations of these rules should be caught during code review. Automated checks may be added to prevent documentation sprawl.
