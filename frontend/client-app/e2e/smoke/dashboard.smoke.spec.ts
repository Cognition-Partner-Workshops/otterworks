import { test, expect } from "../fixtures/fixtures";

// own customer: the Recent documents widget shows only getRecent(6) and parallel tests add documents to the shared customer
test.use({ freshCustomer: true });

test("dashboard shows the signed-in customer's recent documents", {
  tag: ["@smoke", "@page-dashboard"],
  annotation: { type: "route", description: "/dashboard" },
}, async ({ page, document }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent documents" })).toBeVisible();
  await expect(page.getByRole("link", { name: document.title })).toHaveAttribute("href", /^\/documents\/.+/);
});
