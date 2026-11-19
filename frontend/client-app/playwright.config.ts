import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const iosFlows = process.env.PW_IOS_FLOWS === "1";

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
      testIgnore: "**/ios-flows/**",
      use: { ...devices["Desktop Chrome"] },
    },
    ...(iosFlows ? [{
      name: "webkit-iphone",
      testDir: "./e2e/ios-flows",
      workers: 1,
      use: { ...devices["iPhone 13"], baseURL: "http://127.0.0.1:3001" },
    }] : []),
  ],

  ...(iosFlows
    ? { webServer: [
        ...(!process.env.BASE_URL ? [{ command: "npm run dev", url: BASE_URL, reuseExistingServer: !process.env.CI, timeout: 120_000 }] : []),
        { command: "node mock-api/server.mjs", url: "http://127.0.0.1:4010/health", reuseExistingServer: false },
        { command: "VITE_STORAGE_PUBLIC_URL=http://127.0.0.1:4010 API_GATEWAY_URL=http://127.0.0.1:4010 VITE_API_BASE_URL=http://127.0.0.1:4010/api/v1 VITE_COLLAB_WS_URL=ws://127.0.0.1:4010 npm run dev -- --host 127.0.0.1 --port 3001 --strictPort", url: "http://127.0.0.1:3001", reuseExistingServer: false },
      ] }
    : process.env.BASE_URL
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: BASE_URL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      }),
});
