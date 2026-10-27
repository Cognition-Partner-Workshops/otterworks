import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/migrated",
  outputDir: "./playwright-report-migrated-artifacts",
  fullyParallel: true,
  retries: 0,
  expect: { timeout: 10_000 },
  reporter: [
    ["html", { outputFolder: "playwright-report-migrated", open: "never" }],
    ["json", { outputFile: "playwright-report-migrated/results.json" }],
    ["list"],
  ],
  use: {
    baseURL: process.env.ADMIN_BASE_URL || "http://localhost:4200",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run start",
    url: "http://localhost:4200",
    reuseExistingServer: true,
    timeout: 180_000,
  },
});
