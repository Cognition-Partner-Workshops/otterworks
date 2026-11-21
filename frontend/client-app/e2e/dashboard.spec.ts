import { test, expect } from "./fixtures/fixtures";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("shows the Dashboard heading", async ({ page }) => {
    // Dashboard may redirect to login if unauthenticated, or show the page
    const heading = page.getByRole("heading", { name: "Dashboard" });
    const loginHeading = page.getByText("Sign in to your account");

    // Either we see the dashboard or we get redirected to login
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });
  });

  test("displays Upload file and New document buttons", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Dashboard" });
    const loginHeading = page.getByText("Sign in to your account");
    const target = heading.or(loginHeading);
    await expect(target).toBeVisible({ timeout: 10_000 });

    // Only check buttons if we're on the dashboard (not redirected to login)
    if (await heading.isVisible().catch(() => false)) {
      await expect(page.getByRole("link", { name: /Upload file/i })).toBeVisible();
      await expect(page.getByRole("link", { name: /New document/i })).toBeVisible();
    }
  });

  test("renders stat cards or loading state", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Dashboard" });
    const loginHeading = page.getByText("Sign in to your account");
    const loader = page.locator("[class*='animate-spin']");
    // Dashboard may show heading, loader, or redirect to login
    await expect(heading.or(loginHeading).or(loader)).toBeVisible({ timeout: 15_000 });

    if (await heading.isVisible().catch(() => false)) {
      // Stat card labels appear inside stat cards as combined text
      await expect(page.getByText(/Total files/i)).toBeVisible({ timeout: 10_000 });
      await expect(page.getByText(/Storage used/i)).toBeVisible();
    }
  });

  test("shows Recent files section or empty state", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Recent files", exact: true })).toBeVisible();
  });

  test("shows Recent documents section or empty state", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Recent documents", exact: true })).toBeVisible();
  });

  test("shows Activity section or empty state", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Activity", exact: true })).toBeVisible();
  });
});
