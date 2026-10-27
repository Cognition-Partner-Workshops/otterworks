import { test as base, expect } from "@playwright/test";

export type Customer = { displayName: string; email: string; password: string };

type AuthTokens = { accessToken: string; refreshToken: string };

export const test = base.extend<{ customer: Customer; customerTokens: AuthTokens }>({
  customer: async ({}, use, testInfo) => {
    const id = `${Date.now()}-${testInfo.workerIndex}-${Math.random().toString(36).slice(2, 8)}`;
    await use({
      displayName: `Smoke Login ${id}`,
      email: `smoke-login-${id}@otterworks.test`,
      password: "Passw0rd!23",
    });
  },

  customerTokens: async ({ playwright, baseURL, customer }, use) => {
    const api = await playwright.request.newContext({ baseURL });
    const response = await api.post("/api/v1/auth/register", { data: customer });
    expect(response.status(), await response.text()).toBe(201);
    const tokens = (await response.json()) as AuthTokens;
    await api.dispose();
    await use(tokens);
  },

  storageState: async ({ baseURL, customerTokens }, use) => {
    await use({
      cookies: [],
      origins: [
        {
          origin: new URL(baseURL!).origin,
          localStorage: [
            { name: "otter_access_token", value: customerTokens.accessToken },
            { name: "otter_refresh_token", value: customerTokens.refreshToken },
          ],
        },
      ],
    });
  },
});

export { expect };
