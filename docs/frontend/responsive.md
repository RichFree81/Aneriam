# Responsive Standards (MUI-F2)

## Policy
The UI must remain functional on screens down to **360px** width (typical mobile). Layouts may stack, but functionality cannot be hidden without an alternative access path.

## Patterns

### Shell & Layout
- **Drawer**: Permanent on Desktop (`md`+), Temporary/Overlay on Mobile (`xs`, `sm`).
- **AppBar**: Sticky or Fixed. Title truncates if necessary.

### DataToolbar
- **Behavior**: Items wrap naturally.
- **Mobile**:
  - Search bar takes full width on its own row if needed.
  - Action buttons (Filter, Export) group together or collapse into a menu if space is critically low (though wrapping is preferred for simplicity).

### Tables (`DataGrid` / `Table`)
- **Overflow**: Horizontal scroll is acceptable for complex data tables.
- **Stacked**: For simple lists, consider switching to a Card/List view on mobile (optional, only if implemented).
- **Minimums**: Do not hide "Actions" columns. Sticky header preferred.

### Dialogs
- **Sizing**:
  - `fullWidth`: default `true`.
  - `maxWidth`: typically `sm` or `md`.
  - **Mobile**: Use `fullScreen` prop on `Dialog` when `theme.breakpoints.down('sm')` matches, especially for complex forms.

## CSS / SX Rules
- Avoid hardcoded pixel widths like `width: 600px`. Use `%` or `maxWidth`.
- Use `gap` in Flexbox/Grid instead of margins for spacing items that might wrap.
