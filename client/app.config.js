require("dotenv").config();

// Import base configuration from app.json
const { expo: baseConfig } = require("./app.json");

module.exports = ({ config }) => {
  return {
    ...config,
    expo: {
      ...baseConfig,
      extra: {
        ...baseConfig.extra,
        // Dynamic environment-specific values
        apiUrl: process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000",
        adsEnv: process.env.EXPO_PUBLIC_ADS_ENV || "dev"
      },
      // Development server URL - reads from .env
      packagerOpts: {
        hostType: "lan"
      },
      devClient: {
        url: process.env.EXPO_PUBLIC_DEV_SERVER_URL || "exp://localhost:8081"
      }
    }
  };
};
