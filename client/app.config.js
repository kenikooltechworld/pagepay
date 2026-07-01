// Load environment variables from .env file.
// Mirror of Earn9ja/app.config.js: keeps app.json as the single source of
// static Expo config and injects EXPO_PUBLIC_* values into `extra` so the
// runtime can read them via expo-constants.
require("dotenv").config();
const { expo: baseExpo } = require("./app.json");

module.exports = {
  expo: {
    ...baseExpo,
    extra: {
      ...(baseExpo.extra || {}),
      eas: {
        projectId: "b43a48ba-f084-472f-ac1c-3db5fa470326",
      },
      apiUrl:
        process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000/api/v1",
      // `dev` returns Google's test unit IDs (safe for dev builds).
      // `prod` returns the PagePay IDs seeded in app_config. CI sets
      // this to `prod` for the staging EAS build.
      adsEnv: process.env.EXPO_PUBLIC_ADS_ENV || "dev",
    },
  },
};