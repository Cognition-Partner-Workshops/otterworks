import { test as base, expect } from "@playwright/test";

export type Customer = { email: string; displayName: string };
export type CatalogPlan = { plan_id: string; code: string };

export const test = base.extend<{ customer: Customer; billingCatalog: CatalogPlan[] }>({
  customer: async ({ page, request }, use) => {
    const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const customer = {
      email: `smoke-billing-plans-${suffix}@otterworks.test`,
      displayName: `Billing Plans ${suffix}`,
    };
    const response = await request.post("/api/v1/auth/register", {
      data: { ...customer, password: "Passw0rd!23" },
    });
    expect(response.ok(), `register ${response.status()}`).toBe(true);
    const { accessToken, refreshToken } = await response.json();
    await page.addInitScript(
      ([access, refresh]) => {
        localStorage.setItem("otter_access_token", access);
        localStorage.setItem("otter_refresh_token", refresh);
      },
      [accessToken, refreshToken],
    );
    await use(customer);
  },

  billingCatalog: async ({ request }, use) => {
    const response = await request.get("/billing-api/api/plans");
    expect(response.ok(), `billing plans ${response.status()}`).toBe(true);
    const plans: CatalogPlan[] = await response.json();
    expect(plans.length, "billing-service catalog is empty; POST /internal/reset seeds it").toBeGreaterThan(0);
    await use(plans);
  },
});

export { expect };
