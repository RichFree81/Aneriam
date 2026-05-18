# Cost Control Naming Divergence Register

This register records intentional differences between database names and user-facing labels in the Cost Control MVP.

| Database name | UI label | Reason |
|---|---|---|
| `control_accounts` | Cost Categories | Retained for ingest compatibility; users work with CBS L1 Cost Categories. |
| `project_tasks` level-2 rows | Cost Components | NetSuite mirror of the CBS L2 tier when surfaced in CBS views. Applies to both direct scope components and indirect components. |
| `project_tasks` level-3 rows | Cost Item Codes | NetSuite mirror of the CBS L3 tier when surfaced in CBS views. |
| `deliverables` | Direct Cost Components | Database name retained for compatibility; UI should use Cost Component when the row is part of the three-level cost hierarchy. |
| `indirect_l2_accounts` | Indirect Cost Components | Indirect Level 2 components under EPCM and Preliminaries. |
| `package_documents` | Documents / Issue Register | Former `package_deliverables`; renamed so package documents are not confused with Cost Components. |
| `packages.package_type` | Package category | Disambiguates from pricing basis. |
| `packages.pricing_basis` | Pricing basis | NEC4/commercial pricing form for the package. |
| `packages.planned_value` | Provisional Allocation | Package-level provisional reservation before award. |
| `packages.awarded_amount` | Awarded value | Procurement award value. |
| `packages.package_source` | Package source | Three-value source classification: External / Internal / Client. |
| `packages.is_contracted` | Award status | Boolean projected as Planned / Awarded in the UI. |
| `package_cost_items` | Cost Items / Cost Item Lines | Flat WBS line items at the Package x Cost Item Code intersection. |
| `package_cost_nodes` root group rows | Cost Components | Package cost Level 2. Examples include direct components such as foundations and indirect components such as construction management. |
| `package_cost_nodes` child group rows | Cost Item Accounts | Package cost Level 3 account buckets such as Supply, Installation, Earthworks, or Reinforced Concrete Works. |
| `package_cost_nodes` item rows | Cost Lines | Detailed build-up lines assigned beneath a Cost Item Account. Cost lines are not a CBS level. |
