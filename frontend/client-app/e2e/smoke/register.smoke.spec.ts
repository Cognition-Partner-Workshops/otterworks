import { test, expect, uniqueIdentity } from "./register.fixtures";

test(
  "signed-in customer creates a new account on /register and lands on its dashboard",
  {
    tag: ["@smoke", "@page-register"],
    annotation: { type: "route", description: "/register" },
  },
  async ({ page, customer }) => {
    const newAccount = uniqueIdentity("register");
    const sessionLoaded = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/auth/profile") && r.ok(),
    );

    await page.goto("/register");
    await sessionLoaded;

    await page.getByLabel("Full name").fill(newAccount.displayName);
    await page.getByLabel("Email").fill(newAccount.email);
    await page.getByLabel("Password", { exact: true }).fill(newAccount.password);
    await page.getByLabel("Confirm password").fill(newAccount.password);
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
    // Sidebar profile block has no landmark or accessible name; the unique email is its only handle.
    await expect(page.getByText(newAccount.email)).toBeVisible();
    await expect(page.getByText(customer.email)).toHaveCount(0);
  },
);
