import { test as base, expect } from "@playwright/test";

type Customer = { email: string; displayName: string };
type PlanChange = { tenantId: string; planCode: string; effectiveOn: string };

// billing-service has no tenant-create endpoint; this is a seeded tenant
// (services/billing-service/db/seed.sql) that the /billing/plans links do not use.
const SEEDED_TENANT_ID = "00000000-0000-0000-0000-000000000008";

function uniqueSuffix(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// A far-future date unique per run: the service derives the subscription id from
// tenant+plan+date, so reusing a date would return 409 on the next run.
function uniqueEffectiveOn(): string {
  const day = new Date(Date.UTC(2100, 0, 1));
  day.setUTCDate(day.getUTCDate() + Math.floor(Math.random() * 300 * 365));
  return day.toISOString().slice(0, 10);
}

export const test = base.extend<{ customer: Customer; planChange: PlanChange }>({
  customer: async ({ page, request }, use) => {
    const suffix = uniqueSuffix();
    const customer = {
      email: `smoke-billing-change-${suffix}@otterworks.test`,
      displayName: `Smoke Billing ${suffix}`,
    };
    const response = await request.post("/api/v1/auth/register", {
      data: { ...customer, password: "Passw0rd!234" },
    });
    expect(response.status(), await response.text()).toBe(201);
    const tokens: { accessToken: string; refreshToken: string } = await response.json();
    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);
    await use(customer);
  },
  planChange: async ({}, use) => {
    await use({ tenantId: SEEDED_TENANT_ID, planCode: "GROWTH", effectiveOn: uniqueEffectiveOn() });
  },
});

export { expect };
