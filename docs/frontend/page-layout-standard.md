# Page Layout Standard

**Status**: Locked
**Shell**: Toolpad Core (`AppProvider` + `DashboardLayout`)
**Page Frame**: `PageContainer` from `@toolpad/core` (module pages) or `PageLayout` component (settings/utility pages)

---

## Dual Layout Strategy

The app uses two distinct page layout patterns depending on page type. Both render inside `DashboardLayout`.

### Module Pages (Projects, Portfolios, Reports, Dashboards)

Use `PageContainer` from Toolpad, either directly or via the `ModuleTabsLayout` template.

- **Background**: Toolpad gray (`background.default`)
- **Title**: h4, auto-rendered by `PageContainer` from the `title` prop
- **Tabs**: MUI `Tabs` via negative-margin pattern (`mx: -3, px: 3, mt: -1.5`)
- **Content padding**: 3x (24px) — Standard Page context per spacing spec §4.2
- **Component**: `ModuleTabsLayout` or `PageContainer` directly

> ⚠️ `PageLayout type="standard"` is **not** used for module pages. Module pages must use `PageContainer` / `ModuleTabsLayout`.

### Settings / Utility Pages (Settings, Configuration)

Use the `PageLayout` component with `type="utility"`.

- **Background**: Dark `primary.main` header, white `background.paper` content
- **Title**: h6 (dense heading variant per spacing spec Type A) — **exception to the h4 rule above**
- **Tabs**: Anchored to the bottom of the dark header block (via `PageLayout` `tabs` prop)
- **Content padding**: 2x (16px) — Settings/Utility context per spacing spec §4.2
- **Component**: `PageLayout` with `type="utility"`

> ℹ️ The h6 title on utility pages is intentional and spec-compliant (spacing spec §5, Type A header). It is not an error.

---

## Layout Hierarchy

All pages render inside Toolpad's `DashboardLayout` (AppBar + Sidebar). Page content is wrapped in `PageContainer`.

```
AppBar (Toolpad)
├── Sidebar (Toolpad)
└── PageContainer
    ├── Title (h4 via theme)
    ├── Tabs (MUI standard, if applicable)
    │   └── Divider line (full-width)
    └── Content area (white background)
```

---

## PageContainer Rules

| Rule | Setting | Rationale |
|------|---------|-----------|
| **Title** | Use `title` prop | Toolpad standard; rendered as `h4` |
| **Breadcrumbs** | Suppress on top-level pages (`breadcrumbs={[]}`) | Sidebar already provides context |
| **Width** | `maxWidth={false}` | Full-width at all screen sizes |
| **Theme** | Passed to `AppProvider` via `theme` prop | Ensures theme tokens reach Toolpad components |

### When to show title vs suppress

| Page Type | Title | Breadcrumbs |
|-----------|-------|-------------|
| Top-level (Home, Dashboard) | Show | Suppress |
| Module root (/projects, /reports) | Show (auto from nav config) | Suppress |
| Detail page (/projects/123) | Show (custom or auto) | Show |

---

## Title Styling

Controlled globally via `theme/typography.ts`:

```ts
h4: {
    fontSize: '1.19rem',   // compact page heading
}
```

> [!IMPORTANT]
> Do not override title font size per-page. All sizing goes through the theme for consistency.

---

## Navigation Tabs (Pages with Tabs)

Use standard MUI `Tabs` and `Tab` components inside `PageContainer`.

### Required Pattern

```tsx
<PageContainer title="Page Name" breadcrumbs={[]} maxWidth={false}>
    {/* Tabs — gray background, full-width divider */}
    <Tabs
        value={tab}
        onChange={(_e, v) => setTab(v)}
        sx={{ borderBottom: 1, borderColor: 'divider', mx: -3, px: 3, mt: -1.5 }}
    >
        <Tab label="Tab One" />
        <Tab label="Tab Two" />
    </Tabs>

    {/* Content — white background, edge-to-edge */}
    <Box sx={{ bgcolor: 'background.paper', mx: -3, px: 3, py: 3, flexGrow: 1 }}>
        {tab === 0 && ( /* Tab One content */ )}
        {tab === 1 && ( /* Tab Two content */ )}
    </Box>
</PageContainer>
```

### Tab Styling

Controlled globally via `theme/components.ts`:

```ts
MuiTab: {
    styleOverrides: {
        root: {
            textTransform: 'none',  // normal case, not uppercase
        },
    },
}
```

### Visual Rules

| Element | Behaviour |
|---------|-----------|
| **Tab bar background** | `primary.main` (Utility) or `background.paper` (Standard) |
| **Tab divider** | Full-width via `mx: -3, px: 3` |
| **Tab text** | Normal case (theme override) |
| **Title–tabs gap** | Tightened via `mt: -1.5` on Tabs |
| **Content background** | White (`background.paper`) via `Box` |
| **Content width** | Edge-to-edge via `mx: -3, px: 3` |

> [!NOTE]
> **Settings & Utility Pages Exception:**
> For data-dense settings pages, a tighter vertical rhythm (`py={2}`) is permitted. Refer to **[Page-Level Spacing Rules](./page-spacing-spec.md)** for the specific "Settings Context" governance.

---

## Pages Without Tabs

For simple pages without tab navigation, use `PageContainer` with the same base rules:

```tsx
<PageContainer title="Page Name" breadcrumbs={[]} maxWidth={false}>
    {/* Content renders directly */}
</PageContainer>
```

---

## Theme Integration

The app theme must be passed to Toolpad's `AppProvider` for PageContainer and other Toolpad components to respect theme tokens:

```tsx
// main.tsx
<ThemeProvider theme={theme}>
    <CssBaseline />
    <AuthProvider>
        <App />
    </AuthProvider>
</ThemeProvider>

// ToolpadShell.tsx
<AppProvider theme={theme} navigation={NAVIGATION} ...>
    <DashboardLayout>{children}</DashboardLayout>
</AppProvider>
```

---

## Forbidden Patterns

- ❌ Custom shell components (use `DashboardLayout` only)
- ❌ Per-page font size overrides on titles
- ❌ Raw color values (use theme tokens: `background.paper`, `divider`, etc.)
- ❌ Custom `maxWidth` constraints on PageContainer
- ❌ Custom AppBar or Drawer implementations
