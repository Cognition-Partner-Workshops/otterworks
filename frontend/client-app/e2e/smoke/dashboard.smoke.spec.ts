import { test, expect } from "./dashboard.fixtures";

test("dashboard shows the signed-in customer's recent documents", {
  tag: ["@smoke", "@page-dashboard"],
  annotation: { type: "route", description: "/dashboard" },
}, async ({ page, dashboardCustomer }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent documents" })).toBeVisible();
  await expect(page.getByRole("link", { name: dashboardCustomer.documentTitle })).toHaveAttribute("href", /^\/documents\/.+/);
});
