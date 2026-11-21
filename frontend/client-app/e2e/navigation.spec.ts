import {
  expect,
  test,
} from "./fixtures/signed-in";

test.use({ trace: "retain-on-failure", screenshot: "only-on-failure" });

test.describe("Navigation & Routing (signed in)", () => {
  test("landing page loads at / for a signed-in customer", async ({ page }) => {
    await test.step("Open the landing page", async () => {
      await page.goto("/");
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: "OtterWorks",
          exact: true,
        }),
      ).toBeVisible();
    });
  });

  test("/dashboard opens the Dashboard for a signed-in customer", async ({
    page,
  }) => {
    await test.step("Open /dashboard", async () => {
      await page.goto("/dashboard");
      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(
        page.getByRole("main").getByRole("heading", {
          level: 1,
          name: "Dashboard",
          exact: true,
        }),
      ).toBeVisible();
    });
  });

  for (const { link, path, heading } of [
    { link: "Documents", path: "/documents", heading: "Documents" },
    { link: "Files", path: "/files", heading: "Files" },
    { link: "Search", path: "/search", heading: "Search" },
    { link: "Settings", path: "/settings", heading: "Settings" },
    {
      link: "Notifications",
      path: "/notifications",
      heading: "Notifications",
    },
    {
      link: "Shared with me",
      path: "/shared",
      heading: "Shared with me",
    },
    { link: "Trash", path: "/trash", heading: "Trash" },
  ]) {
    test(`sidebar "${link}" opens ${path} for a signed-in customer`, async ({
      page,
    }) => {
      await test.step(`Open ${path} from the signed-in dashboard`, async () => {
        await page.goto("/dashboard");
        await expect(
          page.getByRole("main").getByRole("heading", {
            level: 1,
            name: "Dashboard",
            exact: true,
          }),
        ).toBeVisible();
        await page
          .getByRole("navigation")
          .getByRole("link", { name: link, exact: true })
          .click();
        await expect(page).toHaveURL(new RegExp(`${path}$`));
        await expect(
          page.getByRole("main").getByRole("heading", {
            level: 1,
            name: heading,
            exact: true,
          }),
        ).toBeVisible();
      });
    });
  }
});

test.describe("Navigation & Routing (signed out)", () => {
  test.use({ account: "signedOut" });

  test("/login loads the login page", async ({ page }) => {
    await test.step("Open /login", async () => {
      await page.goto("/login");
      await expect(
        page.getByText("Sign in to your account", { exact: true }),
      ).toBeVisible();
    });
  });

  test("/register loads the registration page", async ({ page }) => {
    await test.step("Open /register", async () => {
      await page.goto("/register");
      await expect(
        page.getByText("Create your account", { exact: true }),
      ).toBeVisible();
    });
  });

  for (const path of [
    "/documents",
    "/files",
    "/search",
    "/settings",
    "/notifications",
    "/shared",
    "/trash",
  ]) {
    test(`signed-out visitor opening ${path} is sent to sign in`, async ({
      page,
    }) => {
      await test.step(`Open ${path} without a session`, async () => {
        await page.goto(path);
        await expect(page).toHaveURL(/\/login$/);
      });
    });
  }
});
