import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { test as base, expect, type APIRequestContext } from "@playwright/test";

const API_GATEWAY_URL = process.env.API_GATEWAY_URL || "http://localhost:8080";
const BILLING_DB_CONTAINER =
  process.env.BILLING_DB_CONTAINER || "otterworks-billing-service-db-1";

export type Customer = {
  displayName: string;
  email: string;
  password: string;
  accessToken: string;
  refreshToken: string;
};

export type BillingPlan = {
  plan_id: string;
  code: string;
  tier: string;
  monthly_fee: string;
  included_units: number;
  overage_rate: string;
};

export type BillingTenant = {
  tenantId: string;
  name: string;
  plan: BillingPlan;
  startsOn: string;
};

type Fixtures = {
  customer: Customer;
  billingPlans: BillingPlan[];
  billingTenant: BillingTenant;
};

async function registerCustomer(request: APIRequestContext): Promise<Customer> {
  const suffix = randomUUID();
  const displayName = `Smoke Margins ${suffix.slice(0, 8)}`;
  const email = `smoke-margins-billing-${suffix}@otterworks.test`;
  const password = "Passw0rd!23";

  const registered = await request.post(`${API_GATEWAY_URL}/api/v1/auth/register`, {
    data: { displayName, email, password },
  });
  expect(registered.status(), await registered.text()).toBe(201);
  const { accessToken, refreshToken } = await registered.json();

  const profile = await request.get(`${API_GATEWAY_URL}/api/v1/auth/profile`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  expect(profile.status()).toBe(200);
  expect(await profile.json()).toMatchObject({ email, displayName });

  return { displayName, email, password, accessToken, refreshToken };
}

export const test = base.extend<Fixtures>({
  // A fresh customer per test, registered through the real API gateway.
  customer: async ({ request }, use) => {
    await use(await registerCustomer(request));
  },

  // Every page opens signed in: the customer's real tokens are in localStorage
  // before the app boots, under the keys the AuthProvider reads.
  page: async ({ page, customer }, use) => {
    await page.addInitScript(
      ({ accessToken, refreshToken }) => {
        localStorage.setItem("otter_access_token", accessToken);
        localStorage.setItem("otter_refresh_token", refreshToken);
      },
      { accessToken: customer.accessToken, refreshToken: customer.refreshToken },
    );
    await use(page);
  },

  billingPlans: async ({ request }, use) => {
    const response = await request.get("/billing-api/api/plans");
    expect(response.status()).toBe(200);
    const plans: BillingPlan[] = await response.json();
    expect(plans.length).toBeGreaterThan(1);
    await use(plans);
  },

  // A tenant of our own, on the first catalogue plan from 2026-01-01.
  // billing-service has no public tenant-creation endpoint, so the tenant row
  // is INSERTed (insert-only, unique id and name) into the billing DB; its
  // subscription is created through the public plan-change API.
  billingTenant: async ({ request, billingPlans }, use) => {
    const tenantId = randomUUID();
    const name = `smoke-margins-billing-${tenantId}`;
    execFileSync("docker", [
      "exec",
      BILLING_DB_CONTAINER,
      "psql",
      "-U",
      "billing_svc",
      "-d",
      "billing_svc_dev",
      "-v",
      "ON_ERROR_STOP=1",
      "-c",
      `INSERT INTO billing_svc.tenants (id, name, tax_exempt, status) VALUES ('${tenantId}', '${name}', false, 'active');`,
    ]);

    const plan = billingPlans[0];
    const startsOn = "2026-01-01";
    const created = await request.post(
      `/billing-api/api/tenants/${tenantId}/plan-change`,
      { data: { plan_id: plan.plan_id, effective_on: startsOn } },
    );
    expect(created.status(), await created.text()).toBe(200);
    expect(await created.json()).toMatchObject({
      latest_plan: plan.plan_id,
      latest_start: startsOn,
    });

    await use({ tenantId, name, plan, startsOn });
  },
});

export { expect };
