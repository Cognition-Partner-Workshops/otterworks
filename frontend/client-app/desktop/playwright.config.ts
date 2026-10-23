import { defineConfig } from "@playwright/test";

// Drives the real Electron app (build/main.js) with Playwright's Electron support.
// Needs a display (DISPLAY=:0 or xvfb-run) and the client-app web build in ../dist.
// Data-backed specs need the local stack (API_GATEWAY_URL, default http://localhost:8080).
export default defineConfig({
  testDir: "./test/e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? "github" : "list",
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
});
