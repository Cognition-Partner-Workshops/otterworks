import { test, expect, SEEDED_TENANT_ID } from "./billing-entitlement.fixtures";

test(
  "billing entitlement shows the tenant's current plan",
  {
    tag: ["@smoke", "@page-billing-entitlement"],
    annotation: { type: "route", description: "/billing/entitlement/:tenantId" },
  },
  async ({ page, customer: _customer, tenantEntitlement }) => {
    await page.goto(`/billing/entitlement/${SEEDED_TENANT_ID}`);

    const card = page.getByRole("region", { name: "Tenant entitlement" });
    await expect(card.getByRole("heading", { name: tenantEntitlement.plan_code })).toBeVisible();
    await expect(card.getByRole("definition")).toHaveText([
      tenantEntitlement.tier,
      tenantEntitlement.subscription_status,
      String(tenantEntitlement.included_units),
      tenantEntitlement.effective_on,
    ]);
  },
);
