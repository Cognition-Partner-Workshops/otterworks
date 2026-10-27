import { test, expect } from "../fixtures/fixtures";

test("billing plans page lists every catalog plan with a Choose plan link", {
  tag: ["@smoke", "@page-billing-plans"],
  annotation: { type: "route", description: "/billing/plans" },
}, async ({ page, billingCatalog }) => {
  await page.goto("/billing/plans");

  await expect(page.getByRole("heading", { level: 1, name: "Plans" })).toBeVisible();
  const plans = page.getByRole("list", { name: "Available plans" });
  await expect(plans.getByRole("listitem")).toHaveCount(billingCatalog.length);
  for (const plan of billingCatalog) {
    const card = plans.getByRole("listitem").filter({ has: page.getByRole("heading", { name: plan.code, exact: true }) });
    await expect(card.getByRole("link", { name: "Choose plan" })).toHaveAttribute(
      "href",
      new RegExp(`\\?plan=${plan.plan_id}$`),
    );
  }
});
