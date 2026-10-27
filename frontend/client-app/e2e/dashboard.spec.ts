import { type Page } from "@playwright/test";
import {
  expect,
  test,
} from "./fixtures/signed-in";

test.use({ trace: "retain-on-failure", screenshot: "only-on-failure" });

async function openDashboard(page: Page) {
  await page.goto("/dashboard");
  await expect(
    page.getByRole("main").getByRole("heading", {
      level: 1,
      name: "Dashboard",
      exact: true,
    }),
  ).toBeVisible();
}

test.describe("Dashboard (signed in)", () => {
  test.use({ account: "fresh" });

  test("shows the Dashboard heading for the signed-in customer", async ({
    page,
    customer,
  }) => {
    await test.step("Open the signed-in customer's dashboard", async () => {
      await openDashboard(page);
    });
    await test.step("Show the signed-in customer's email", async () => {
      await expect(page.getByText(customer.email, { exact: true })).toBeVisible();
    });
  });

  test("Upload file and New document link to Files and Documents", async ({
    page,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open the signed-in customer's dashboard", async () => {
      await openDashboard(page);
    });
    await test.step("Link the dashboard actions to their destinations", async () => {
      await expect(
        main.getByRole("link", { name: "Upload file", exact: true }),
      ).toHaveAttribute("href", "/files");
      await expect(
        main.getByRole("link", { name: "New document", exact: true }),
      ).toHaveAttribute("href", "/documents");
    });
  });

  test("stat cards start at zero for a brand-new customer", async ({ page }) => {
    const main = page.getByRole("main");

    await test.step("Open the signed-in customer's dashboard", async () => {
      await openDashboard(page);
    });
    await test.step("Show zero counts and the default storage allowance", async () => {
      // Standard exception: stat cards have no role or accessible name; anchor on visible text and step up to the card.
      await expect(
        main.getByText("Total files", { exact: true }).locator(".."),
      ).toHaveText(/^0\s*Total files$/);
      await expect(
        main.getByText("Documents", { exact: true }).locator(".."),
      ).toHaveText(/^0\s*Documents$/);
      await expect(
        main.getByText(/Storage used · of 10 GB/).locator(".."),
      ).toHaveText(/^0 B\s*Storage used · of 10 GB$/);
      await expect(
        main.getByText(/Recent activity · actions today/).locator(".."),
      ).toHaveText(/^0\s*Recent activity · actions today$/);
    });
  });

  test("shows the empty Recent files section for a brand-new customer", async ({
    page,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open the signed-in customer's dashboard", async () => {
      await openDashboard(page);
    });
    await test.step("Show the empty Recent files section", async () => {
      await expect(
        main.getByRole("heading", {
          level: 2,
          name: "Recent files",
          exact: true,
        }),
      ).toBeVisible();
      await expect(main.getByText("No recent files", { exact: true })).toBeVisible();
    });
  });

  test("shows the empty Recent documents section for a brand-new customer", async ({
    page,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open the signed-in customer's dashboard", async () => {
      await openDashboard(page);
    });
    await test.step("Show the empty Recent documents section", async () => {
      await expect(
        main.getByRole("heading", {
          level: 2,
          name: "Recent documents",
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        main.getByText("No recent documents", { exact: true }),
      ).toBeVisible();
    });
  });

  test("shows the empty Activity section for a brand-new customer", async ({
    page,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open the signed-in customer's dashboard", async () => {
      await openDashboard(page);
    });
    await test.step("Show the empty Activity section", async () => {
      await expect(
        main.getByRole("heading", { level: 2, name: "Activity", exact: true }),
      ).toBeVisible();
      await expect(
        main.getByText("No recent activity", { exact: true }),
      ).toBeVisible();
    });
  });
});

test.describe("Dashboard (signed out)", () => {
  test.use({ account: "signedOut" });

  test("signed-out visitor opening /dashboard is sent to sign in", async ({
    page,
  }) => {
    await test.step("Open /dashboard without a session", async () => {
      await page.goto("/dashboard");
    });
    await test.step("Redirect to the sign-in page", async () => {
      await expect(page).toHaveURL(/\/login$/);
      await expect(
        page.getByText("Sign in to your account", { exact: true }),
      ).toBeVisible();
    });
  });
});
