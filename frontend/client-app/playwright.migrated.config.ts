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
    baseURL: process.env.BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 0.0.0.0 --port 3000",
    url: "http://localhost:3000",
    reuseExistingServer: true,
  },
});
