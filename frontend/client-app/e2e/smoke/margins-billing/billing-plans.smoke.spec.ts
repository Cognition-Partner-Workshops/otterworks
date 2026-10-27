import { test, expect } from "./margins-billing.fixtures";

test.describe("Billing plans smoke (signed in)", () => {
  test("a signed-in customer sees every billing plan with its price and units", async ({
    page,
    billingPlans,
  }) => {
    await test.step("open /billing/plans as the signed-in customer", async () => {
      await page.goto("/billing/plans");
      await expect(page.getByRole("heading", { name: "Plans", level: 1 })).toBeVisible();
    });

    await test.step("each plan from the billing catalogue is listed", async () => {
      const list = page.getByRole("list", { name: "Available plans" });
      await expect(list.getByRole("listitem")).toHaveCount(billingPlans.length);
      for (const plan of billingPlans) {
        const card = list.getByRole("listitem").filter({
          has: page.getByRole("heading", { name: plan.code, exact: true }),
        });
        await expect(card).toContainText(plan.tier);
        await expect(card).toContainText(`$${plan.monthly_fee} / month`);
        await expect(card).toContainText(`${plan.included_units} included units`);
        await expect(card.getByRole("link", { name: "Choose plan" })).toBeVisible();
      }
    });
  });
});
