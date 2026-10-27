import { test as base, expect } from "@playwright/test";

type Customer = { email: string; displayName: string };

export const test = base.extend<{ customer: Customer }>({
  customer: async ({ page, request }, use) => {
    const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const customer = {
      email: `smoke-landing-${unique}@otterworks.test`,
      displayName: `Smoke Landing ${unique}`,
    };
    const registered = await request.post("/api/v1/auth/register", {
      data: { ...customer, password: "Passw0rd!23" },
    });
    expect(registered.ok()).toBeTruthy();
    const { accessToken, refreshToken } = await registered.json();

    const profile = await request.get("/api/v1/auth/profile", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(profile.ok()).toBeTruthy();
    expect((await profile.json()).email).toBe(customer.email);

    await page.addInitScript(
      ([access, refresh]) => {
        localStorage.setItem("otter_access_token", access);
        localStorage.setItem("otter_refresh_token", refresh);
      },
      [accessToken, refreshToken] as const,
    );
    await use(customer);
  },
});

export { expect };
