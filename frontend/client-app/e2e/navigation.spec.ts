import { test, expect } from "@playwright/test";

test.describe("Navigation & Routing", () => {
  test("landing page loads at /", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Larkbridge Freight", exact: true })
    ).toBeVisible();
  });

  test("/login loads the login page", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Sign in to track loads and open shipment files")).toBeVisible();
  });

  test("/register loads the registration page", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByText("Create a shipper account")).toBeVisible();
  });

  test("/dashboard loads or redirects to login", async ({ page }) => {
    await page.goto("/dashboard");
    const dashboard = page.getByRole("heading", { name: "Overview" });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(dashboard.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/documents loads or redirects to login", async ({ page }) => {
    await page.goto("/documents");
    const docs = page.getByRole("heading", { name: "Paperwork" });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(docs.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/files loads or redirects to login", async ({ page }) => {
    await page.goto("/files");
    const files = page.getByRole("heading", { name: "Shipment files" });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(files.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/search loads or redirects to login", async ({ page }) => {
    await page.goto("/search");
    const search = page.getByRole("heading", { name: "Search shipments and files", exact: true });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(search.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/settings loads or redirects to login", async ({ page }) => {
    await page.goto("/settings");
    const settings = page.getByRole("heading", { name: "Settings" });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(settings.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/notifications loads or redirects to login", async ({ page }) => {
    await page.goto("/notifications");
    const notifications = page.getByRole("heading", { name: /Notification/i });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(notifications.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/shared loads or redirects to login", async ({ page }) => {
    await page.goto("/shared");
    const shared = page.getByRole("heading", { name: /Shared/i });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(shared.or(login)).toBeVisible({ timeout: 10_000 });
  });

  test("/trash loads or redirects to login", async ({ page }) => {
    await page.goto("/trash");
    const trash = page.getByRole("heading", { name: /Trash/i });
    const login = page.getByText("Sign in to track loads and open shipment files");
    await expect(trash.or(login)).toBeVisible({ timeout: 10_000 });
  });
});
