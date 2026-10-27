import { test, expect } from "./fixtures/signed-in";

test.describe("Settings page (signed in)", () => {
  test(
    "shows the Settings heading to a signed-in customer",
    { tag: ["@smoke", "@settings-legal"] },
    async ({ page }) => {
      const main = page.getByRole("main");

      await test.step("Open Settings", async () => {
        await page.goto("/settings");
      });
      await test.step("Confirm the Settings heading", async () => {
        await expect(
          main.getByRole("heading", { name: "Settings", level: 1 }),
        ).toBeVisible();
      });
    },
  );

  test(
    "shows the signed-in customer's name and email in the Profile section",
    { tag: ["@smoke", "@settings-legal"] },
    async ({ page, customer }) => {
      const main = page.getByRole("main");

      await test.step("Open Settings", async () => {
        await page.goto("/settings");
      });
      await test.step("Confirm the Profile section and customer details", async () => {
        await expect(
          main.getByRole("heading", { name: "Profile", level: 2 }),
        ).toBeVisible();
        await expect(main.getByLabel("Full name")).toHaveValue(
          customer.displayName,
        );
        await expect(main.getByLabel("Email", { exact: true })).toHaveValue(
          customer.email,
        );
      });
    },
  );

  test(
    "lists the email, in-app and desktop notification preferences",
    { tag: ["@smoke", "@settings-legal"] },
    async ({ page }) => {
      const main = page.getByRole("main");

      await test.step("Open Settings", async () => {
        await page.goto("/settings");
      });
      await test.step("Confirm each notification preference", async () => {
        await expect(
          main.getByRole("heading", { name: "Notification preferences" }),
        ).toBeVisible();
        await expect(
          main.getByText("Email notifications", { exact: true }),
        ).toBeVisible();
        await expect(
          main.getByText("In-app notifications", { exact: true }),
        ).toBeVisible();
        await expect(
          main.getByText("Desktop notifications", { exact: true }),
        ).toBeVisible();
      });
    },
  );

  test(
    "keeps Save changes disabled until the profile is edited",
    { tag: ["@smoke", "@settings-legal"] },
    async ({ page, customer }) => {
      const main = page.getByRole("main");
      const saveButton = main.getByRole("button", { name: "Save changes" });

      await test.step("Open Settings and confirm the profile is unchanged", async () => {
        await page.goto("/settings");
        await expect(main.getByLabel("Full name")).toHaveValue(
          customer.displayName,
        );
        await expect(saveButton).toBeDisabled();
      });
      await test.step("Edit the profile and enable saving", async () => {
        await main
          .getByLabel("Full name")
          .fill(`${customer.displayName} Edited`);
        await expect(saveButton).toBeEnabled();
      });
    },
  );
});

test.describe("Settings page (signed out)", () => {
  test.use({ account: "signedOut" });

  test(
    "redirects a signed-out visitor to sign in",
    { tag: ["@smoke", "@settings-legal"] },
    async ({ page }) => {
      await test.step("Visit Settings while signed out", async () => {
        await page.goto("/settings");
      });
      await test.step("Confirm the sign-in redirect", async () => {
        await expect(page).toHaveURL(/\/login/);
        await expect(
          page.getByText("Sign in to your account", { exact: true }),
        ).toBeVisible();
      });
    },
  );
});
