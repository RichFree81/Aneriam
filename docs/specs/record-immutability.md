# Record Immutability and Soft Deletes — Specification (A-3)

**Date:** 2026-03-01
**Status:** Locked

---

## Core Rule

**Nothing in this system is ever permanently deleted.**

Records receive a `deleted_at` timestamp instead (soft delete). All list queries automatically filter `WHERE deleted_at IS NULL`, so users never see deleted records in the UI, but the data is always recoverable and auditable.

---

## Soft Delete Behaviour

| Operation | Behaviour |
|-----------|----------|
| User deletes a record | `deleted_at` is set to the current UTC timestamp |
| List queries | Always include `WHERE deleted_at IS NULL` |
| Detail queries | Return 404 if `deleted_at IS NOT NULL` (same as not found) |
| Restore | Admin sets `deleted_at = NULL` (future admin UI) |
| Permanent deletion | Never permitted |

### Affected Tables

`deleted_at` is present on:
- `project`
- `portfolio`
- `financial_note`
- `portfolio_user`

---

## Workflow Immutability

The `WorkflowMixin` defines the lifecycle: `DRAFT → SUBMITTED → APPROVED → LOCKED`.

| Status | Editable? |
|--------|----------|
| `DRAFT` | Yes — any authorised user |
| `SUBMITTED` | Content locked; status transitions only |
| `APPROVED` | Content locked; only `LOCKED` transition allowed |
| `LOCKED` | No modifications of any kind |

Attempting to edit a `LOCKED` or `APPROVED` record returns `HTTP 409 Conflict`.

---

## Audit Log Immutability

Audit log entries (`audit_log` table) are append-only:
- Entries can never be edited or deleted by anyone, including admins.
- No `UPDATE` or `DELETE` SQL is ever executed on this table.
- API endpoints expose read-only access to audit logs.

---

## Document and Contract Versioning (future)

Document and contract records will use versioning: each edit creates a new version row, the previous version is preserved. The "current" version is the one with the highest version number and no `superseded_at` timestamp.

---

## Query Pattern

Every list endpoint must apply the soft-delete filter:

```python
# Correct
statement = select(Project).where(
    Project.portfolio_id == portfolio_id,
    Project.deleted_at.is_(None)
)

# Wrong — omitting the filter returns deleted records
statement = select(Project).where(Project.portfolio_id == portfolio_id)
```
