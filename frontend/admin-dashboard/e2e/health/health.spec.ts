import { type Page } from "@playwright/test";
import { test, expect, details } from "../support/admin-session";

interface Probe { name: string; status: string }
interface Health { services: Probe[]; database?: { status: string }; redis?: { status: string } }

async function expectHealth(page: Page, health: Health): Promise<void> {
  const statuses = health.services.map(s => ({
    name: s.name, status: s.status === "healthy" ? "healthy" : s.status === "unhealthy" ? "down" : "degraded",
  }));
  for (const [key, name] of [["database", "postgres"], ["redis", "redis"]] as const) {
    const probe = health[key];
    if (probe) statuses.push({ name, status: probe.status === "healthy" ? "healthy" : "down" });
  }
  for (const service of statuses) {
    // Material health cards have no region role; status badges have no status role.
    const card = page.locator("mat-card").filter({ has: page.getByRole("heading", { name: service.name, exact: true }) });
    await expect(card.getByText(service.status.toUpperCase(), { exact: true })).toBeVisible();
  }
  for (const [status, icon, label] of [["healthy", "check_circle", "Healthy"], ["degraded", "warning", "Degraded"], ["down", "error", "Down"]]) {
    const count = statuses.filter(s => s.status === status).length;
    // Summary divs have no role and concatenate decorative icon ligatures with count/label.
    await expect(page.getByText(new RegExp(`^${icon}\\s*${count}\\s*${label}$`))).toBeVisible();
  }
}

test("ADM-HLTH-001 compare health cards and totals with live probes", details("ADM-HLTH-001", "health", "health"), async ({ page, request, adminSession }) => {
  await test.step("Fetch live health and open the health screen", async () => {
    const response = await request.get("/api/v1/admin/health/services", { headers: adminSession.headers });
    await expect(response).toBeOK();
    const health: Health = await response.json();
    await page.goto("/health");
    await expectHealth(page, health);
  });
});

test("ADM-HLTH-002 refresh the live health display", details("ADM-HLTH-002", "health", "health"), async ({ page, adminSession }) => {
  const initial = page.waitForResponse(r => r.url().endsWith("/api/v1/admin/health/services") && r.request().method() === "GET");
  await page.goto("/health");
  const initialResponse = await initial;
  expect(initialResponse.status()).toBe(200);
  await expectHealth(page, await initialResponse.json());
  await test.step("Refresh and compare the newly returned probe results", async () => {
    const response = page.waitForResponse(r => r.url().endsWith("/api/v1/admin/health/services") && r.request().method() === "GET");
    await page.getByRole("button", { name: /Refresh/ }).click();
    const refreshed = await response;
    expect(refreshed.status()).toBe(200);
    await expectHealth(page, await refreshed.json());
  });
});
