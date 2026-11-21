import { test, expect } from "../fixtures/fixtures";

test(
  "signed-in customer can sign in again from /login and reach the dashboard",
  {
    tag: ["@smoke", "@page-login"],
    annotation: { type: "route", description: "/login" },
  },
  async ({ page, customer }) => {
    await page.goto("/login");
    // Precondition: the customer's session is already in localStorage (no redirect away from /login exists).
    expect(await page.evaluate(() => localStorage.getItem("otter_access_token"))).toBe(customer.accessToken);

    await page.getByLabel("Email").fill(customer.email);
    await page.getByLabel("Password").fill(customer.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  },
);
