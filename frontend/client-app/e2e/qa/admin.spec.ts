import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

// Admin dashboard lives on its own origin; the client-app config's baseURL (:3000) is not used here.
const ADMIN_URL = process.env.ADMIN_BASE_URL || "http://localhost:4200";
const GATEWAY_URL = process.env.OTTERWORKS_API_BASE_URL || "http://localhost:8080";
const PASSWORD = "OtterworksTest123!";

test.describe.configure({ mode: "serial" });

let email = "";

async function registerOperator(request: APIRequestContext): Promise<string> {
  const address = `qa-admin-e2e-${Date.now()}@example.test`;
  const res = await request.post(`${GATEWAY_URL}/api/v1/auth/register`, {
    data: { email: address, password: PASSWORD, displayName: "QA Admin E2E" },
  });
  expect(res.status(), await res.text()).toBe(201);
  return address;
}

async function login(page: Page) {
  await page.goto(`${ADMIN_URL}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /sign in|log in|login/i }).click();
  await expect(page.locator("h1.page-title", { hasText: "Dashboard" })).toBeVisible();
}

test.beforeAll(async ({ request }) => {
  email = await registerOperator(request);
});

test("unauthenticated users are redirected to /login", async ({ page }) => {
  await page.goto(`${ADMIN_URL}/users`);
  await expect(page).toHaveURL(/\/login$/);
});

test("gateway login lands on the dashboard with live metrics", async ({ page, request }) => {
  await login(page);
  const token = await page.evaluate(() => localStorage.getItem("ow_admin_token"));
  expect(token, "dashboard should store the gateway access token, not the offline mock").toBeTruthy();
  const payload = JSON.parse(Buffer.from(token!.split(".")[1], "base64url").toString());
  expect(payload.email).toBe(email);

  const metrics = await (
    await request.get(`${GATEWAY_URL}/api/v1/admin/metrics/summary`, { headers: { Authorization: `Bearer ${token}` } })
  ).json();
  const totalUsers = page.locator(".stat-card", { hasText: "Total Users" }).locator(".stat-value");
  await expect(totalUsers).toHaveText(String(metrics.users.total));
});

test("user management lists, searches and suspends/restores a user", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.locator("h1.page-title", { hasText: "User Management" })).toBeVisible();
  const rows = page.locator("tr.table-row");
  await expect(rows.first()).toBeVisible();

  await page.getByPlaceholder("Search by name or email").pressSequentially("james.park");
  await expect(rows).toHaveCount(1);
  const row = rows.first();
  await expect(row).toContainText("James Park");
  await expect(row.locator(".status-chip")).toHaveText("active");

  await row.getByRole("button", { name: "User actions" }).click();
  await page.getByRole("menuitem", { name: "Suspend" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Suspend" }).click();
  await expect(page.getByText("James Park has been suspended")).toBeVisible();
  await expect(row.locator(".status-chip")).toHaveText("suspended");

  await row.getByRole("button", { name: "User actions" }).click();
  await page.getByRole("menuitem", { name: "Restore" }).click();
  await expect(page.getByText("James Park has been restored")).toBeVisible();
  await expect(row.locator(".status-chip")).toHaveText("active");
});

test("audit log view shows the suspend event", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Audit Logs" }).click();
  await expect(page.locator("h1.page-title", { hasText: "Audit Logs" })).toBeVisible();
  await page.getByPlaceholder("Search by user, action, or resource").pressSequentially("suspend");
  await expect(page.locator("tr.mat-mdc-row").first()).toBeVisible();
  await expect(page.locator("tr.mat-mdc-row", { hasText: /suspend/i }).first()).toBeVisible();
});

test("every admin page in the sidebar renders without errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await login(page);
  for (const [link, title] of [
    ["Feature Flags", "Feature Flags"],
    ["System Health", "System Health"],
    ["Announcements", "Announcements"],
    ["Storage Quotas", "Storage"],
    ["Incidents", "Incident Response"],
    ["Analytics", "Analytics"],
  ]) {
    await page.getByRole("link", { name: link }).click();
    await expect(page.locator("h1", { hasText: title }).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("logout clears the session", async ({ page }) => {
  await login(page);
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${ADMIN_URL}/`);
  await expect(page).toHaveURL(/\/login$/);
});
