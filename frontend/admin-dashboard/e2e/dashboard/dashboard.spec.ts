import { test, expect, details } from "../support/admin-session";

test("ADM-DASH-001 read the real total user count", details("ADM-DASH-001", "dashboard", "dashboard"), async ({ page, adminSession }) => {
  await test.step("Open the dashboard and compare its total with its live API snapshot", async () => {
    const summary = page.waitForResponse(r => r.url().endsWith("/api/v1/admin/metrics/summary") && r.request().method() === "GET");
    await page.goto("/");
    const response = await summary;
    expect(response.status()).toBe(200);
    const metrics = await response.json();
    // Metric cards lack a region role and the Total Users label/value have no semantic roles.
    const card = page.locator("mat-card").filter({ has: page.getByText("Total Users", { exact: true }) });
    await expect(card.getByText(Number(metrics.users.total).toLocaleString("en-US"), { exact: true })).toBeVisible();
  });
});
