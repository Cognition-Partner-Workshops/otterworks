import { defineConfig } from "@playwright/test";

// Electron e2e for the desktop shell. Requires `npm ci` here, the client-app web
// build in ../dist (`npm --prefix .. run build`), a display (DISPLAY=:0 / xvfb-run)
// and the OtterWorks API gateway (API_GATEWAY_URL, default http://localhost:8080).
// Run: ../node_modules/.bin/playwright test -c playwright.config.ts
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? "github" : "list",
  outputDir: "./e2e-results",
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
});
