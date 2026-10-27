import { test, expect } from "../fixtures/signed-in";

test.describe("Billing entitlement smoke (signed in)", () => {
  test("a signed-in customer sees the entitlement of their own tenant", async ({
    page,
    billingTenant,
  }) => {
    const { tenantId, plan } = billingTenant;

    await test.step("open /billing/entitlement/:tenantId for the fixture tenant", async () => {
      await page.goto(`/billing/entitlement/${tenantId}`);
      await expect(page.getByRole("heading", { name: "Tenant entitlement", level: 1 })).toBeVisible();
    });

    await test.step("the tenant's plan, tier, status, units and effective date are shown", async () => {
      // The page asks for the entitlement on 2026-02-28; the fixture plan started 2026-01-01.
      await expect(page.getByRole("region", { name: "Tenant entitlement" })).toMatchAriaSnapshot(`
        - region "Tenant entitlement":
          - paragraph: Tenant ${tenantId}
          - heading "${plan.code}" [level=2]
          - term: Tier
          - definition: ${plan.tier}
          - term: Status
          - definition: active
          - term: Included units
          - definition: "${plan.included_units}"
          - term: Effective on
          - definition: 2026-02-28
          - link "Change plan"
      `);
    });
  });
});
