import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type Customer = { email: string; headers: { Authorization: string } };

export const test = base.extend<{ customer: Customer }>({
  customer: async ({ request, page }, use) => {
    const email = `margins-smoke-${randomUUID()}@example.com`;
    const registration = await request.post("/api/v1/auth/register", {
      data: { displayName: "Margins Smoke", email, password: "Margins-Smoke-2026!" },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken } = await registration.json();
    await page.addInitScript(
      (tokens) => {
        localStorage.setItem("otter_access_token", tokens.accessToken);
        localStorage.setItem("otter_refresh_token", tokens.refreshToken);
      },
      { accessToken, refreshToken },
    );
    await use({ email, headers: { Authorization: `Bearer ${accessToken}` } });
  },
});

export { expect };
