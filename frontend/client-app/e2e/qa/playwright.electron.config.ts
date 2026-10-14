import { defineConfig } from "@playwright/test";

// Electron desktop QA suite: launches the real desktop app (frontend/client-app/desktop)
// via Playwright's _electron API, so no browser project or Vite webServer is needed.
// Prereqs: web build (VITE_COLLAB_WS_URL=ws://localhost:8084 npm run build), desktop
// `npm ci && npm run build`, and the local stack (`make up`).
export default defineConfig({
  testDir: ".",
  testMatch: /electron\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
});
