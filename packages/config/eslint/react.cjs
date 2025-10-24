const base = require("./base.cjs");

module.exports = {
  ...base,
  plugins: [...base.plugins, "react", "react-hooks", "jsx-a11y"],
  extends: [
    ...base.extends,
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "plugin:jsx-a11y/recommended"
  ],
  settings: {
    ...base.settings,
    react: {
      version: "detect"
    }
  },
  rules: {
    ...base.rules,
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off"
  }
};
