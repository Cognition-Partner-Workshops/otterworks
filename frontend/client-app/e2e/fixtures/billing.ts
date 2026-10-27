import { expect, type APIRequestContext } from "@playwright/test";
import pg from "pg";

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

export async function seedBillingCatalog(
  request: APIRequestContext,
): Promise<void> {
  const client = new pg.Client({
    connectionString: process.env.BILLING_DB_URL ||
      "postgresql://billing_svc:billing_svc@127.0.0.1:56432/billing_svc_dev",
  });
  await client.connect();
  try {
    await client.query(`
      INSERT INTO billing_svc.plans
        (id, code, tier, monthly_fee, included_units, overage_rate) VALUES
        ('10000000-0000-0000-0000-000000000001', 'STARTER', 'starter', 49.00, 100, 0.055000),
        ('10000000-0000-0000-0000-000000000002', 'GROWTH', 'growth', 149.00, 500, 0.035000),
        ('10000000-0000-0000-0000-000000000003', 'SCALE', 'scale', 499.00, 2000, 0.020000)
      ON CONFLICT DO NOTHING;
      INSERT INTO billing_svc.tenants (id, name, tax_exempt, status) VALUES
        ('00000000-0000-0000-0000-000000000001', 'Tenant One', false, 'active'),
        ('00000000-0000-0000-0000-000000000008', 'Tenant Eight', false, 'active'),
        ('00000000-0000-0000-0000-000000000009', 'Tenant Nine', false, 'active')
      ON CONFLICT DO NOTHING;
      INSERT INTO billing_svc.subscriptions
        (id, tenant_id, plan_id, starts_on, ends_on, status, suspended_on) VALUES
        ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001',
         '10000000-0000-0000-0000-000000000001', '2026-01-01', NULL, 'active', NULL),
        ('20000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000008',
         '10000000-0000-0000-0000-000000000001', '2026-01-01', NULL, 'active', NULL),
        ('20000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000009',
         '10000000-0000-0000-0000-000000000001', '2026-01-01', NULL, 'active', NULL)
      ON CONFLICT DO NOTHING;
    `);
  } finally {
    await client.end();
  }
  const catalog = await getBillingCatalog(request);
  expect(
    catalog.length,
    "billing-service catalog is empty: plans exist but are inactive; the suite will not modify them",
  ).toBeGreaterThan(0);
}

export function uniqueEffectiveOn(): string {
  const day = new Date(Date.UTC(2100, 0, 1));
  day.setUTCDate(day.getUTCDate() + Math.floor(Math.random() * 300 * 365));
  return day.toISOString().slice(0, 10);
}
