# Page-Level Spacing Rules Specification

**Version:** 1.1.1
**Context:** Material UI (MUI) / Toolpad Core System
**Scope:** Page Content Layout (Governance Standard)

## 1. Governance Hierarchy

To resolve potential conflicts between layout documents, the following hierarchy applies:

1.  **This Specification (Page-Level Spacing Rules):**
    *   Defines the **Spacing Scale** (8px invariant).
    *   Defines the **Spacing Tokens** (e.g., 2x, 3x).
    *   Defines the **Structural Invariants** (Header→Content relationship).
    *   Defines the **Allowable Contexts** (Standard vs. Settings/Utility).
    *   *Authority:* No other document may introduce new tokens or redefine the base scale.

2.  **Page Layout Standard:**
    *   Defines **how** these tokens are applied to specific Toolpad page structures.
    *   Defines the component hierarchy (HeaderBlock / ContentBlock).
    *   *Constraint:* The Layout Standard may bind specific tokens to patterns (e.g., "Settings pages use 2x"), but it must not introduce arbitrary values (e.g., "2.5x") or override the invariants defined here.

## 2. MUI & Toolpad Compatibility Assurance

This specification is designed to operate strictly within the **MUI System** and **Toolpad Core** compatibility layer.

*   **No Internal Overrides:** This standard does not require modifying internal MUI component padding or default behaviors unless explicitly governed by the theme.
*   **No Custom Engines:** Implementation must rely solely on standard MUI layout utilities (`Stack`, `Box`, `Container`, `Grid`) and the Theme Spacing Scale.
*   **Dashboard Integration:** All rules are validated for use within the standard `DashboardLayout` frame.

## 3. Spacing Scale & Hierarchy

### 3.1 The 8px Invariant
The application enforces a strict **8px base unit**. All layout values must be multiples of this base.

| Token | Abs. Value | Structural Role |
| :--- | :--- | :--- |
| **0.5x** | 4px | **Micro-Spacing:** Icon-to-text, tight label grouping. |
| **1x** | 8px | **Component Internal:** Standard gap between inputs, button groups. |
| **2x** | 16px | **Primary Layout (Dense):** Standard separation for utility/settings pages. |
| **3x** | 24px | **Primary Layout (Standard):** Standard page gutter and section separation. |
| **4x** | 32px | **Major Separation:** Landing page sections (rare). |
| **6x** | 48px | **Flow Break:** Authentication screens, error pages. |

### 3.2 Token Authority
*   **Permitted Values:** Only tokens defined in the table above satisfy compliance.
*   **Prohibition:** No additional fractional values (e.g., `1.5x`, `2.5x`) or arbitrary pixel values may be introduced unless formally added to this specification via a governance revision.

### 3.3 Hierarchical Spacing Principle
Spacing must correlate with structural hierarchy to communicate logical relationships.
*   **Larger Tokens = Higher Separation:** Major section breaks must use larger tokens than internal component gaps.
*   **Consistent Semantics:** A `3x` gap always implies a Section Break. A `2x` gap always implies Related Content.
*   **No Arbitrary Escalation:** Spacing tokens may not be increased solely to "fix visual discomfort"; underlying structural nesting must be addressed instead.

## 4. Page Layout Policy

### 4.1 Unification of Vertical Rhythm (The Structural Invariant)
The vertical distance between the **HeaderBlock** (Page Header/Tabs) and the **ContentBlock** (First Content Element) is a strict structural invariant.

*   **Boundary Definition:** The invariant applies at the structural boundary between the HeaderBlock implementation and the ContentBlock implementation.
*   **Control Mechanism:** This spacing must be controlled by the **Parent Wrapper** (PageContainer padding or ContentBlock top-padding).
*   **Prohibition:** Child components (e.g., Cards, Grids, Typography) must **never** use `margin-top` to create, adjust, or "fix" this primary structural gap.

### 4.2 Global Standard vs. Dense Context
The system recognizes two distinct spacing contexts based on page utility.

| Context | Allowable Top Padding | Usage |
| :--- | :--- | :--- |
| **Standard Page** | **3x Unit** (24px) | Default for Dashboards, Reports, and General Views. |
| **Settings / Utility** | **2x Unit** (16px) | Restricted to Settings Modules, Data-Dense Configurations, and Utility screens. |

> **Note:** The padding token applies to the **ContentBlock** only (the `p` prop on the content `Box`). The **HeaderBlock** governs its own vertical padding separately — specifically `pt: 2, pb: 0` (when tabs are present) or `pt: 2, pb: 2` (no tabs). These header padding values are not governed by the Standard/Utility token and must not be changed to match the content token.

## 5. Header Variants (Governance)

To ensure consistency in density, specific header patterns are standardized.

### Type A: Scope Header (No Navigation)
Used for module roots, selection screens, or simple utility pages.
*   **Visual Style:** Distinct background surface (e.g., `primary.main` or `grey.100`).
*   **Vertical Padding:** Balanced 2x (16px) top and bottom.
*   **Content Relationship:** Must correspond to the **Settings / Utility** context (2x content padding).
*   **Typography:** Uses the standardized dense heading variant (h6).

### Type B: Context Header (With Navigation)
Used for complex configuration pages requiring sub-navigation tabs.
*   **Visual Style:** Distinct background surface.
*   **Navigation Alignment:** Tabs are anchored to the bottom of the header block.
*   **Tab Styling:** Must use the **Dense Tab Variant** (reduced font scale, natural case text) defined in the Theme.
*   **Content Relationship:** Must correspond to the **Settings / Utility** context (2x content padding).

## 6. Layout Mechanics & Implementation Policy

### 6.1 Container-First Spacing
Spacing is a property of the **Container**, not the Component.
*   **Padding:** Use container-level padding props to define internal breathing room.
*   **Stacks:** Use Stack components to define equidistant spacing between children.

### 6.2 Margin Policy
*   **Structural Prohibition:** Margins must **never** be used to define the primary Page Start line.
*   **Content Rhythm:** Negative margins are strictly prohibited for vertical rhythm manipulation (e.g., pulling content up).
*   **Horizontal Gutters:** Controlled negative horizontal gutters are permitted **only** when governed by a layout context (e.g., full-bleed dividers inside a padded container).
    *   *Constraint:* These negative values must exactly equal a defined spacing token (e.g., `mx: -3`).
*   **Flow Direction:** If used, functional margins must strictly follow a "Push Down" flow (`margin-bottom`). `margin-top` is restricted to non-structural, isolated adjustments only.

### 6.3 Component Configuration
Specific component density settings (e.g., DataGrid density, Table padding modes) are excluded from this specification.
> *Refer to the **Component Configuration Specification** for density governance.*

## 7. Anti-Patterns (Compliance Violations)

The following patterns are strictly prohibited in the codebase:

1.  **Hardcoded Values:** Usage of pixel literals (e.g., `20px`) instead of Theme Spacing Tokens.
2.  **Spacer Elements:** Empty `div` or `Box` elements used solely to occupy vertical space.
3.  **Margin-Top Hacks:** Applying `margin-top` to a first-child element to "push" it away from the header.
4.  **Arbitrary Padding:** Inconsistent padding values (e.g., `2.5x`) that do not align with the defined 8px scale.
