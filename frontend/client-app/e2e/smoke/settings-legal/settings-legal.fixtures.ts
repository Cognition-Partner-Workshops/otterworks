import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

export type Customer = {
  id: string;
  email: string;
  displayName: string;
  password: string;
  accessToken: string;
  refreshToken: string;
};

type SettingsLegalFixtures = {
  customer: Customer;
};

export { expect };

export const test = base.extend<SettingsLegalFixtures>({
  customer: async ({ request, baseURL }, use) => {
    const suffix = randomUUID();
    const displayName = `Smoke Settings ${suffix.slice(0, 8)}`;
    const email = `smoke-settings-legal-${suffix}@otterworks.test`;
    const password = `Pw-${suffix}`;
    const response = await request.post(
      new URL("/api/v1/auth/register", baseURL!).toString(),
      {
        data: { displayName, email, password },
      },
    );
    const responseText = await response.text();

    expect(response.status(), `Registration response: ${responseText}`).toBe(201);

    const body = JSON.parse(responseText) as {
      accessToken: string;
      refreshToken: string;
      user: { id: string; email: string; displayName: string };
    };
    expect(body.accessToken).toBeTruthy();
    expect(body.refreshToken).toBeTruthy();
    expect(body.user.id).toBeTruthy();
    expect(body.user).toMatchObject({ email, displayName });

    const profileResponse = await request.get(
      new URL("/api/v1/auth/profile", baseURL!).toString(),
      {
        headers: { Authorization: `Bearer ${body.accessToken}` },
      },
    );
    expect(profileResponse.status(), await profileResponse.text()).toBe(200);

    await use({
      id: body.user.id,
      email,
      displayName,
      password,
      accessToken: body.accessToken,
      refreshToken: body.refreshToken,
    });
  },
  storageState: async ({ customer, baseURL }, use) => {
    await use({
      cookies: [],
      origins: [
        {
          origin: new URL(baseURL!).origin,
          localStorage: [
            { name: "otter_access_token", value: customer.accessToken },
            { name: "otter_refresh_token", value: customer.refreshToken },
          ],
        },
      ],
    });
  },
});
