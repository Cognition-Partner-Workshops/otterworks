import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

export type Customer = { email: string; displayName: string };

export const test = base.extend<{ customer: Customer }>({
  customer: async ({ request, page }, use) => {
    const customer = {
      email: `legal-smoke-${randomUUID()}@example.com`,
      displayName: `Legal Smoke ${randomUUID().slice(0, 8)}`,
    };
    const registration = await request.post("/api/v1/auth/register", {
      data: { ...customer, password: "Legal-Smoke-2026!" },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken } = await registration.json();
    const profile = await request.get("/api/v1/auth/profile", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    await expect(profile).toBeOK();
    expect((await profile.json()).email).toBe(customer.email);
    await page.addInitScript((tokens) => {
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
    }, { accessToken, refreshToken });
    await use(customer);
  },
});

export { expect };
