import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

export type Customer = { displayName: string; email: string };

export const test = base.extend<{ customer: Customer }>({
  customer: async ({ request, page }, use) => {
    const id = randomUUID();
    const customer = { displayName: `Settings Smoke ${id.slice(0, 8)}`, email: `settings-smoke-${id}@example.com` };
    const registration = await request.post("/api/v1/auth/register", {
      data: { ...customer, password: "Settings-Smoke-2026!" },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken } = await registration.json();
    await page.addInitScript((tokens) => {
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
    }, { accessToken, refreshToken });
    await use(customer);
  },
});

export { expect };
