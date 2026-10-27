import { test, expect } from "./landing.fixtures";

test(
  "signed-in customer sees the OtterWorks corporate landing page",
  { tag: ["@smoke", "@page-landing"], annotation: { type: "route", description: "/" } },
  async ({ page, customer }) => {
    await page.goto("/");

    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { level: 1, name: "OtterWorks" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Products" })).toBeVisible();
  },
);
