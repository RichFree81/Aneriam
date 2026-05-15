# Cost Control UI Standards

## Summary Cards

Summary cards must use the shared `.summary-card` styling from `base.html`.

- Primary package or project identifiers use `summary-card sc-main`.
- Secondary financial/status rollups use `summary-card fy`.
- Do not create one-off card shading in page templates.
- When a page has grouped cards, keep the visual hierarchy consistent: primary cards first, secondary rollups second, and any lower-priority operational metrics third using the same shared classes unless a new shared class is deliberately added.

## Header Actions

Page-specific creation actions belong in the header three-dot actions menu, not as permanent forms in the page content area.

- WBS package list: `Add Package`.
- Package cost items tab: `Add Group`, `Add Cost Item`, and package award actions.
- Page content should show the working table/grid first, with creation forms opened as modal pop-outs.

## Hierarchical Tables

Hierarchical project controls data must use Tabulator tree grids where practical.

- Scope uses parent Scope Items with nested Deliverables.
- Package cost items use cost groups with nested cost items.
- Group rows must roll up child values so section, subsection, and grand totals can be read from the tree.
