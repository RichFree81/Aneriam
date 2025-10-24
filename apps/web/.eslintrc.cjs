const base = require("@aneriam/config/eslint/react");

module.exports = {
  ...base,
  root: true,
  extends: [...(base.extends ?? []), "next/core-web-vitals", "next/typescript"],
  parserOptions: {
    ...base.parserOptions,
    tsconfigRootDir: __dirname
  }
};
