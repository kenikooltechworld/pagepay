require("dotenv").config();

// Import base configuration from app.json
const { expo: baseConfig } = require("./app.json");

module.exports = ({ config }) => {
  return {
    ...config,
    expo: {
      ...baseConfig,
      extra: {
        ...baseConfig.extra
      }
    }
  };
};
