import { test, expect, expectSignedInDashboard } from "./auth-landing.fixtures";

test.describe("Landing page (/) smoke — signed in", () => {
  test("a signed-in customer opening / sees the OtterWorks corporate front page with its Sign In and Create Account entry points, and stays signed in", async ({
    page,
    customer,
  }) => {
    await test.step("Open / as the signed-in customer", async () => {
      await page.goto("/");
    });

    await test.step("The corporate hero introduces OtterWorks", async () => {
      await expect(page.getByRole("heading", { name: "OtterWorks", exact: true, level: 1 })).toBeVisible();
      await expect(page.getByText("Enterprise retail products for otters", { exact: true })).toBeVisible();
      for (const section of ["Our Story", "Products", "Leadership", "Departments", "Newsroom", "Careers"]) {
        await expect(page.getByRole("heading", { name: section, exact: true, level: 2 })).toBeVisible();
      }
    });

    await test.step("The header offers Sign In (/login) and Create Account (/register)", async () => {
      const nav = page.getByRole("navigation");
      await expect(nav.getByRole("link", { name: "Sign In" })).toHaveAttribute("href", "/login");
      await expect(nav.getByRole("link", { name: "Create Account" })).toHaveAttribute("href", "/register");
    });

    await test.step("Visiting the landing page keeps the customer's session", async () => {
      await page.goto("/dashboard");
      await expectSignedInDashboard(page, customer);
    });
  });
});
