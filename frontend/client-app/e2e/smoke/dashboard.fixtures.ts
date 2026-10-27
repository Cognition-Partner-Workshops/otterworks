import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type DashboardCustomer = { documentTitle: string };

export const test = base.extend<{ dashboardCustomer: DashboardCustomer }>({
  dashboardCustomer: async ({ page, request }, use) => {
    const id = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: { displayName: "Dashboard Smoke", email: `dashboard-smoke-${id}@example.com`, password: "Dashboard-Smoke-2026!" },
    });
    await expect(registration).toBeOK();
    const tokens = await registration.json();
    const documentTitle = `Dashboard smoke ${id}`;
    const created = await request.post("/api/v1/documents", {
      headers: { Authorization: `Bearer ${tokens.accessToken}` },
      data: { title: documentTitle, content: "Seeded for the dashboard smoke test." },
    });
    await expect(created).toBeOK();
    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);
    await use({ documentTitle });
  },
});

export { expect };
