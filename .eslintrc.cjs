const base = require("@aneriam/config/eslint/react");

module.exports = {
  ...base,
  root: true,
  parserOptions: {
    ...base.parserOptions,
    tsconfigRootDir: __dirname
  }
};
