import { BILLING_TENANTS, expect, test } from "../fixtures/fixtures";

test(
  "billing entitlement shows the tenant's current plan",
  {
    tag: ["@smoke", "@page-billing-entitlement"],
    annotation: { type: "route", description: "/billing/entitlement/:tenantId" },
  },
  async ({ page, tenantEntitlement }) => {
    await page.goto(`/billing/entitlement/${BILLING_TENANTS.entitlement}`);

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
