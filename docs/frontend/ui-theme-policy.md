# UI Theme Policy & Governance

## 1. Token Governance
The `src/theme` directory is the **single source of truth** for all styling.
- **Palette**: Use semantic names (`primary.main`, `error.light`, `background.paper`).
- **Spacing**: Use the 8px multiplier (`theme.spacing(2)` = 16px).
- **Shape**: Use `theme.shape.borderRadius`.
- **Typography**: Use variants (`h6`, `subtitle1`, `body2`). Do not hardcode font sizes.
- **Components**: Tabs use standard MUI defaults (0.875rem, Medium weight) with mixed-case text.

> [!IMPORTANT]
> **Hex Value Restriction**: Raw hex values (e.g. `#ffffff`) may appear **ONLY** in `src/theme/palette.ts` (the token definitions). All other components and theme overrides must reference these colors via `theme.palette.*`.

### Allowed vs. Disallowed Patterns

| Feature | Allowed | Disallowed |
| :--- | :--- | :--- |
| **Colors** | `color="primary"`, `sx={{ color: 'text.secondary' }}` | `color="#1a1a1a"`, `color="rgb(0,0,0)"` |
| **Spacing** | `p={2}`, `m={1}` | `p="16px"`, `margin="10px"` |
| **Shadows/Elevation** | `elevation={0}` (default), `elevation={1-4}` (overlays) | `box-shadow: 0px 4px ...` (custom strings) |
| **Borders** | `border: 1px solid theme.palette.divider` | `border: 1px solid #e0e0e0` |
| **Radius** | `borderRadius: 1` (=4px), `borderRadius: 2` (=8px) | `borderRadius: "4px"` |

## 2. Palette System (Semantic Colors)
We strictly enforce a semantic palette.

- **Primary**: Brand action color.
- **Secondary**: Supporting accents.
- **Text**:
  - `text.primary`: High emphasis content (#1a1a1a)
  - `text.secondary`: Metadata, descriptions (#666666)
- **Background**:
  - `background.default`: Main page background.
  - `background.paper`: Card/Process surfaces (White).
- **Divider**: Subtle separators.

## 3. Surface Discipline

### Page vs. Card
- **Page (`background.default`)**: The canvas. Low hierarchy.
- **Card/Paper (`background.paper`)**: Contained content. Standard border radius.

### Elevation
- **0**: Standard cards on gray background (Flat).
- **1-4**: Overlays, Modals, Dropdowns, Sticky Headers.
- **Never**: Random custom shadows.

### Borders
- **Default Radius**: **4px** (`theme.shape.borderRadius = 4` or `borderRadius: 1`).
- **Elevated Surfaces (Card/Panel)**: **8px** (`borderRadius: 2`) allowed for contained content areas to distinguish from the page background.
- Avoid mixing rounded and square corners in the same context.

### Surface Specifics
### Surface Specifics
- **AppBar**: Governance is limited to **palette and elevation** (background color, shadow).
- **Utility Headers**: Use `primary.main` background with `common.white` text for data-dense/settings pages.
- **Tabs**: Use standard MUI defaults (Medium weight) with mixed-case text.
