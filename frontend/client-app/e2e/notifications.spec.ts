import { test, expect } from "./fixtures/signed-in";

test.describe("Notifications Page", () => {
  test.beforeEach(async ({ page }) => {
    await test.step("open /notifications as a signed-in customer", async () => {
      await page.goto("/notifications");
    });
  });

  test("shows Notifications heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Notifications", exact: true })
    ).toBeVisible();
  });

  test.describe("empty inbox", () => {
    test.use({ account: "fresh" });

    test("shows the empty state to a customer with no notifications", async ({ page }) => {
      const main = page.getByRole("main");
      await expect(main.getByText("No notifications", { exact: true })).toBeVisible();
      await expect(
        main.getByText("You're all caught up! New notifications will appear here.")
      ).toBeVisible();
      await expect(main.getByText(/unread notification/)).toHaveCount(0);
    });
  });
});

test.describe("Notifications Page (signed out)", () => {
  test.use({ account: "signedOut" });

  test("sends a signed-out visitor to the sign-in page", async ({ page }) => {
    await test.step("open /notifications without a session", async () => {
      await page.goto("/notifications");
    });

    await test.step("the visitor lands on /login", async () => {
      await expect(page).toHaveURL(/\/login$/);
      await expect(page.getByText("Sign in to your account")).toBeVisible();
    });
  });
});
