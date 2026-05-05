# RTO & Purchase-Order Mapping — Spec v1

**Status:** Signed off — building. **Date:** 2026-05-05. **Scope:** Cost Control MVP (`app/`).

## 1. Goal

Let the cost controller create Requests-To-Order (RTOs) inside the Cost Control app, track their status through award, and link them to NetSuite Purchase Orders after import — so every PO on a project is either *attributed to an RTO* or visibly *Unassigned*.

## 2. In scope (this spec)

- RTO records with header data (header-only — no line items in v1).
- RTO status workflow: **Draft → Submitted → Approved → Issued for PO → Cancelled**.
- Link table tying any imported PO to one RTO.
- "Unassigned POs" filter on the existing Purchase Orders tab.
- "Link to RTO" action per PO row, with **suggested matches** ranked by vendor + amount + project + date.
- Manual unlink (mistake recovery).
- One CSV/PDF export of the RTO header (basic — for filing).

## 3. Out of scope (explicitly NOT in v1)

- **Line items on RTOs.** RTO total is a single number for now. Line-level entry can come later if the workflow needs it.
- **Auto-matching from PO memo (Option 3).** Layered later as just one more matcher.
- **PDF generation matching the RTO Excel template.** A simple HTML print-view will do; faithful template reproduction is a later concern.
- **Multi-step approval workflow.** Status flips are unrestricted for v1 — the cost controller is the operator.
- **Email notifications, audit log of edits.** Skip for v1; add when there are multiple users.
- **RTO line items mapped to Project Tasks / Activity Codes / CC codes.** A "package" link is enough granularity for now.

## 4. Data model

Two new tables. Both append to `cost_control.db` via the existing startup-migration list in `app.py` (no Alembic).

### 4.1 `rto`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `rto_number` | TEXT NOT NULL UNIQUE | e.g. `5009.RTO.001`. App-generated next number per project on create. |
| `project_number` | TEXT NOT NULL | FK to `projects.project_number` (logical, not enforced — same pattern as elsewhere in this DB) |
| `package_number` | TEXT NULL | FK to `packages.package_number` — optional; lets user tie an RTO to a package upfront. |
| `vendor_name` | TEXT NOT NULL DEFAULT '' | Free text. NetSuite-aligned naming when possible but not enforced. |
| `description` | TEXT NOT NULL DEFAULT '' | What the order is for. |
| `total_amount` | NUMERIC(18,2) NOT NULL DEFAULT 0 | Excl. VAT. |
| `status` | TEXT NOT NULL DEFAULT 'Draft' | One of: `Draft`, `Submitted`, `Approved`, `Issued for PO`, `Cancelled`. |
| `request_date` | DATE NOT NULL | Defaults to today on create. |
| `originator` | TEXT NOT NULL DEFAULT '' | Free text. Blank by default; user fills in on create. |
| `notes` | TEXT NOT NULL DEFAULT '' | Free notes. |
| `created_at` | DATETIME NOT NULL | local time, same convention as `cost_node_audit_log` |
| `updated_at` | DATETIME NOT NULL | bumped on every edit |

### 4.2 `po_rto_links`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `po_number` | TEXT NOT NULL | The NetSuite PO number, matching `po_lines.po_number`. |
| `rto_id` | INTEGER NOT NULL | FK to `rto.id` (CASCADE on delete). |
| `source` | TEXT NOT NULL | One of `manual`, `auto_memo` (future). |
| `linked_at` | DATETIME NOT NULL | local time |
| `linked_by` | TEXT NOT NULL DEFAULT '' | originator name; placeholder until auth |
| `unique(po_number)` | | A PO is linked to at most one RTO. |

The "at most one" constraint is deliberate. If a single NetSuite PO funds two RTOs (rare), the user picks the larger one; the smaller RTO's status stays `Issued for PO` but has no link. We can revisit if it becomes a real pattern.

## 5. Routes

All under `/project/{project_number}` for tenant clarity.

| Method | Path | Purpose |
|---|---|---|
| GET | `/rtos` | List of RTOs for the project (table view). |
| GET | `/rtos/new` | Create form. |
| POST | `/rtos/new` | Submit create. Generates `{proj}.RTO.NNN` from MAX existing + 1. |
| GET | `/rtos/{rto_number}` | RTO detail page (header + linked POs + status flip buttons). |
| POST | `/rtos/{rto_number}/edit` | Update fields. |
| POST | `/rtos/{rto_number}/status` | Flip status. Form has hidden `target_status` field. |
| POST | `/rtos/{rto_number}/delete` | Delete (only when status is `Draft` or `Cancelled`). |
| GET | `/purchase-orders/{po_number}/link-suggestions` | JSON: top-5 candidate RTOs ranked. Used by the link modal. |
| POST | `/purchase-orders/{po_number}/link` | Body: `rto_id`. Creates a `po_rto_links` row, source=`manual`. Flips RTO status to `Issued for PO` if currently `Approved`. |
| POST | `/purchase-orders/{po_number}/unlink` | Removes the link. Does NOT roll back RTO status (manual flip if needed). |

Add `?filter=unassigned` to the existing `/purchase-orders` route to show only POs with no link.

## 6. Suggested-matches algorithm

When the user clicks **Link to RTO** on a PO row, the modal shows up to 5 candidate RTOs ranked by a simple confidence score 0-100.

For a PO with `(po_vendor, po_amount, po_project, po_date)`, score each open RTO (status in `Approved` or `Issued for PO`) of the same project:

| Signal | Points | Logic |
|---|---|---|
| Same project | required | Filtered upfront, not scored. |
| Vendor exact match (normalised) | +40 | Lowercase, strip punctuation, ignore leading numeric IDs. |
| Vendor fuzzy match (substring or first-3-words) | +20 | Fallback when exact fails. |
| Amount within ±2% of RTO total | +25 | Exact match | Within 2% | Within 10% — graduated. |
| Amount within ±10% | +10 | |
| Date: PO within 30 days after RTO request_date | +20 | Slides linearly: same day = +20, day 30 = +5, day 60 = 0. |
| RTO status = `Approved` | +5 | Slight bias toward already-approved over still-submitted. |

If top candidate scores ≥ 60 it renders highlighted ("Likely match"). Below 30: "Weak match — verify". User can also search/pick any RTO outside the top 5.

This algorithm lives in `costcontrol/rto.py` (new file) so it's isolated from app.py.

## 7. Status flow

```
 [Draft] ──submit──▶ [Submitted] ──approve──▶ [Approved] ──link PO──▶ [Issued for PO]
    │                    │                        │
    └────cancel──────────┴────cancel──────────────┴────cancel──▶ [Cancelled]
```

- `Draft` and `Submitted` can be cancelled or deleted.
- `Approved` and `Issued for PO` can only be cancelled (not deleted directly — must cancel first).
- `Issued for PO` is reached automatically when a PO links to an `Approved` RTO. Manual flip back to `Approved` is allowed (e.g., link was a mistake) — done via unlinking the PO.
- `Cancelled` is terminal but can be deleted to clean up the list.
- v1 has no separate approval gate: the cost controller can flip `Submitted` → `Approved` themselves. Re-evaluate when a second user joins.

## 8. UI: three new screens

### 8.1 RTO list — `GET /project/{N}/rtos`

Same shell as the Packages and Purchase Orders tabs. Columns: RTO No., Date, Vendor, Description, Package, Total, Status (chip), Linked PO, **Variance** (RTO total − linked PO total; blank if no PO linked).

Project-level tab order becomes: `Cost Work Sheet | Packages | RTOs | Purchase Orders`.

### 8.2 RTO create / detail — same template, two modes

Form fields mirror your existing Excel template header: project (locked), package (dropdown of project's packages, optional), vendor, description, request date, total amount excl VAT, originator, notes.

On detail mode: also shows current status, "Submit / Approve / Cancel" buttons appropriate to current status, and a panel listing any linked POs.

### 8.3 Link-PO modal — opened from PO row

Two columns:
- **Suggested RTOs** (top 5, ranked) — each row clickable.
- **Search any RTO** — text input filters the full RTO list for this project.

Confirm → POSTs `/purchase-orders/{po_number}/link` with `rto_id`.

## 9. PO tab changes

- Replace the static `Unassigned` cell with: linked RTO number (clickable to RTO detail) OR a small `[Link to RTO]` button.
- Add a header filter: **All POs** / **Unassigned** / **Linked**.
- Add a count badge to the tab title showing unassigned count: `Purchase Orders (18 — 12 unassigned)`.
- For each linked PO row, show a **Variance** chip: `+R 5,000` (PO over RTO, red) / `−R 2,000` (PO under RTO, green) / `R 0` (exact match, neutral). Computed as `linked_po_total − rto_total`.

## 10. Build slices (proposed order)

1. **Slice 1 — Data model.** Add the two tables via startup migration; add SQLModel classes; no UI yet. *Verifiable: tables exist after restart.*
2. **Slice 2 — RTO list + create + detail.** Routes, templates, status flip buttons. Linking still says "Unassigned" everywhere. *Verifiable: can create an RTO, walk it through statuses.*
3. **Slice 3 — Link modal + suggested matches.** Algorithm, JSON endpoint, modal UI. *Verifiable: pick a PO, get 5 suggestions, link one, see it appear on the RTO detail.*
4. **Slice 4 — PO tab filter + unassigned count.** Polish. *Verifiable: filter dropdown works, count is right.*

Each slice is a separate commit. Stop after each one for visual review before continuing.

## 11. Decisions (locked, 2026-05-05)

1. **Tabs structure:** RTOs is a sibling tab next to Purchase Orders.
2. **RTO numbering:** Auto-incremented `{project_number}.RTO.NNN` zero-padded to 3 digits, generated server-side from MAX existing + 1 per project.
3. **Originator:** Blank by default — user fills in on create.
4. **Approval gate:** Single-user / unrestricted in v1. Revisit when second user joins.
5. **Auto-flip on link:** When a PO links to an `Approved` RTO, the RTO advances automatically to `Issued for PO`.
6. **PO Variance:** Shown as a chip on RTO list (column) and on each linked PO row in the PO tab. Sign-coloured: PO > RTO is red (over-spend), PO < RTO is green (under-spend), zero is neutral.
7. **Cancelled deletion:** Allowed. Approved / Issued for PO must be cancelled first, then deleted from cancelled state.
