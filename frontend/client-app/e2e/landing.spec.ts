import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("displays the hero section with branding", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Careotter" })).toBeVisible();
    await expect(
      page.getByText("Patient records management for modern medical practices")
    ).toBeVisible();
  });

  test("shows Sign In and Create Account CTAs", async ({ page }) => {
    await expect(page.getByRole("link", { name: "Sign In" })).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Create Account" })
    ).toBeVisible();
  });

  test("renders all six feature cards", async ({ page }) => {
    const features = [
      "Patient Records",
      "Chart Editing",
      "Care Team Collaboration",
      "Powerful Search",
      "HIPAA-Ready Sharing",
      "Instant Notifications",
    ];
    for (const title of features) {
      await expect(page.getByText(title, { exact: true })).toBeVisible();
    }
  });

  test("Sign In link navigates to /login", async ({ page }) => {
    await page.getByRole("link", { name: "Sign In" }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("Create Account link navigates to /register", async ({ page }) => {
    await page.getByRole("link", { name: "Create Account" }).click();
    await expect(page).toHaveURL(/\/register/);
  });

  test("footer is visible with copyright text", async ({ page }) => {
    await expect(
      page.getByText("Patient records management for doctor offices")
    ).toBeVisible();
  });
});
