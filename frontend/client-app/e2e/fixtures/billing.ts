import { expect, type APIRequestContext } from "@playwright/test";

// 0001 is reserved for /billing/plans links; never point two fixtures at one tenant. Change-plan subscriptions accumulate, no cleanup API.
export const BILLING_TENANTS = {
  entitlement: "00000000-0000-0000-0000-000000000009",
  planChange: "00000000-0000-0000-0000-000000000008",
} as const;

export const ENTITLEMENT_DATE = "2026-02-28";

export type CatalogPlan = { plan_id: string; code: string };

export async function getBillingCatalog(
  request: APIRequestContext,
): Promise<CatalogPlan[]> {
  const response = await request.get("/billing-api/api/plans");
  await expect(response).toBeOK();
  return response.json();
}

export async function seedBillingCatalogIfEmpty(
  request: APIRequestContext,
): Promise<void> {
  let catalog = await getBillingCatalog(request);
  if (catalog.length === 0) {
    const reset = await request.post("/billing-api/internal/reset");
    expect(reset.status(), await reset.text()).toBe(204);
    catalog = await getBillingCatalog(request);
  }
  expect(
    catalog.length,
    "billing-service catalog is empty; POST /internal/reset seeds it",
  ).toBeGreaterThan(0);
}

export function uniqueEffectiveOn(): string {
  const day = new Date(Date.UTC(2100, 0, 1));
  day.setUTCDate(day.getUTCDate() + Math.floor(Math.random() * 300 * 365));
  return day.toISOString().slice(0, 10);
}
