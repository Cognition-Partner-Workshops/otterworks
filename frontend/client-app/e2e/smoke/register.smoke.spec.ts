import { test, expect, expectSignedInDashboard, loginStatusViaApi } from "../fixtures/signed-in";

test.describe("Register page (/register) smoke — signed in", () => {
  test("registering a new customer on /register from a signed-in browser creates the account and lands signed in as the new customer", async ({
    page,
    request,
    customer,
    newCustomerDetails,
  }) => {
    await test.step("Open /register while signed in as the fixture customer", async () => {
      await page.goto("/register");
      await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
    });

    await test.step("Register a brand-new customer", async () => {
      await page.getByLabel("Full name").fill(newCustomerDetails.displayName);
      await page.getByLabel("Email").fill(newCustomerDetails.email);
      await page.getByLabel("Password", { exact: true }).fill(newCustomerDetails.password);
      await page.getByLabel("Confirm password").fill(newCustomerDetails.password);
      await page.getByRole("button", { name: "Create account" }).click();
    });

    await test.step("The dashboard is signed in as the new customer", async () => {
      await expectSignedInDashboard(page, newCustomerDetails);
      await expect(page.getByRole("complementary").getByText(customer.email, { exact: true })).toHaveCount(0);
    });

    await test.step("The account exists in auth-service: its credentials sign in through the API", async () => {
      expect(await loginStatusViaApi(request, newCustomerDetails)).toBe(200);
    });
  });
});
