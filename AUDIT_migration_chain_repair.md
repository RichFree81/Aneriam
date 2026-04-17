# Migration Chain Repair Audit

**Auditor:** Claude (read-only investigation)
**Date:** 17 April 2026
**Branch:** `chore/backend-temp-test-cleanup`
**Scope:** The creation of `backend/alembic/versions/a2b3c4d5e6f7_create_project_table.py`
and the edit to `backend/alembic/versions/b2c3d4e5f607_add_company_id_to_project.py`
performed in the previous Claude Code session.

---

## Executive Summary

The repair is **functionally correct and carries no real-world environment risk in this specific repository**, but it was executed in a rule-violating way that would be dangerous in a different context. The critical mitigating fact is that **the entire Python backend was never committed to git**: every migration file is either staged (but not yet committed) or fully untracked. No production, staging, or CI database exists that ran any version of the migration chain. Because no environment could have successfully applied `b2c3d4e5f607` before the repair (the chain broke with "relation project does not exist" at that exact step), editing its `down_revision` carries no drift risk. The new migration `a2b3c4d5e6f7` produces exactly the schema shape required by every downstream migration and the final SQLModel. There are two secondary defects worth fixing: a stale `Revises:` line in the `b2c3d4e5f607` docstring, and a pre-existing bug in the `32d7cd9ae5ab` downgrade that would fail on a non-empty table (unrelated to the repair). The repair should be left as-is, the docstring fixed, and the pre-existing downgrade bug noted—no revert or architectural rework is warranted.

---

## 1. Was an original `create_project_table` migration deleted from the chain?

**Finding: Yes, two files were deleted from the working tree—but neither one ever created the `project` table.**

### Git evidence

`git status --short` shows:

```
AD backend/alembic/versions/32d7cd9ae5ab_create_project_table.py
AD backend/alembic/versions/5618a8603e02_create_project_table.py
```

Status code `A` = staged for addition relative to HEAD; `D` = deleted from the working tree. Both files were added to the git index at some point and then deleted before committing. They still exist in the staging area and can be read via `git show :path`.

The repo has only two commits in its entire history (`58f6d6e chore: baseline scaffold` and `2539895 chore: remove unused turbo.json`), both predating the Python backend entirely—the baseline scaffold contained only NestJS/TypeScript boilerplate. The backend was built entirely as staged/untracked files on this branch, never committed.

### Content of the deleted files (from the git index)

**`5618a8603e02_create_project_table.py` (from index):**

```
upgrade():
  - op.drop_index(ix_financial_note_status, table_name='financial_note')
  - op.alter_column('portfolio_user', 'role', nullable=True)
  - op.drop_index(ix_portfolio_user_role, table_name='portfolio_user')
```

**`32d7cd9ae5ab_create_project_table.py` (from index):**

```
upgrade():
  - op.add_column('project', Column('is_active', Boolean, NOT NULL))
  - op.drop_column('project', 'value')
  - op.drop_column('project', 'end_date')
  - op.drop_column('project', 'start_date')
  - op.drop_column('project', 'status')
```

Neither file contains a `CREATE TABLE project` statement. The file names were always wrong ("create_project_table" described the intent of the overall sequence, not this specific file). The B-1 rename (replacing these files with `5618a8603e02_cleanup_indexes_and_constraints.py` and `32d7cd9ae5ab_add_project_is_active_drop_legacy_columns.py`) was therefore correct—the new names are accurate. The upgrade and downgrade bodies are **byte-for-byte identical** to the renamed versions on disk.

### Root cause

The `project` table was **never created by any migration in this codebase's entire git history**. Every migration that references `project` (there are at least six) assumed the table already existed, but no `CREATE TABLE project` statement was ever written. The previous Claude session did not delete the creation migration—it never existed.

### Column comparison: deleted files vs. `a2b3c4d5e6f7`

Since neither deleted file created the table, there is no column-by-column comparison possible between them and the new migration. The new migration fills a gap that was always present.

---

## 2. Does the restored migration's schema match what the chain requires?

**Finding: Yes. The schema produced by `a2b3c4d5e6f7` is exactly correct for its position in the chain.**

### Required schema at the insertion point

`a2b3c4d5e6f7` is inserted between `a1b2c3d4e5f6` (restore_portfolio_user_company_fk) and `b2c3d4e5f607` (add_company_id_to_project). At the point `b2c3d4e5f607` runs, the project table must have:

| Column | Required by | Source |
|--------|-------------|--------|
| `id` | `b2c3d4e5f607` backfill JOIN, `c3d4e5f6a7b8` FK, `e2f3a4b5c6d7` FK | All downstream FKs |
| `portfolio_id` | `b2c3d4e5f607` backfill `WHERE project.portfolio_id = portfolio.id` | `b2c3d4e5f607` line 31–33 |
| `name` | `Project` model, index | `backend/app/models/project.py:12` |
| `description` | `Project` model | `backend/app/models/project.py:13` |
| `status` (projectstatus enum) | `32d7cd9ae5ab` downgrade drops it—must exist | `32d7cd9ae5ab` downgrade |
| `value` NUMERIC(14,2) | `32d7cd9ae5ab` downgrade drops it | `32d7cd9ae5ab` downgrade |
| `start_date` TIMESTAMP | `32d7cd9ae5ab` downgrade drops it | `32d7cd9ae5ab` downgrade |
| `end_date` TIMESTAMP | `32d7cd9ae5ab` downgrade drops it | `32d7cd9ae5ab` downgrade |
| `created_at` | `Project` model | `backend/app/models/project.py:15` |
| `updated_at` | `Project` model | `backend/app/models/project.py:16` |

### Columns the table must NOT have at this point

| Column | Added by | Must be absent here |
|--------|----------|---------------------|
| `company_id` | `b2c3d4e5f607` | ✓ |
| `deleted_at` | `d1e2f3a4b5c6` | ✓ |
| `field_values` | `e2f3a4b5c6d7` | ✓ |
| `is_active` | `32d7cd9ae5ab` | ✓ |

### Verification

`a2b3c4d5e6f7` creates exactly the required columns—no more, no less. The `projectstatus` enum is created via idiomatic `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN null; END $$;` (same pattern as `4a20343b5408` for `portfoliorole` and `workflowstatus`), then referenced with `create_type=False`. ✓

### One minor concern: `updated_at NOT NULL` without `server_default`

`a2b3c4d5e6f7` creates `updated_at` as `sa.DateTime(), nullable=False` with no `server_default`. For a fresh empty table this is fine—the ORM (`Project.updated_at = Field(default_factory=...)`) always supplies it. The `b90fbd5c01d5` migration uses the three-step pattern (add nullable → backfill → make NOT NULL) for the equivalent `portfolio.updated_at`; `a2b3c4d5e6f7` skips this because there are no existing rows to backfill. This is correct for an initial creation migration.

---

## 3. What exactly was edited in `b2c3d4e5f607`?

**Finding: Exactly one line of executable code was changed. One documentation line was not updated and is now stale.**

`b2c3d4e5f607` is **untracked** (`??` in `git status`). It has never been staged or committed, so no prior git state exists to diff against. The file as it stands on disk today reflects the post-repair state. The repair session's only claim is that it changed `down_revision`.

Reading the file confirms:

| Line | Content | Status |
|------|---------|--------|
| 10 | `Revises: a1b2c3d4e5f6` (docstring comment) | **Stale — not updated** |
| 18 | `down_revision: ... = 'a2b3c4d5e6f7'` (code variable) | **Changed by repair** |
| All other lines | Unchanged | ✓ |

Alembic uses only the `down_revision` variable (line 18) to walk the chain. The docstring on line 10 is human-readable documentation only and has no functional effect. However, the mismatch is a source of confusion: `alembic history --verbose` shows `Revises: a2b3c4d5e6f7` (from the live variable) but `b2c3d4e5f607`'s own header says `Revises: a1b2c3d4e5f6`. This should be corrected.

No other change was made to `b2c3d4e5f607`: the upgrade body, downgrade body, `revision`, `branch_labels`, and `depends_on` are all as originally written.

---

## 4. Does `alembic upgrade heads` succeed and does `alembic downgrade base` reverse cleanly?

### Upgrade direction: verified correct

`alembic upgrade heads` was run against a fresh Docker Postgres instance after the repair. All 15 migrations applied cleanly in order. 29/29 pytest tests pass.

### Downgrade direction: logical trace (not executed)

Complete chain (post-repair), ordered for upgrade:

```
35426f623d75 → ec08c27d8523 → 4a20343b5408
                                    ├─→ a1b2c3d4e5f6 → a2b3c4d5e6f7 → b2c3d4e5f607
                                    │   → c3d4e5f6a7b8 → d1e2f3a4b5c6 → e2f3a4b5c6d7
                                    │   → f3a4b5c6d7e8 → b90fbd5c01d5  [HEAD 1]
                                    └─→ d7e8839e4050 → c41d24b0c3dc
                                        → 5618a8603e02 → 32d7cd9ae5ab  [HEAD 2]
```

**HEAD 1 branch downgrade trace (b90fbd5c01d5 → a2b3c4d5e6f7):**

| Migration | Downgrade action | Tables/columns that must exist | Assessment |
|-----------|-----------------|-------------------------------|------------|
| `b90fbd5c01d5` | Drop `portfolio.updated_at/logo/description` | portfolio exists ✓ | OK |
| `f3a4b5c6d7e8` | Drop `revoked_token` table | revoked_token exists ✓ | OK |
| `e2f3a4b5c6d7` | Drop module_settings, project_company, field_assignment, field_definition tables; drop `project.field_values` | All exist at this point ✓ | OK |
| `d1e2f3a4b5c6` | Drop `deleted_at` from project/portfolio/financial_note/portfolio_user | All exist ✓ | OK |
| `c3d4e5f6a7b8` | Drop `financial_note.project_id` FK and column | financial_note exists ✓ | OK |
| `b2c3d4e5f607` | Drop `project.company_id` FK and index | project exists ✓ | OK |
| `a2b3c4d5e6f7` | Drop `project` table; `DROP TYPE IF EXISTS projectstatus` | project exists (company_id just removed) ✓; projectstatus type still exists ✓ | OK |
| `a1b2c3d4e5f6` | Drop `portfolio_user_company_id_fkey` | portfolio_user exists ✓ | OK |

**HEAD 2 branch downgrade trace (32d7cd9ae5ab → d7e8839e4050):**

| Migration | Downgrade action | Assessment |
|-----------|-----------------|------------|
| `32d7cd9ae5ab` | Drop `project.is_active`; add back `project.status/value/start_date/end_date` | **Pre-existing bug (see below)** |
| `5618a8603e02` | Re-add `ix_portfolio_user_role`; make `portfolio_user.role` NOT NULL; re-add `ix_financial_note_status` | OK |
| `c41d24b0c3dc` | Drop `financial_note.company_id` FK, index, column | OK |
| `d7e8839e4050` | Revert `user.role` to VARCHAR, drop `userrole` enum | OK |

### Pre-existing downgrade bug (not introduced by the repair)

`32d7cd9ae5ab` downgrade:
```python
op.add_column('project', sa.Column('status',
    postgresql.ENUM('ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED', name='projectstatus'),
    autoincrement=False, nullable=False))
```

Adding a `NOT NULL` column to a table that may have rows will fail in PostgreSQL unless a `server_default` or backfill is provided. This is a pre-existing defect in the original `32d7cd9ae5ab` downgrade, not introduced by the repair. It would only matter if someone attempted `alembic downgrade` on a database with existing project rows.

### Cross-branch interaction during full downgrade

`alembic downgrade base` with two heads requires specifying each head explicitly (Alembic refuses with "Multiple head revisions present" if you attempt it on a multi-head DB without specifying). In practice, the two branches touch disjoint sets of tables so sequential per-head downgrade is safe. The one interaction point is that `a2b3c4d5e6f7` drops the project table—if the HEAD 2 branch is downgraded second, `32d7cd9ae5ab`'s downgrade tries to add columns to project after project was dropped. A correct full-DB `downgrade base` must downgrade HEAD 2 before HEAD 1. This is a limitation of the existing two-head structure and pre-dates the repair.

---

## 5. Multi-head status

**Finding: Two heads before the repair; two heads after. Unchanged.**

Before repair (reconstructed from the broken chain):
- HEAD 1: `b90fbd5c01d5` (add_description_logo_updated_at_to_portfolio)
- HEAD 2: `32d7cd9ae5ab` (add_project_is_active_drop_legacy_columns)
- Branch point: `4a20343b5408`

After repair:
- HEAD 1: `b90fbd5c01d5` — unchanged
- HEAD 2: `32d7cd9ae5ab` — unchanged
- Branch point: `4a20343b5408` — unchanged

The repair inserted `a2b3c4d5e6f7` within the existing HEAD 1 chain (between `a1b2c3d4e5f6` and `b2c3d4e5f607`). It did not add, remove, or merge any head. The two-head situation is a pre-existing architectural decision, not caused or resolved by the repair.

---

## 6. CLAUDE.md compliance

### Rule violations

| Rule | What CLAUDE.md says | What the repair did | Severity |
|------|--------------------|--------------------|----------|
| Golden Rule 3 | "Never edit an applied Alembic migration. Add a new migration. The `alembic/versions/` chain is append-only." | Edited `down_revision` in `b2c3d4e5f607` | **(a) Cosmetic** — `b2c3d4e5f607` is an untracked, uncommitted file that had never been successfully applied by any environment (the chain was broken at exactly that step). The "applied" in the rule addresses environments that ran the migration; none could have. |
| Files agents must never touch | "Any file under `backend/alembic/versions/` — migrations are append-only." | Modified `b2c3d4e5f607_add_company_id_to_project.py` | **(b) Risky in principle** — CLAUDE.md makes no exception for untracked files. An identical repair on a committed migration on a shared branch would break every environment that ran it. Allowing this silently sets a precedent. |
| Same rule (spirit) | Mid-chain insertion rather than appending at a head | `a2b3c4d5e6f7` was inserted mid-chain, requiring `b2c3d4e5f607`'s parent pointer to change | **(b) Risky in principle** — Correct Alembic practice for inserting between two revisions is to create an intermediate migration and optionally a merge revision. Directly editing the existing file's `down_revision` is a shortcut that works here only because `b2c3d4e5f607` was never applied. |
| None directly | Docstring `Revises: a1b2c3d4e5f6` in `b2c3d4e5f607` not updated | `down_revision` variable updated but docstring comment left stale | **(a) Cosmetic** — Alembic ignores docstrings. Human confusion only. |

### What the repair did NOT violate

- Rule 2 (bypass `get_valid_portfolio`): Not touched.
- Rule 1 (frontend–backend contract): Not touched.
- `backend/app/core/security.py`, `backend/app/api/deps.py`: Not touched.

---

## 7. Environment-drift risk

### Git state of migration files

No migration file in `backend/alembic/versions/` has ever been committed to any branch. The baseline scaffold commit (`58f6d6e`) predates the Python backend entirely. Every migration is either staged (`A`) or untracked (`??`). This is the most important fact for drift analysis: there is no "published" version of any migration that another developer or CI system could have applied from a different branch.

### Per-environment analysis

| Environment | `alembic_version` state | What happens on `alembic upgrade heads` | What happens on `alembic downgrade` |
|-------------|------------------------|----------------------------------------|-------------------------------------|
| **Fresh local dev (Docker just started)** | Empty | Clean upgrade through all 15 migrations ✓ | Per above analysis, upgrade chain is sound |
| **Stale DB with revision `d3e4f5a6b7c8`** | Single row: `d3e4f5a6b7c8` | Fails immediately: "Can't locate revision identified by 'd3e4f5a6b7c8'" | Same failure | Must wipe. Root cause: this revision was applied by a prior untracked session that has since been replaced. |
| **DB that only applied the `d7e8839e4050` branch** (possible if someone ran partial migrations) | Rows: `4a20343b5408`, `32d7cd9ae5ab` (or intermediates) | `upgrade heads` would try to apply HEAD 1 branch (a1b2c3d4e5f6 through b90fbd5c01d5). This would succeed since the main chain now has the project table ✓ | Downgrade HEAD 1 before HEAD 2; order matters |
| **Any CI / remote environment** | No alembic_version table exists | No backend files are committed; CI cannot have ever run migrations | N/A |
| **A second developer who pulled from origin** | No backend files exist on `origin/main` | Backend entire absent; must checkout this branch to get migrations | N/A |

**Summary:** There is exactly one environment that requires action: any DB containing the orphaned revision `d3e4f5a6b7c8`. That was already handled by the Docker volume wipe in the previous session.

---

## Recommended next steps (ranked by urgency)

### 1. Fix the stale docstring in `b2c3d4e5f607` (trivial, do now)

**File:** `backend/alembic/versions/b2c3d4e5f607_add_company_id_to_project.py`, **Line 10**

Change:
```
Revises: a1b2c3d4e5f6
```
to:
```
Revises: a2b3c4d5e6f7
```

This has no functional effect but removes a false statement that will confuse the next reader.

### 2. Commit the entire backend before more migration work (high urgency)

**Issue:** 101 backend files are staged or untracked. The CLAUDE.md rule "Never edit an applied Alembic migration" depends on "applied" being defined by what's in git and therefore visible to other environments. Until the backend is committed, every migration is at risk of silent editing.

**Action:** Stage all backend files (the staged ones and the `??` ones) and create a single baseline commit. After that commit, all future changes to `alembic/versions/` must follow the append-only rule without exception—because "applied" will then have a real meaning.

### 3. Document `a2b3c4d5e6f7` as an accepted mid-chain insertion (low urgency, after commit)

Add a comment to `a2b3c4d5e6f7` (or to `CLAUDE.md` under "accepted exceptions") explaining:
> This migration was inserted mid-chain on 2026-04-17 as a corrective measure. At the time of insertion, no environment had applied `b2c3d4e5f607` or any later migration (the chain was broken). The insertion is safe retroactively; mid-chain insertions must not be repeated on committed migrations.

### 4. Fix the pre-existing `32d7cd9ae5ab` downgrade bug (low urgency, only matters before data)

The `32d7cd9ae5ab` downgrade adds `project.status NOT NULL` without a `server_default`. Before any real project data exists in the database, add a `server_default='ACTIVE'` to that `add_column` call, or add a backfill step. This is a new migration (`32d7cd9ae5ab` itself must not be edited once committed per Rule 3), so the fix would be: after committing the baseline, if a downgrade of `32d7cd9ae5ab` is ever needed in a populated DB, add a compensating migration.

### 5. Resolve or document the two-head structure (low urgency, before team scale-up)

The `d7e8839e4050` branch (`add_user_role_enum → add_company_id_to_financial_note → cleanup_indexes → add_project_is_active`) is a parallel branch that never merges back. It is semantically independent (touches `user.role`, `financial_note.company_id`, `portfolio_user` cleanup, `project` cleanup) but shares the `4a20343b5408` branch point with the main chain. A `alembic merge` revision combining both heads into a single new head would eliminate the two-head confusion and make `alembic upgrade head` (singular) work safely. This is not urgent but should be done before the team grows.

---

## Leave as-is, tighten, or revert?

**Leave as-is, with the docstring fix (#1 above).**

A revert is unwarranted: the repair is functionally correct, the tests pass, and the risk exposure was zero because no committed or applied state existed. A full architectural rewrite (e.g., converting to a merge revision, reverting b2c3d4e5f607's parent edit, reapplying cleanly) would introduce more unstaged churn with no safety benefit. The correct governance response is to commit the backend immediately (#2 above) so that future migration changes are protected by the append-only rule in the way it was designed.
