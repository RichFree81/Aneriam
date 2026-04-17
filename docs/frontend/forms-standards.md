# Milestone C: Forms, Validation, and Input Standards

## Overview
This milestone standardizes form construction, validation behavior, and user feedback using plain Material UI components and light compositional wrappers.

## Core Standards

### 1. Form Construction
- **Labels**: Always use the `label` prop.
- **Required Fields**: Marked with an asterisk (`*`) which is styled with `text.secondary` (default) or `error.main` (on error).
- **Helper Text**: **Forbidden** for self-explanatory labels. Use only for error messages or complex formatting instructions (e.g. passwords).
- **Placeholders**: Supplementary only. Do not use as a replacement for labels.
- **Section Headers**: Use `variant="subtitle1"` with `fontWeight: 600` wrapped in a `Box` with `mt={4}` for visual separation. **Do not** place a `Divider` below the header.
- **Field Layout**: Wrap section fields in a shaded container:
  ```tsx
  // Outer Container
  <Box sx={{ p: 3, bgcolor: 'grey.50', borderRadius: 1, border: 1, borderColor: 'divider' }}>
      <Grid container spacing={2}>
          {/* Inputs (White Background) */}
          <TextField sx={{ bgcolor: 'background.paper' }} />
      </Grid>
  </Box>
  ```

### 2. Validation Pattern
- **Trigger**: Validation should strictly happen **onBlur** (field leave) or **onSubmit**. Avoid aggressive validation on keystroke unless specifically required (e.g., password strength).
- **Display**: use the `error` prop (boolean) and `helperText` (string).
- **Error Style**: Errors use `palette.error.main`.

### 3. Feedback
- **Field Level**: Use `helperText` in error state.
- **Form Level**: Use the `FormGlobalError` component for submission failures.
- **Success**: Use `Alert` with `severity="success"`.

## Components

### `FormSection`
Groups related fields with standard vertical spacing. For use in **create/edit forms** only — field grouping with no edit-state toggle. Heading renders as `subtitle1` with `fontWeight: 600`.

```tsx
<FormSection title="Account">
  <TextField label="Name" fullWidth />
  <TextField label="Email" fullWidth />
</FormSection>
```

> **Not** for settings/configuration pages. Use `SettingsSection` there instead.

### `SettingsSection`
For use in **settings and configuration pages** only. Provides view/edit/save/cancel state toggling with a grey (`grey.50`) container. Heading also uses `subtitle1` with `fontWeight: 600`.

```tsx
<SettingsSection
  title="Module Identity"
  isEditing={editing}
  onEdit={() => setEditing(true)}
  onSave={() => setEditing(false)}
  onCancel={() => setEditing(false)}
>
  <TextField label="Name" fullWidth />
</SettingsSection>
```

> **Not** for create/edit forms. Use `FormSection` there instead.

### `FormGlobalError`
Standard API error display.
```tsx
<FormGlobalError error={errorMessage} />
```

## Theme Defaults (Milestone C Updates)
- **MuiTextField**: `variant="outlined"` always.
- **MuiInputLabel**: Standardized asterisk color.
- **MuiAlert**: Standardized variants and severity colors.
- **MuiInputAdornment**: Standardized color (`text.secondary`).
