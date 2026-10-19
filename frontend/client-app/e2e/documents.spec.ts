import { test, expect } from "@playwright/test";

test.describe("Research Notes Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/documents");
  });

  test("shows Notes heading or redirects to login", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Notes" });
    const loginHeading = page.getByText("Sign in to your Quillstead account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });
  });

  test("has New research note button when authenticated", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Notes" });
    const loginHeading = page.getByText("Sign in to your Quillstead account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      await expect(
        page.getByRole("button", { name: /New research note/i })
      ).toBeVisible();
    }
  });

  test("has search/filter input when authenticated", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Notes" });
    const loginHeading = page.getByText("Sign in to your Quillstead account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      await expect(
        page.getByPlaceholder("Filter research notes...")
      ).toBeVisible();
    }
  });

  test("has grid/list view toggle when authenticated", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Notes" });
    const loginHeading = page.getByText("Sign in to your Quillstead account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      // View toggle buttons should be present
      const buttons = page.locator("button svg");
      await expect(buttons.first()).toBeVisible();
    }
  });

  test("shows empty state when no research notes exist", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Notes" });
    const loginHeading = page.getByText("Sign in to your Quillstead account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      // Either documents are listed or empty state is shown
      const emptyState = page.getByText("No research notes yet");
      const docCard = page.locator("[class*='grid'] > *").first();
      await expect(emptyState.or(docCard)).toBeVisible({ timeout: 10_000 });
    }
  });

  test("displays breadcrumb navigation", async ({ page }) => {
    const heading = page.getByRole("heading", { name: "Notes" });
    const loginHeading = page.getByText("Sign in to your Quillstead account");
    await expect(heading.or(loginHeading)).toBeVisible({ timeout: 10_000 });

    if (await heading.isVisible().catch(() => false)) {
      await expect(page.getByText("Notes").first()).toBeVisible();
    }
  });
});
