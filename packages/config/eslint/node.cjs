const base = require("./base.cjs");

module.exports = {
  ...base,
  env: {
    ...base.env,
    browser: false
  },
  parserOptions: {
    ...base.parserOptions
  }
};
