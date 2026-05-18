# Cost Control Naming Divergence Register

This register records intentional differences between database names and user-facing labels in the Cost Control MVP.

| Database name | UI label | Reason |
|---|---|---|
| `control_accounts` | Cost Categories | Retained for ingest compatibility; users work with CBS L1 Cost Categories. |
| `project_tasks` level-2 rows | Cost Components | NetSuite mirror of the CBS L2 tier when surfaced in CBS views. Applies to both direct scope components and indirect components. |
| `project_tasks` level-3 rows | Cost Item Codes | NetSuite mirror of the CBS L3 tier when surfaced in CBS views. |
| `cost_components` | Direct Cost Components | Direct Level 2 cost components linked to scope and area metadata. |
| `indirect_l2_accounts` | Indirect Cost Components | Indirect Level 2 components under EPCM and Preliminaries. |
| `package_documents` | Documents / Issue Register | Package document and issue records, separate from Cost Components. |
| `packages.package_type` | Package category | Disambiguates from pricing basis. |
| `packages.pricing_basis` | Pricing basis | NEC4/commercial pricing form for the package. |
| `packages.planned_value` | Provisional Allocation | Package-level provisional reservation before award. |
| `packages.awarded_amount` | Awarded value | Procurement award value. |
| `packages.package_source` | Package source | Three-value source classification: External / Internal / Client. |
| `packages.is_contracted` | Award status | Boolean projected as Planned / Awarded in the UI. |
| `package_cost_items` | Cost Items / Cost Item Lines | Flat WBS line items at the Package x Cost Item Code intersection. |
| `package_cost_nodes` root group rows | Cost Groupings | Package-local grouping buckets for BOQ-style cost build-ups. These are not Scope Cost Components. Codes are generated as numeric outline values such as `1`, `2`, `3`. |
| `package_cost_nodes` child group rows | Cost Item Accounts | Package cost Level 3 account buckets such as Supply, Installation, Earthworks, or Reinforced Concrete Works. Codes are generated beneath the parent Cost Grouping, for example `1.1` or `1.2`. |
| `package_cost_nodes` item rows | Cost Lines | Detailed build-up lines assigned beneath a Cost Item Account. Cost lines are not a CBS level and do not inherit package grouping outline numbers; their code field remains the cost item code. |
| Add package Cost Line flow | Level 2 Cost Component -> Cost Item Account (CBS Level 3) -> Cost Line | Cost lines are added against a CBS Level 2 Cost Component first. The Level 3 account list is filtered to previously created Cost Item Codes for that component; new accounts can be created from the standard library or as custom project-specific accounts. |
