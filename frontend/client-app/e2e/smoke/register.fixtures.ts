import { test as base, expect } from "@playwright/test";

export type Identity = { displayName: string; email: string; password: string };

export function uniqueIdentity(label: string): Identity {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  return {
    displayName: `Smoke ${label} ${id}`,
    email: `smoke-${label}-${id}@otterworks.test`,
    password: "Passw0rd!23",
  };
}

export const test = base.extend<{ customer: Identity }>({
  customer: async ({ request, context }, use) => {
    const customer = uniqueIdentity("customer");
    const response = await request.post("/api/v1/auth/register", { data: customer });
    expect(response.ok()).toBeTruthy();
    const { accessToken, refreshToken } = await response.json();
    await context.addInitScript(
      ([access, refresh]) => {
        if (!localStorage.getItem("otter_access_token")) {
          localStorage.setItem("otter_access_token", access);
          localStorage.setItem("otter_refresh_token", refresh);
        }
      },
      [accessToken, refreshToken],
    );
    await use(customer);
  },
});

export { expect };
