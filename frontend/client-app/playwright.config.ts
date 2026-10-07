import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import path from "node:path";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const PUBLIC_PAGES_BUILT = process.env.PUBLIC_PAGES_BUILT === "1";

export default defineConfig({
  testDir: "./e2e",
  outputDir: PUBLIC_PAGES_BUILT ? "./a11y-results" : "./test-results",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "html",
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
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  /* Accessibility audits use the production build, without a backend. */
  ...(PUBLIC_PAGES_BUILT && existsSync(path.resolve(__dirname, "dist/index.html"))
    ? {
        webServer: {
          command: "npm run start -- --host 127.0.0.1 --port 3000 --strictPort",
          url: BASE_URL,
          reuseExistingServer: false,
          timeout: 120_000,
        },
      }
    : process.env.CI || PUBLIC_PAGES_BUILT
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: BASE_URL,
          reuseExistingServer: true,
          timeout: 120_000,
        },
      }),
});
