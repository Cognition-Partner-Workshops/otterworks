import { test, expect } from "../fixtures/fixtures";

test(
  "billing-change-plan: a signed-in customer saves a plan change for a tenant",
  {
    tag: ["@smoke", "@page-billing-change-plan"],
    annotation: { type: "route", description: "/billing/change/:tenantId" },
  },
  async ({ page, request, planChange }) => {
    await page.goto(`/billing/change/${planChange.tenantId}`);
    await expect(page.getByRole("heading", { name: "Change plan" })).toBeVisible();

    await page.getByLabel("Plan").selectOption({ label: planChange.planCode });
    await page.getByLabel("Effective date").fill(planChange.effectiveOn);
    await page.getByRole("button", { name: "Save plan change" }).click();

    await expect(page.getByRole("status")).toHaveText(
      `Plan change saved for ${planChange.effectiveOn}.`,
    );
    const entitlement = await request.get(
      `/billing-api/api/tenants/${planChange.tenantId}/entitlement?on=${planChange.effectiveOn}`,
    );
    expect(await entitlement.json()).toMatchObject({ plan_code: planChange.planCode });
  },
);
