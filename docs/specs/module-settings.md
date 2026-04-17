# Module Settings Storage — Specification (A-4)

**Date:** 2026-03-01
**Status:** Locked

---

## Purpose

Settings screens in the UI look complete but currently save nothing. This spec defines where settings are stored and how they are read back. Settings are per-company and per-module.

---

## Design

- A `module_settings` table stores key-value configuration per company per module.
- Application-level defaults exist in code as a fallback if no company setting is saved.
- Company admins write settings; the system reads the company override first and falls back to the default.

---

## Lookup Logic

```
read_setting(company_id, module_key, key):
    row = SELECT * FROM module_settings
          WHERE company_id = ? AND module_key = ? AND key = ?
    if row:
        return row.value
    return APPLICATION_DEFAULTS[module_key][key]
```

---

## Application Defaults (in code)

These defaults apply to every company that hasn't set an override:

| Module | Key | Default |
|--------|-----|---------|
| `projects` | `display_name` | `Projects` |
| `projects` | `id_prefix` | `PRJ` |
| `projects` | `default_view` | `list` |
| `portfolios` | `display_name` | `Portfolios` |
| `portfolios` | `code_prefix` | `PF` |

---

## Database Table: `module_settings`

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer PK | |
| `company_id` | integer FK → company | |
| `module_key` | string | e.g. `projects`, `portfolios` |
| `key` | string | Setting name, e.g. `display_name` |
| `value` | string | Plain string or JSON-encoded value |
| `created_at` | datetime | |
| `updated_at` | datetime | |

Unique constraint: `(company_id, module_key, key)`

---

## API Surface (Phase 2 — C-1)

- `GET /settings/{module_key}` — get all settings for the current company's module (returns merged defaults + overrides)
- `PUT /settings/{module_key}` — set one or more key-value pairs for the current company's module (company admin only)
- `DELETE /settings/{module_key}/{key}` — reset a key to the application default (company admin only)
