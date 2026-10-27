import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : "html",
  failOnFlakyTests: !!process.env.CI,
  timeout: 30_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      testIgnore: "webkit/**",
      use: { ...devices["Desktop Chrome"] },
    },
    // Baselines are WebKit-on-macOS; Linux runs never see this project or its specs.
    ...(process.platform === "darwin"
      ? [
          {
            name: "webkit-macos",
            testMatch: "webkit/**/*.spec.ts",
            snapshotPathTemplate:
              "{testDir}/webkit/__screenshots__/{projectName}-{platform}/{testFileName}/{arg}{ext}",
            use: { ...devices["Desktop Safari"] },
          },
        ]
      : []),
  ],

  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
