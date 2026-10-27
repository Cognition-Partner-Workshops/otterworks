import { test as base, expect, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import type { Entitlement } from "../../src/features/billing/api";

// billing-service has no tenant-create API; tenants exist only in its deterministic seed
// (services/billing-service/db/seed.sql), loaded by POST /internal/reset. Tenant Nine: STARTER.
export const SEEDED_TENANT_ID = "00000000-0000-0000-0000-000000000009";
// entitlement-page.tsx always asks for the entitlement on this date.
const ENTITLEMENT_DATE = "2026-02-28";

async function registerCustomer(request: APIRequestContext) {
  const id = randomUUID();
  const response = await request.post("/api/v1/auth/register", {
    data: {
      displayName: `Smoke Entitlement ${id.slice(0, 8)}`,
      email: `smoke-entitlement-${id}@example.test`,
      password: `Smoke-${id}!`,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()) as { accessToken: string; refreshToken: string };
}

export const test = base.extend<{ customer: void; tenantEntitlement: Entitlement }>({
  customer: async ({ page, request }, use) => {
    const tokens = await registerCustomer(request);
    await page.addInitScript(([access, refresh]) => {
      localStorage.setItem("otter_access_token", access);
      localStorage.setItem("otter_refresh_token", refresh);
    }, [tokens.accessToken, tokens.refreshToken]);
    await use();
  },
  tenantEntitlement: async ({ request }, use) => {
    const url = `/billing-api/api/tenants/${SEEDED_TENANT_ID}/entitlement?on=${ENTITLEMENT_DATE}`;
    let response = await request.get(url);
    // A fresh billing-service starts empty; seed it once, but never wipe data that already exists.
    if (response.status() === 404) {
      const reset = await request.post("/billing-api/internal/reset");
      expect(reset.status(), await reset.text()).toBe(204);
      response = await request.get(url);
    }
    expect(response.ok(), await response.text()).toBe(true);
    await use((await response.json()) as Entitlement);
  },
});

export { expect };
