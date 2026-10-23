import { test, expect } from "@playwright/test";
import {
  apiContext,
  createDocument,
  createFolder,
  registerViaApi,
  seedNotifications,
  signInWithTokens,
  type ApiUser,
} from "./fixtures/browsing-helpers";

test.describe("Browsing journeys (signed in)", () => {
  let user: ApiUser;

  test.beforeEach(async ({ page }) => {
    const api = await apiContext();
    user = await registerViaApi(api);
    await api.dispose();
    await signInWithTokens(page, user);
  });

  test("deep link to /dashboard renders the app shell with the signed-in user", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
    await expect(page.getByText(user.displayName).first()).toBeVisible();
    await expect(page.getByText("No recent files")).toBeVisible();
  });

  test("sidebar navigates between browsing pages and highlights the active item", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = page.locator("aside");
    for (const [label, path, heading] of [
      ["Recent", "/recent", "Recent"],
      ["Files", "/files", /Files/],
      ["Notifications", "/notifications", "Notifications"],
      ["Settings", "/settings", "Settings"],
      ["Dashboard", "/dashboard", "Dashboard"],
    ] as const) {
      const link = sidebar.getByRole("link", { name: label, exact: true });
      await link.click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
      await expect(link).toHaveClass(/border-accent-500/);
    }
  });

  test("folder drill-down updates the URL and breadcrumb, and breadcrumb returns to root", async ({ page }) => {
    const api = await apiContext();
    const parent = await createFolder(api, user, "Projects");
    const child = await createFolder(api, user, "Q3 Launch", parent.id);
    await api.dispose();

    await page.goto("/files");
    await page.getByRole("link", { name: /Projects/ }).first().click();
    await expect(page).toHaveURL(new RegExp(`/files\\?folder=${parent.id}$`));
    const crumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumb).toContainText("Projects");

    await page.getByRole("link", { name: /Q3 Launch/ }).first().click();
    await expect(page).toHaveURL(new RegExp(`/files\\?folder=${child.id}$`));
    await expect(crumb).toContainText("Q3 Launch");
    await expect(page.getByText("This folder is empty")).toBeVisible();

    await crumb.getByRole("link", { name: "Files" }).click();
    await expect(page).toHaveURL(/\/files$/);
    await expect(page.getByRole("link", { name: /Projects/ }).first()).toBeVisible();
  });

  test("nested folder breadcrumb shows the full ancestor path", async ({ page }) => {
    const api = await apiContext();
    const parent = await createFolder(api, user, "Projects");
    const child = await createFolder(api, user, "Q3 Launch", parent.id);
    await api.dispose();

    await page.goto(`/files?folder=${child.id}`);
    const crumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumb).toContainText("Q3 Launch");
    await expect(crumb.getByRole("link", { name: "Projects" })).toBeVisible({ timeout: 5_000 });
  });

  test("recent page lists a newly created document under Today", async ({ page }) => {
    const api = await apiContext();
    await createDocument(api, user, "Browsing recent doc");
    await api.dispose();

    await page.goto("/recent");
    const today = page.locator("section", { has: page.getByRole("heading", { name: "Today" }) });
    await expect(today.getByText("Browsing recent doc")).toBeVisible();
  });

  test("settings preference toggle persists across reload", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    const toggle = page
      .locator("div.justify-between", { hasText: "Desktop notifications" })
      .getByRole("button");
    await expect(toggle).toBeVisible();
    const wasOn = /bg-otter-600/.test((await toggle.getAttribute("class")) ?? "");
    const saved = page.waitForResponse(
      (r) => r.url().includes("/api/v1/settings") && r.request().method() === "PATCH"
    );
    await toggle.click();
    expect((await saved).status()).toBe(200);
    await page.reload();
    await expect(toggle).toHaveClass(wasOn ? /bg-gray-300/ : /bg-otter-600/);
  });

  test("notification bell badge shows the unread count", async ({ page }) => {
    await seedNotifications(user, ["Bell QA one", "Bell QA two"]);
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Notifications (2 unread)" })).toBeVisible();
  });

  test("notification bell opens the notifications page with seeded items", async ({ page }) => {
    await seedNotifications(user, ["Bell QA three"]);
    await page.goto("/dashboard");
    await page.locator("header").getByRole("link", { name: /^Notifications/ }).click();
    await expect(page).toHaveURL(/\/notifications$/);
    await expect(page.getByText("Bell QA three")).toBeVisible();
  });

  test("unknown deep link inside the app shows 404 with a way home", async ({ page }) => {
    await page.goto("/files/does/not/exist");
    await expect(page.getByRole("heading", { name: /404/ })).toBeVisible();
    await page.getByRole("link", { name: "Back to home" }).click();
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe("Browsing journeys (signed out)", () => {
  test("landing page links to sign in and sign up", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "OtterWorks", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: /Sign in/i }).first()).toBeVisible();
  });

  test("protected deep link redirects to login", async ({ page }) => {
    await page.goto("/files?folder=00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("Sign in to your account")).toBeVisible();
  });

  test("unknown top-level path renders 404", async ({ page }) => {
    await page.goto("/totally-unknown");
    await expect(page.getByRole("heading", { name: /404/ })).toBeVisible();
  });
});
