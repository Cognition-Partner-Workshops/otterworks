import { test, expect, request, type APIRequestContext, type Page } from "@playwright/test";
import { randomBytes } from "node:crypto";

/*
 * Admin dashboard (Angular, :4200) journeys against a live stack.
 * Bugs are tagged [REAL] (genuine defect) or [PLANTED] (AGENTS.md / bug-catalog.yaml).
 * Skips itself when the admin dashboard or gateway is not reachable (e.g. client-app-only CI).
 */

const ADMIN_URL = process.env.ADMIN_BASE_URL || "http://localhost:4200";
const GATEWAY_URL = process.env.GATEWAY_URL || "http://localhost:8080";
const PASSWORD = `Qa-${randomBytes(6).toString("hex")}-A1!`;

test.use({ baseURL: ADMIN_URL });
test.describe.configure({ mode: "serial" });

let gateway: APIRequestContext;
let email = "";
let token = "";
let reachable = false;

async function login(page: Page, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
}

async function createFlag(): Promise<{ id: string; name: string }> {
  const name = `qa_e2e_${randomBytes(4).toString("hex")}`;
  const res = await gateway.post("/api/v1/admin/features", {
    headers: { Authorization: `Bearer ${token}` },
    data: { feature: { name, description: "admin e2e temp flag", enabled: false } },
  });
  expect(res.status()).toBe(201);
  return { id: (await res.json()).id, name };
}

async function flagEnabled(id: string): Promise<boolean> {
  const res = await gateway.get(`/api/v1/admin/features/${id}`, { headers: { Authorization: `Bearer ${token}` } });
  return (await res.json()).enabled;
}

async function deleteFlag(id: string) {
  await gateway.delete(`/api/v1/admin/features/${id}`, { headers: { Authorization: `Bearer ${token}` } });
}

test.beforeAll(async () => {
  gateway = await request.newContext({ baseURL: GATEWAY_URL });
  try {
    const [admin, health] = await Promise.all([
      gateway.get(ADMIN_URL, { timeout: 5_000 }),
      gateway.get("/health", { timeout: 5_000 }),
    ]);
    reachable = admin.ok() && health.ok();
  } catch {
    reachable = false;
  }
  if (!reachable) return;
  email = `admin-e2e-${Date.now()}-${randomBytes(3).toString("hex")}@example.test`;
  const reg = await gateway.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD, displayName: "Admin E2E" },
  });
  expect(reg.status()).toBe(201);
  token = (await reg.json()).accessToken;
});

test.beforeEach(() => {
  test.skip(!reachable, `admin dashboard (${ADMIN_URL}) or gateway (${GATEWAY_URL}) not reachable`);
});

test.afterAll(async () => {
  await gateway?.dispose();
});

test.describe("admin login", () => {
  test("unauthenticated visit redirects to login", async ({ page }) => {
    await page.goto("/users");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "OtterWorks Admin" })).toBeVisible();
  });

  test("empty submit shows a validation error", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.locator(".error-message")).toBeVisible();
  });

  test("valid credentials land on the dashboard with a real gateway token", async ({ page }) => {
    await login(page);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    const stored = await page.evaluate(() => localStorage.getItem("ow_admin_token"));
    expect(stored?.split(".")).toHaveLength(3);
  });

  test("[REAL] wrong password is rejected", async ({ page }) => {
    test.fail(true, "[REAL] AuthService.login() falls back to an offline mock admin on ANY error, so a 401 logs you in");
    await login(page, "definitely-wrong-password");
    await expect(page.locator(".error-message")).toBeVisible({ timeout: 5_000 });
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe("signed-in admin journeys", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("users list loads and search filters rows", async ({ page }) => {
    await page.getByRole("link", { name: "Users" }).click();
    await expect(page.getByRole("heading", { name: "User Management" })).toBeVisible();
    await expect(page.getByText("james.park@otterworks.io")).toBeVisible();
    await page.getByPlaceholder("Search by name or email").fill("james.park");
    await expect(page.getByText("james.park@otterworks.io")).toBeVisible();
    await expect(page.getByText("bob.martinez@otterworks.io")).toHaveCount(0);
  });

  test("feature flag toggle on persists to the backend", async ({ page }) => {
    const flag = await createFlag();
    try {
      await page.getByRole("link", { name: "Feature Flags" }).click();
      const card = page.locator("mat-card", { has: page.getByRole("heading", { name: flag.name }) });
      await expect(card).toBeVisible();
      const put = page.waitForResponse((r) => r.url().endsWith(`/features/${flag.id}`) && r.request().method() === "PUT");
      await card.getByRole("switch").click();
      expect((await put).status()).toBe(200);
      expect(await flagEnabled(flag.id)).toBe(true);
    } finally {
      await deleteFlag(flag.id);
    }
  });

  test("[REAL] feature flag toggled on then off ends disabled", async ({ page }) => {
    test.fail(true, "[REAL] FeaturesComponent.toggleFlag never updates flag.enabled, so the 2nd toggle re-sends enabled=true");
    const flag = await createFlag();
    try {
      await page.getByRole("link", { name: "Feature Flags" }).click();
      const card = page.locator("mat-card", { has: page.getByRole("heading", { name: flag.name }) });
      const isPut = (r: { url(): string; request(): { method(): string } }) =>
        r.url().endsWith(`/features/${flag.id}`) && r.request().method() === "PUT";
      let put = page.waitForResponse(isPut);
      await card.getByRole("switch").click();
      await put;
      put = page.waitForResponse(isPut);
      await card.getByRole("switch").click();
      await put;
      expect(await flagEnabled(flag.id)).toBe(false);
    } finally {
      await deleteFlag(flag.id);
    }
  });

  test("audit log renders and the action filter narrows rows", async ({ page }) => {
    await page.getByRole("link", { name: "Audit Logs" }).click();
    await expect(page.getByRole("heading", { name: "Audit Logs" })).toBeVisible();
    const rows = page.locator("tr.mat-mdc-row");
    await expect(rows.first()).toBeVisible();
    const action = (await rows.first().locator(".action-chip").textContent())?.trim() ?? "";
    await page.getByLabel("Action").click();
    await page.getByRole("option", { name: action, exact: false }).first().click();
    await expect(rows.first()).toBeVisible();
    const chips = await page.locator("tr.mat-mdc-row .action-chip").allTextContents();
    expect(new Set(chips.map((c) => c.trim()))).toEqual(new Set([action]));
  });

  test("[REAL] audit action filter finds older events stored in the backend", async ({ page }) => {
    test.fail(true, "[REAL] AuditComponent loads only the latest 20 events (no action_type/paging params) and filters " +
      "client-side, so filtering for older actions shows 'no results' even though the backend has them");
    const res = await gateway.get("/api/v1/admin/audit-logs", {
      headers: { Authorization: `Bearer ${token}` },
      params: { action_type: "user.suspended", per_page: "1" },
    });
    expect((await res.json()).total).toBeGreaterThan(0);
    for (let i = 0; i < 21; i++) {
      const flag = await createFlag();
      await deleteFlag(flag.id);
    }
    await page.getByRole("link", { name: "Audit Logs" }).click();
    await expect(page.locator("tr.mat-mdc-row").first()).toBeVisible();
    await page.getByLabel("Action").click();
    await page.getByRole("option", { name: "Suspend" }).click();
    await expect(page.locator("tr.mat-mdc-row").first()).toBeVisible({ timeout: 5_000 });
  });

  test("system health page shows service status via SPA navigation", async ({ page }) => {
    await page.getByRole("link", { name: "System Health" }).click();
    await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible();
    await expect(page.locator(".summary-card.healthy .summary-count")).not.toHaveText("0");
  });

  test("dashboard shows metrics summary cards", async ({ page }) => {
    await expect(page.locator("mat-card").first()).toBeVisible();
    await expect(page.getByText(/users/i).first()).toBeVisible();
  });

  test("[REAL] deep-linking /health renders the SPA health page", async ({ page }) => {
    test.fail(true, "[REAL] nginx location /health shadows the Angular /health route; reload shows raw JSON");
    await page.goto("/health");
    await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible({ timeout: 5_000 });
  });
});
