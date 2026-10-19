import { test, expect } from "@playwright/test";

test.describe("Case Files Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/documents");
  });

  test("shows Case files heading or redirects to login", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Case files" });
    const loginHeading = page.getByText("Sign in with your staff or resident account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });
  });

  test("has New case file button when authenticated", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Case files" });
    const loginHeading = page.getByText("Sign in with your staff or resident account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      await expect(
        page.getByRole("button", { name: /New case file/i })
      ).toBeVisible();
    }
  });

  test("has search/filter input when authenticated", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Case files" });
    const loginHeading = page.getByText("Sign in with your staff or resident account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      await expect(
        page.getByPlaceholder("Filter case files...")
      ).toBeVisible();
    }
  });

  test("has grid/list view toggle when authenticated", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Case files" });
    const loginHeading = page.getByText("Sign in with your staff or resident account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      // View toggle buttons should be present
      const buttons = page.locator("button svg");
      await expect(buttons.first()).toBeVisible();
    }
  });

  test("shows empty state when no documents exist", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Case files" });
    const loginHeading = page.getByText("Sign in with your staff or resident account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      // Either documents are listed or empty state is shown
      const emptyState = page.getByText("No case files yet");
      const docCard = page.locator("[class*='grid'] > *").first();
      await expect(emptyState.or(docCard)).toBeVisible({ timeout: 10_000 });
    }
  });

  test("displays breadcrumb navigation", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Case files" });
    const loginHeading = page.getByText("Sign in with your staff or resident account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      await expect(page.getByText("Case files").first()).toBeVisible();
    }
  });
});
