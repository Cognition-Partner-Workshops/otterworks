import { test, expect } from "../fixtures/fixtures";

test("settings shows the signed-in customer's profile", {
  tag: ["@smoke", "@page-settings"],
  annotation: { type: "route", description: "/settings" },
}, async ({ page, customer }) => {
  await page.goto("/settings");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
  await expect(main.getByLabel("Full name")).toHaveValue(customer.displayName);
  await expect(main.getByLabel("Email")).toHaveValue(customer.email);
  await expect(main.getByRole("heading", { name: "Notification preferences" })).toBeVisible();
});
