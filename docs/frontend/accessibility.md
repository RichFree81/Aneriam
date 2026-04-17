# Accessibility Standards (MUI-F1)

## Policy
Aneriam applications must support keyboard navigation and screen readers to a reasonable standard. We do not target full WCAG AAA, but we strictly enforce "no dead ends" and "usable non-visual navigation".

## Checklist

### Keyboard Navigation
- [ ] **Tab Order**: Focus moves logically top-to-bottom, left-to-right.
- [ ] **No Traps**: Focus never gets stuck in a component (Escape should close modals/popovers).
- [ ] **Focus Visibility**: Focus outline MUST be visible on all interactive elements. Do NOT use `outline: none` without a fallback styled state.

### Semantics & Labels
- [ ] **IconButtons**: MUST have an `aria-label` or `Tooltip` (that provides accessible name).
- [ ] **Forms**: All inputs must have a visual label or `aria-label` / `aria-labelledby`. Placeholders are NOT labels.
- [ ] **Dialogs**: Must use `DialogTitle` (for `aria-labelledby`) and optionally `DialogContentText` (for `aria-describedby`).

### Color & Contrast
- [ ] **Text**: Use `text.primary` on default backgrounds.
- [ ] **Errors**: Error text must be readable against its background (standard Palette.error.main).
- [ ] **States**: Disabled states must have `aria-disabled="true"` or `disabled` attribute.

## Component Specifics

### Dialogs
- Ensure `autoFocus` is placed on the least destructive action (e.g., "Cancel") or the first input, not "Delete".
- Supports `Escape` key to close.

### DataToolbar
- Filter inputs and buttons must be keyboard reachable.
- Search input must have a label (visible or aria).

### Feedback States
- Error messages must be announced or strictly associated with the failed field.
