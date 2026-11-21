import { test, expect, expectSignedInDashboard } from "../fixtures/signed-in";

test.describe("Login page (/login) smoke — signed in", () => {
  test("signing in on /login from a signed-in browser authenticates the submitted customer and lands on their dashboard", async ({
    page,
    customer,
    secondCustomer,
  }) => {
    await test.step("Open /login while signed in as the fixture customer", async () => {
      await page.goto("/login");
      await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    });

    await test.step("Sign in with another registered customer's credentials", async () => {
      await page.getByLabel("Email").fill(secondCustomer.email);
      await page.getByLabel("Password").fill(secondCustomer.password);
      await page.getByRole("button", { name: "Sign in" }).click();
    });

    await test.step("The dashboard is signed in as the customer who just signed in", async () => {
      await expectSignedInDashboard(page, secondCustomer);
      await expect(page.getByRole("complementary").getByText(customer.email, { exact: true })).toHaveCount(0);
    });

    await test.step("The new session survives a reload", async () => {
      await page.reload();
      await expectSignedInDashboard(page, secondCustomer);
    });
  });
});
