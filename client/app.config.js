require("dotenv").config();

// Import the static configuration from app.json
const appJson = require("./app.json");

module.exports = {
  ...appJson,
  expo: {
    ...appJson.expo,
    // Override/add dynamic values from environment variables
    extra: {
      ...appJson.expo.extra,
      apiUrl: process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000",
      adsEnv: process.env.EXPO_PUBLIC_ADS_ENV || "dev"
    }
  }
};
