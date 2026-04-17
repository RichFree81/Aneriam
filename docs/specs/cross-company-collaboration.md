# Cross-Company Project Collaboration — Specification (A-2)

**Date:** 2026-03-01
**Status:** Locked

---

## Purpose

Projects are owned by one company. Other companies can be invited as participants with a defined collaboration role. This enables multi-party projects (e.g., main contractor inviting a subcontractor) while maintaining clear ownership and access boundaries.

---

## Ownership Rules

- One company **owns** a project. They created it; they govern it; they control access.
- Other companies are **participants** with a defined role.
- Only the owning company's admins can define or change field definitions on that project.
- Participants see only what the owning company permits based on their role.

---

## Collaboration Roles

| Role | Typical Use |
|------|------------|
| `Contractor` | Primary delivery company |
| `Consultant` | Advisory / oversight |
| `Subcontractor` | Secondary delivery company |
| `Client` | End client / project owner |

These values are stored as plain strings — new roles can be added without a schema change.

---

## Lifecycle

```
Owning company admin sends invitation
          ↓
  status = "Pending"
          ↓
  Invited company admin accepts or declines
          ↓
  status = "Accepted" | "Declined"
```

A declined invitation does not prevent re-invitation.

---

## Database Table: `project_company`

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer PK | |
| `project_id` | integer FK → project | The project being shared |
| `company_id` | integer FK → company | The invited (participating) company |
| `collaboration_role` | string | e.g. Contractor, Client |
| `status` | string | `Pending` \| `Accepted` \| `Declined` |
| `invited_at` | datetime | When the invitation was sent |
| `accepted_at` | datetime nullable | When the invitation was accepted |
| `invited_by_user_id` | integer FK → user | Who sent the invitation |

Unique constraint: `(project_id, company_id)` — one record per company per project.

---

## Access Control

- Owning company admins: full project access + can manage `project_company` entries.
- Accepted participants: read access to the project and its permitted data; no access to field definitions or other companies' data.
- Pending/Declined participants: no access to the project.

---

## API Surface (Phase 3 — C-9)

- `GET /portfolios/{id}/projects/{id}/collaborators` — list collaborating companies
- `POST /portfolios/{id}/projects/{id}/collaborators` — invite a company (owning admin only)
- `PATCH /portfolios/{id}/projects/{id}/collaborators/{id}` — accept / decline invitation
- `DELETE /portfolios/{id}/projects/{id}/collaborators/{id}` — remove collaborator (owning admin only)
