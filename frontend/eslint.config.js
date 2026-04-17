import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Milestone F - Governance & Hardening Rules

      // 1. No raw hex/rgb colors (except in palette or docs)
      'no-restricted-syntax': [
        'warn',
        {
          selector: "Literal[value=/^#[0-9a-fA-F]{3,8}$/]:not(:matches(Program[sourceType='module'] > ExportDefaultDeclaration Property[key.name='palette'] *))",
          message: 'MUI Standards: Do not use raw hex colors. Use theme tokens (primary.main, text.secondary, etc.) or palette.ts.'
        },
        {
          selector: "Literal[value=/^rgba?\\(/]",
          message: 'MUI Standards: Do not use raw rgb/rgba strings. Use alpha utility functions or theme tokens.'
        },

        // 2. No custom box-shadow strings
        {
          selector: "Property[key.name='boxShadow'] > Literal[value=/\\d+px/]",
          message: 'MUI Standards: Do not use custom box-shadow strings. Use valid integers (theme.shadows[n]) or theme.shadows tokens.'
        },

        // 3. IconButton aria-label enforcement (Best effort)
        {
          selector: "JSXOpeningElement[name.name='IconButton']:not(:has(JSXAttribute[name.name='aria-label'])):not(:has(JSXAttribute[name.name='title']))",
          message: "MUI Standards: IconButton must have an aria-label or title for accessibility."
        }
      ],
    },
  },
  // Specific exclusions for palette.ts and documentation/assets if needed
  {
    files: ['src/theme/palette.ts', 'docs/**'],
    rules: {
      'no-restricted-syntax': 'off'
    }
  }
])
