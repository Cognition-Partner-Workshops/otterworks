import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

/**
 * Admin dashboard (frontend/admin-dashboard) journeys against a running local stack.
 * ADMIN_BASE_URL defaults to http://localhost:4200, OTTERWORKS_API_BASE_URL to http://localhost:8080.
 * Logs in with OTTERWORKS_ADMIN_LOGIN_EMAIL/PASSWORD, else a freshly registered user
 * (admin-service accepts any valid JWT; see tests/api/test_admin_console_flow.py).
 */
const ADMIN_URL = (process.env.ADMIN_BASE_URL || "http://localhost:4200").replace(/\/$/, "");
const API_URL = (process.env.OTTERWORKS_API_BASE_URL || "http://localhost:8080").replace(/\/$/, "");

let credentials: { email: string; password: string };

async function resolveCredentials(request: APIRequestContext) {
  const email = process.env.OTTERWORKS_ADMIN_LOGIN_EMAIL;
  const password = process.env.OTTERWORKS_ADMIN_LOGIN_PASSWORD;
  if (email && password) return { email, password };
  const generated = {
    email: `admin-e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.test`,
    password: "OtterworksTest123!",
  };
  const res = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { displayName: "Admin E2E", ...generated },
  });
  expect(res.status(), await res.text()).toBe(201);
  return generated;
}

async function login(page: Page) {
  await page.goto(`${ADMIN_URL}/login`);
  await page.locator('input[name="email"]').fill(credentials.email);
  await page.locator('input[name="password"]').fill(credentials.password);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.locator(".page-title", { hasText: "Dashboard" })).toBeVisible({ timeout: 15_000 });
}

async function open(page: Page, path: string, title: string) {
  await page.goto(`${ADMIN_URL}${path}`);
  await expect(page.locator(".page-title", { hasText: title })).toBeVisible();
}

test.describe("Admin dashboard", () => {
  test.describe.configure({ mode: "default" });

  test.beforeAll(async ({ request }) => {
    const probe = await request.get(`${ADMIN_URL}/login`).catch(() => null);
    test.skip(!probe || !probe.ok(), `admin dashboard not reachable at ${ADMIN_URL}`);
    credentials = await resolveCredentials(request);
  });

  test("redirects to login when unauthenticated and rejects an empty password", async ({ page }) => {
    await page.goto(`${ADMIN_URL}/users`);
    await expect(page).toHaveURL(/\/login/);
    await page.locator('input[name="email"]').fill(credentials.email);
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page.getByText("Please enter both email and password.")).toBeVisible();
  });

  test("logs in and shows dashboard stat cards with a real token", async ({ page }) => {
    await login(page);
    await expect(page.locator(".stat-card")).toHaveCount(4);
    const token = await page.evaluate(() => localStorage.getItem("ow_admin_token"));
    expect(token?.split(".")).toHaveLength(3);
  });

  test("searches users and suspends/restores one via the action menu", async ({ page }) => {
    await login(page);
    await open(page, "/users", "User Management");
    const rows = page.locator("tr.mat-mdc-row");
    await expect(rows.first()).toBeVisible();

    const emailOf = async (row: ReturnType<Page["locator"]>) =>
      ((await row.innerText()).match(/[\w.+-]+@[\w.-]+/) || [""])[0];
    const search = page.getByPlaceholder("Search by name or email");

    const firstEmail = await emailOf(rows.first());
    await search.fill(firstEmail.toUpperCase());
    await search.press("End");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText(firstEmail);

    await search.fill("");
    await search.press("End");
    const target = rows.filter({ has: page.getByRole("cell", { name: "active", exact: true }) }).first();
    const email = await emailOf(target);
    const row = rows.filter({ hasText: email });

    await target.getByRole("button", { name: "User actions" }).click();
    await page.getByRole("menuitem", { name: /Suspend/ }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Suspend" }).click();
    await expect(page.getByText(/has been suspended/)).toBeVisible();
    await expect(row.getByRole("cell", { name: "suspended", exact: true })).toBeVisible();

    await row.getByRole("button", { name: "User actions" }).click();
    await page.getByRole("menuitem", { name: /Restore/ }).click();
    await expect(page.getByText(/has been restored/)).toBeVisible();
    await expect(row.getByRole("cell", { name: "active", exact: true })).toBeVisible();
  });

  test("shows the suspension in the audit log", async ({ page }) => {
    await login(page);
    await open(page, "/audit", "Audit Logs");
    await page.getByPlaceholder("Search by user, action, or resource").fill("suspend");
    await page.getByPlaceholder("Search by user, action, or resource").press("End");
    await expect(page.locator("tr.mat-mdc-row").first()).toBeVisible();
  });

  test("lists storage quotas with usage", async ({ page }) => {
    await login(page);
    await open(page, "/quotas", "Storage Quotas");
    await expect(page.locator("tr.mat-mdc-row").first()).toBeVisible();
    await expect(page.locator("tr.mat-mdc-row").first()).toContainText(/GB|MB|KB| B/);
  });

  test("toggles a feature flag and persists it", async ({ page }) => {
    await login(page);
    const token = await page.evaluate(() => localStorage.getItem("ow_admin_token"));
    const headers = { Authorization: `Bearer ${token}` };
    const flag = (await (await page.request.get(`${API_URL}/api/v1/admin/features`, { headers })).json()).features[0];
    try {
      await open(page, "/features", "Feature Flags");
      const switchFor = () =>
        page.locator("mat-card", { has: page.getByRole("heading", { name: flag.name }) }).locator("button[role='switch']");
      await expect(switchFor()).toHaveAttribute("aria-checked", String(flag.enabled));
      await switchFor().click();
      await expect(page.locator(".mat-mdc-snack-bar-container")).toContainText(
        `${flag.name} ${flag.enabled ? "disabled" : "enabled"}`,
      );
      await page.reload();
      await expect(switchFor()).toHaveAttribute("aria-checked", String(!flag.enabled));
    } finally {
      await page.request.put(`${API_URL}/api/v1/admin/features/${flag.id}`, {
        headers,
        data: { feature: { enabled: flag.enabled } },
      });
    }
  });

  // [REAL] FeaturesComponent.toggleFlag computes `!flag.enabled` but never updates the flag after the
  // PUT, so toggling the same switch back re-sends the first state and the flag stays flipped.
  test("toggling a flag off and on again persists the original state [REAL: stale toggleFlag state]", async ({
    page,
  }) => {
    await login(page);
    const token = await page.evaluate(() => localStorage.getItem("ow_admin_token"));
    const headers = { Authorization: `Bearer ${token}` };
    const flags = (await (await page.request.get(`${API_URL}/api/v1/admin/features`, { headers })).json()).features;
    const flag = flags[0];
    try {
      await open(page, "/features", "Feature Flags");
      const card = page.locator("mat-card", { has: page.getByRole("heading", { name: flag.name }) });
      const toggle = card.locator("button[role='switch']");
      await toggle.click();
      const snackbar = page.locator(".mat-mdc-snack-bar-container").last();
      await expect(snackbar).toContainText(flag.enabled ? "disabled" : "enabled");
      await toggle.click();
      await expect(snackbar).toContainText(flag.enabled ? "enabled" : "disabled");
      await page.reload();
      await expect(
        page.locator("mat-card", { has: page.getByRole("heading", { name: flag.name }) }).locator("button[role='switch']"),
      ).toHaveAttribute("aria-checked", String(flag.enabled));
    } finally {
      await page.request.put(`${API_URL}/api/v1/admin/features/${flag.id}`, {
        headers,
        data: { feature: { enabled: flag.enabled } },
      });
    }
  });

  test("shows system health for backend services via the sidebar", async ({ page }) => {
    await login(page);
    await page.getByRole("link", { name: "System Health" }).click();
    await expect(page.locator(".page-title", { hasText: "System Health" })).toBeVisible();
    await expect(page.locator(".summary-card.healthy .summary-count")).not.toHaveText("0");
    await expect(page.getByText("auth-service")).toBeVisible();
  });

  // [REAL] nginx.conf.template `location /health` (container probe) shadows the SPA /health route,
  // so reloading or deep-linking the System Health page returns probe JSON instead of the app.
  test("deep-links to the System Health page [REAL: nginx /health shadows SPA route]", async ({ page }) => {
    await login(page);
    await open(page, "/health", "System Health");
  });
});
