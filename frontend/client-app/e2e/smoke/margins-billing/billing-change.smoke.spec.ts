import { test, expect } from "./margins-billing.fixtures";

test.describe("Billing change plan smoke (signed in)", () => {
  test("a signed-in customer changes their tenant's plan and the change is saved", async ({
    page,
    request,
    billingTenant,
    billingPlans,
  }) => {
    const { tenantId, plan: currentPlan } = billingTenant;
    const newPlan = billingPlans.find((plan) => plan.plan_id !== currentPlan.plan_id)!;
    const effectiveOn = "2026-04-01";

    await test.step("open /billing/change/:tenantId for the fixture tenant", async () => {
      await page.goto(`/billing/change/${tenantId}`);
      await expect(page.getByRole("heading", { name: "Change plan", level: 1 })).toBeVisible();
      await expect(page.getByLabel("Plan")).toBeVisible();
    });

    await test.step(`choose ${newPlan.code} from ${effectiveOn} and save`, async () => {
      await page.getByLabel("Plan").selectOption({ label: newPlan.code });
      await page.getByLabel("Effective date").fill(effectiveOn);
      await page.getByRole("button", { name: "Save plan change" }).click();
      await expect(page.getByRole("status")).toHaveText(`Plan change saved for ${effectiveOn}.`);
      await expect(page.getByRole("alert")).toHaveCount(0);
    });

    await test.step("the billing service now entitles the tenant to the new plan", async () => {
      const response = await request.get(
        `/billing-api/api/tenants/${tenantId}/entitlement?on=${effectiveOn}`,
      );
      expect(response.status()).toBe(200);
      expect(await response.json()).toMatchObject({
        tenant_id: tenantId,
        plan_code: newPlan.code,
        subscription_status: "active",
      });
    });
  });
});
