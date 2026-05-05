# Procurement Spec — Cost Control MVP

**Status:** Implemented (Slices A–F, commits `889df1c` → `ecd2557`).
**Supersedes:** the original RTO-only project-level spec — now obsolete.
**Date:** 2026-05-05.
**Scope:** the procurement workflow inside `app/` only.

## 1. Goal

Let the cost controller manage each external package's full procurement lifecycle inside the Cost Control app — from tender issue through adjudication, award, RTO, original PO, and variations — and surface the resulting variance against the awarded contract value.

## 2. The two-package model

Every Package has an `is_external` boolean. Defaulted from `package_type` at seed time:

| Package type | Default `is_external` |
|---|---|
| Construction Package Labour & Materials | `True` |
| Engineering Construction Package | `True` |
| Supply Package | `True` |
| Design Package | `False` |
| Services Package | `False` |

Internal packages have only the **Cost Buildup** tab — the entire procurement workflow is hidden from the UI for them. External packages also expose a **Procurement** tab with four sub-tabs.

## 3. Lifecycle stages — single source of truth

The canonical lifecycle is defined by every Schedule Estimation Standard (Construction, Design, Services, Supply — all use the same four stages):

```
Definition → Procurement → Execution → Close-out
```

These four (plus the modifier states `On Hold` and `Cancelled`) are what `Package.package_stage` carries. A separate `procurement_stage` field used to exist; it duplicated the same lifecycle and was deprecated 2026-05-05. The column remains in the schema for back-compat but the app no longer reads or writes it.

Sub-states inside the Procurement stage (Tender Draft / Issued / Closed / Adjudicating / Awarded / Cancelled) live on the **Tender record** (`tender.status`) — that's the right place because Tender is the entity going through those sub-states, not the Package.

External package activities map onto the four stages like this:

| Stage | Activity | Relevant records |
|---|---|---|
| Definition | Scope writing, technical basis | Package.scope_summary, Workstreams |
| **Procurement** | Tender → Adjudication → Award | Tender + Bidder + EvaluationCriterion + BidEvaluation |
| Execution | RTO + Original PO + Variations | RTO + PORtoLink (`is_original` flag) |
| Close-out | Punch list, final account | (manual) |

**Auto-transitions:**
- Issuing a tender on a Definition-stage package automatically advances `package_stage` to **Procurement**.
- Marking a bidder as Awarded automatically advances `package_stage` from Procurement to **Execution**.
- No automatic move into Close-out; the user advances manually.

Internal packages share the same four stages but skip the procurement-related child records — no Tender, no RTO. They walk Definition → Procurement (representing internal resource allocation) → Execution → Close-out.

## 4. Data model

### Package — fields added in Slice A

| Column | Type | Notes |
|---|---|---|
| `is_external` | BOOLEAN NOT NULL DEFAULT 0 | Defaulted by package_type at seed time. |
| `awarded_vendor_name` | TEXT NULL | Set on award. |
| `awarded_amount` | NUMERIC(18,2) NULL | Set on award. |
| `awarded_date` | DATE NULL | Set to today() on award. |
| `procurement_stage` | TEXT NOT NULL DEFAULT 'Pre-Tender' | **DEPRECATED 2026-05-05** — superseded by `package_stage`. Column kept for back-compat; no longer read or written. |

### Tender (Slice C)

One per external package. `tender_number = {package}.TND.NNN`. Status: Draft / Issued / Closed / Adjudicating / Awarded / Cancelled. Holds bidders + adjudication notes.

### Bidder (Slice C)

Many per Tender. Status: Pending / Submitted / Withdrawn / Disqualified / Shortlisted / Awarded.

### BidDocument (Slice C)

Many per Bidder. Stores `document_name + document_ref` only — no binary upload. The user pastes a URL or network path.

### EvaluationCriterion (Slice D)

Per Tender. `criterion_name + weight (NUMERIC 5,2)`. Weights ought to sum to 100 across criteria — soft warning in the UI, not a DB invariant.

### BidEvaluation (Slice D)

Per (Bidder, Criterion). UNIQUE constraint enforces one row per cell. Score 0–100 plus optional evaluator + notes. Empty score → row deleted (so it doesn't drag the weighted total).

### RTO (Slice B)

One per external package. `rto_number = {package}.RTO.NNN`. Status: Draft / Submitted / Approved / Issued for PO / Cancelled. Always tied to a package via `package_number` (NOT NULL at the model layer).

### PORtoLink (Slice E)

Links a NetSuite PO to an RTO. UNIQUE on `po_number` (one PO ↔ one RTO). Carries `is_original BOOLEAN NOT NULL DEFAULT 0`. **First link to a given RTO** is auto-flagged `is_original=1`; **subsequent links are variations** (`is_original=0`).

## 5. Routing map

All under `/project/{N}/packages/{M}/...`:

| Path | Purpose |
|---|---|
| `/cost` | Cost Buildup tab (existing) |
| `/tender` | Tender sub-tab |
| `/tender/issue` POST | Create tender |
| `/tender/edit` POST | Edit tender header |
| `/tender/status` POST | Flip tender status |
| `/tender/delete` POST | Delete (Draft/Cancelled only) |
| `/tender/bidders/add` POST | Add bidder |
| `/tender/bidders/{id}/edit` POST | Edit bidder |
| `/tender/bidders/{id}/delete` POST | Delete bidder |
| `/tender/bidders/{id}/documents/add` POST | Attach doc ref |
| `/tender/documents/{id}/delete` POST | Remove doc ref |
| `/adjudication` | Adjudication scoring matrix |
| `/adjudication/criteria/add` POST | Add criterion |
| `/adjudication/criteria/{id}/edit` POST | Edit criterion |
| `/adjudication/criteria/{id}/delete` POST | Delete criterion (CASCADE on scores) |
| `/adjudication/score` POST | Bulk save scores |
| `/adjudication/bidders/{id}/status` POST | Flip bidder status (Awarded → triggers package award flow) |
| `/award` GET | Award summary + variance roll-up |
| `/rto` GET | Orders sub-tab — RTO detail or "Create RTO" CTA |
| `/rto/new` GET, POST | Create RTO |
| `/rto/edit-form` GET, `/rto/edit` POST | Edit RTO |
| `/rto/status` POST | Flip RTO status |
| `/rto/delete` POST | Delete RTO |

Project-scoped:
- `GET /project/{N}/rtos` → 301 redirect to `/packages` (legacy bookmarks).
- `GET /project/{N}/purchase-orders` → flat register of all POs with Original/Variation chip per linked row.
- `POST /project/{N}/purchase-orders/{po}/link` → links to RTO; auto-flags is_original based on chronology.
- `POST /project/{N}/purchase-orders/{po}/unlink` → unlinks; if last PO on an Issued-for-PO RTO, RTO auto-flips back to Approved.

## 6. Award flow side-effects

When `package_bidder_status` is called with `target_status='Awarded'`, the helper `_award_package_to_bidder(db, pkg, tender, bidder)` runs:

1. Demote any previously-awarded bidder on the same tender to `Shortlisted`.
2. Set the chosen bidder's status to `Awarded`.
3. Set Tender status to `Awarded`.
4. Copy `bidder.vendor_name`, `bidder.bid_amount`, `today()` onto Package's `awarded_vendor_name`, `awarded_amount`, `awarded_date`.
5. Set `Package.is_contracted = True` (freezes the pre-award column on cost nodes).
6. Advance `Package.package_stage = 'Execution'` (per the four-stage lifecycle, awarding ends Procurement and starts Execution).

Re-awarding is supported — the helper just demotes whichever bidder was previously Awarded and re-runs the same side-effects with the new winner.

## 7. Variance roll-up

On the Award page (`/award`), a SQL aggregate joins `rto → po_rto_links → po_lines` and groups by `is_original` to produce four numbers:

| KPI | Calculation |
|---|---|
| Original PO | `SUM(amount WHERE is_original=1)` |
| Variations | `SUM(amount WHERE is_original=0)` |
| Total Committed | `SUM(amount)` |
| Variance vs Award | `Total Committed − Package.awarded_amount` |

Variance is sign-coloured: positive (over-spend) red, negative (under-spend) green, zero neutral, none-yet em-dash.

## 8. Helpers

- `costcontrol.seed.default_is_external(package_type)` — returns boolean per the table in §2.
- `costcontrol.rto.next_rto_number(db, package_number)` — `{package}.RTO.NNN`, suffix incremented per package.
- `costcontrol.rto.score_match(po, rto)` — 0–100 confidence score for the link-suggestion modal (vendor + amount + date + status weights).
- `costcontrol.rto.suggest_matches(db, project_number, po)` — top-5 ranked + full linkable list for the modal.
- `costcontrol.tender.next_tender_number(db, package_number, package_id)` — `{package}.TND.NNN`.
- `costcontrol.tender.weighted_score(scores, weights)` — `Σ(score×weight) / Σ(weight)`. Cells with no score are excluded from BOTH numerator and denominator.

## 9. What's deliberately NOT in scope

- **Multi-evaluator scoring.** One row per (bidder, criterion); evaluator is a free-text field. Supporting independent scores from multiple evaluators with averaging would need a `(bidder, criterion, evaluator_id)` triple key.
- **Binary document upload.** `document_ref` is a URL/network-path string. Files live on the network share; the app just records pointers.
- **Multi-level approval gating.** Single-user app; any user can flip Submitted → Approved on either RTO or Tender.
- **PDF generation matching the original Excel RTO template.** The app shows the same data structure but doesn't render a faithful PDF.
- **Re-tender numbering UI.** The model supports `{package}.TND.002+` and `{package}.RTO.002+`, but there's no UI yet to issue a second tender or RTO on the same package.
- **Auto-match of POs to RTOs by memo regex.** Suggestions modal scores by vendor / amount / date / status only; the future "Option 3" would extract `{package}.RTO.NNN` from `po_lines.memo` if Procurement starts including it.

## 10. Verification per slice

Each slice was smoke-tested end-to-end before commit. The current canonical test path on `5009.PKG.101` is:

1. Issue tender → walk Issued → Closed → Adjudicating.
2. Add bidders + bid amounts.
3. Add weighted criteria + score the matrix.
4. Mark a bidder as Awarded — verify package fields update (vendor / amount / date / is_contracted / package_stage='Execution') and the tender flips to Awarded.
5. Create RTO (auto-numbered `5009.PKG.101.RTO.001`).
6. Walk RTO Submitted → Approved.
7. Link first PO → expect Original chip everywhere.
8. Link second PO → expect Variation chip.
9. Visit Award page → verify Original/Variations/Total Committed/Variance match expected math.

All current tests pass with no regressions on the home page, project page, or PO list.
