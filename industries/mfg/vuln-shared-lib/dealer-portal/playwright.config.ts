import { defineConfig, devices } from '@playwright/test';

// Smoke suite: the BFF serves the production Angular build and proxies to a stubbed upstream.
const bffPort = Number(process.env['BFF_PORT'] || 5080);
const stubPort = Number(process.env['STUB_PORT'] || 5199);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env['CI'] ? 1 : 0,
  reporter: process.env['CI'] ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${bffPort}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'node e2e/stub-upstream.mjs',
      url: `http://127.0.0.1:${stubPort}/healthz`,
      env: { STUB_PORT: String(stubPort) },
      reuseExistingServer: !process.env['CI'],
    },
    {
      command: 'dotnet run --no-build -c Release --no-launch-profile --project bff/src/DealerPortal.Bff',
      url: `http://localhost:${bffPort}/healthz`,
      timeout: 120_000,
      reuseExistingServer: !process.env['CI'],
      env: {
        ASPNETCORE_URLS: `http://localhost:${bffPort}`,
        ASPNETCORE_ENVIRONMENT: 'Production',
        Portal__DevApiBaseUrl: `http://127.0.0.1:${stubPort}`,
        Portal__NoticeFeedUrl: `http://127.0.0.1:${stubPort}/dealer-notices.json`,
        Portal__StaticRoot: `${__dirname}/dist/dealer-portal/browser`,
        Portal__SecureCookie: 'false',
      },
    },
  ],
});
