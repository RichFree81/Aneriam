const base = require("@aneriam/config/eslint/node");

module.exports = {
  ...base,
  root: true,
  parserOptions: {
    ...base.parserOptions,
    project: ["./tsconfig.json"],
    tsconfigRootDir: __dirname
  }
};
