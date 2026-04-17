# Field Library — Specification (A-1)

**Date:** 2026-03-01
**Status:** Locked

---

## Purpose

The Field Library is a governed, hierarchical system for defining what data fields exist on records like projects and portfolios. It enforces naming consistency by ensuring nobody types a field name directly onto a project — they always select from the library.

---

## Library Layers

| Layer | `company_id` | Managed By | Applies To |
|-------|-------------|-----------|-----------|
| Application defaults | `NULL` | Aneriam | Every company, every project — always present |
| Module library | `NULL` | Aneriam | Pre-built optional fields relevant to that module |
| Company library | company's ID | Company admin | Fields specific to how that company works |
| Project assignment | — | Project admin | Picks from module + company library |

---

## Key Rules

1. **Library-only selection.** Field names can only come from the library. Direct text entry is never allowed.
2. **Company defaults.** Company admins set which library fields appear on every new project by default.
3. **Dropdown options in the library.** Dropdown fields carry their allowed options inside the `FieldDefinition.options` column (JSON list). This prevents value inconsistency (e.g., "High" vs "high").
4. **Deprecation, not deletion.** Fields can be deprecated (`is_deprecated = true`) — hidden from new selections — but never deleted if already in use on a live project.
5. **Participants are value-only.** Users from invited companies (via cross-company collaboration) can fill in values only; they never touch field definitions.
6. **Values stored as JSON.** Field values are stored in `project.field_values` as a JSON object keyed by `field_definition.name`. This avoids wide EAV tables and keeps values co-located with the record.

---

## Database Tables

### `field_definition`

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer PK | |
| `company_id` | integer FK → company | NULL = system/module level |
| `module_key` | string | e.g. `projects`, `portfolios` |
| `name` | string | Internal snake_case key; used as JSON key in `field_values` |
| `label` | string | Human-readable display label |
| `field_type` | string | `text` \| `number` \| `date` \| `dropdown` \| `boolean` |
| `options` | text (JSON) | List of allowed values for dropdown type; NULL otherwise |
| `is_required` | boolean | Default required flag (can be overridden per project) |
| `is_deprecated` | boolean | Hidden from new selections; preserved if in use |
| `sort_order` | integer | Display order |
| `created_at` | datetime | |

Unique constraint: `(company_id, module_key, name)`

### `field_assignment`

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer PK | |
| `project_id` | integer FK → project | |
| `field_definition_id` | integer FK → field_definition | |
| `required_override` | boolean nullable | NULL = inherit from field_definition |
| `created_at` | datetime | |

Unique constraint: `(project_id, field_definition_id)`

### `project.field_values`

Text column holding a JSON object. Example:

```json
{
  "priority": "High",
  "budget_code": "CAPEX-001",
  "target_completion": "2026-12-31"
}
```

Keys must match `field_definition.name` values assigned to the project via `field_assignment`.

---

## API Surface (Phase 3 — C-2)

- `GET /field-definitions?module_key=projects` — list available field definitions for the current company
- `POST /field-definitions` — create a company-owned field definition (company admin only)
- `PATCH /field-definitions/{id}` — update label, options, sort_order, is_deprecated
- `GET /portfolios/{id}/projects/{id}/field-assignments` — list assigned fields on a project
- `POST /portfolios/{id}/projects/{id}/field-assignments` — assign a field to a project
- `DELETE /portfolios/{id}/projects/{id}/field-assignments/{id}` — remove field assignment
- `PATCH /portfolios/{id}/projects/{id}/field-values` — update the JSON field values object
