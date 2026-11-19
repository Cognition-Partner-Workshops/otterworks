import { defineConfig, devices } from "@playwright/test";

const gatewayPort = process.env.FIXTURE_GATEWAY_PORT || "8099";
const gatewayUrl = `http://127.0.0.1:${gatewayPort}`;

export default defineConfig({
  testDir: "./e2e/admin",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  outputDir: "test-results/admin",
  use: {
    ...devices["Desktop Chrome"],
    timezoneId: "UTC",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "angular",
      metadata: { pathPrefix: "" },
      use: { baseURL: "http://localhost:4200" },
    },
    {
      name: "react",
      metadata: { pathPrefix: "/admin" },
      use: { baseURL: "http://localhost:3000" },
    },
  ],
  webServer: [
    {
      command: "node e2e/admin/fixture-gateway.mjs",
      url: `${gatewayUrl}/api/v1/admin/users`,
      env: { FIXTURE_GATEWAY_PORT: gatewayPort },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run start --prefix ../admin-dashboard",
      url: "http://localhost:4200/login",
      env: { API_GATEWAY_URL: gatewayUrl },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000/admin/login",
      env: { API_GATEWAY_URL: gatewayUrl },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
