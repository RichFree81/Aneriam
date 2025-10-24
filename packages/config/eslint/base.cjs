const base = {
  env: {
    es2022: true,
    node: true,
    browser: true
  },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module"
  },
  plugins: ["@typescript-eslint", "import", "simple-import-sort"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:import/recommended",
    "plugin:import/typescript",
    "prettier"
  ],
  settings: {
    "import/resolver": {
      typescript: true
    }
  },
  rules: {
    "@typescript-eslint/no-explicit-any": "warn",
    "simple-import-sort/imports": "error",
    "simple-import-sort/exports": "error"
  },
  ignorePatterns: ["**/dist/**", "**/.next/**", "**/node_modules/**"]
};

module.exports = base;
