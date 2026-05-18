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
- Package cost items tab: `Add Cost Grouping`, `Add Cost Line`, and package award actions.
- Page content should show the working table/grid first, with creation forms opened as modal pop-outs.

## Hierarchical Tables

Hierarchical project controls data must use Tabulator tree grids where practical.

- Scope uses parent Scope Items with nested Cost Components.
- Package cost items use the package-local three-level hierarchy: Cost Grouping -> Cost Item Account -> Cost Line.
- Cost Grouping and Cost Item Account rows must roll up child values so grouping, account, and grand totals can be read from the tree.
- Package Cost Groupings are not Scope Cost Components. They are BOQ-style grouping buckets inside one package cost build-up.
- Cost Grouping and Cost Item Account codes are generated numeric outline codes such as `1`, `1.1`, and `1.2`. Cost Lines keep their cost item code field and do not inherit the grouping outline number.
- Package cost line forms must start with `Related Control Account`, then filter the `Related Cost Component` list to components under that control account. The `Cost Item Account` list must then filter to accounts already created under the selected component. If no suitable account exists, the user can select `+ Add new Cost Item Account` at the bottom of the same dropdown.
- Selecting `+ Add new Cost Item Account` must open a separate pop-out for choosing from the standard library or entering a custom account. Custom accounts are project records only and must not be added back to the standard library.
- Package cost line forms must use CBS-aligned labels: `Related Control Account`, `Related Cost Component`, `Cost Item Account`, `Cost line description`, and `CBS cost item code`.
