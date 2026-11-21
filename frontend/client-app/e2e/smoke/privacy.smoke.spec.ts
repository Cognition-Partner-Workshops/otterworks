import { test, expect } from "../fixtures/signed-in";

test(
  "signed-in customer opening /privacy reads the Privacy Policy",
  { tag: ["@smoke", "@settings-legal"] },
  async ({ page }) => {
    const main = page.getByRole("main");

    await test.step("Open the Privacy Policy page", async () => {
      await page.goto("/privacy");
    });
    await test.step("Confirm the Privacy Policy heading", async () => {
      await expect(
        main.getByRole("heading", { name: "Privacy Policy", level: 1 }),
      ).toBeVisible();
    });
    await test.step("Read each Privacy Policy clause", async () => {
      await expect(
        main.getByText("1. Information We Collect.", { exact: true }),
      ).toBeVisible();
      await expect(main.getByText("2. How We Use It.", { exact: true })).toBeVisible();
      await expect(main.getByText("3. Sharing.", { exact: true })).toBeVisible();
      await expect(main.getByText("4. Retention.", { exact: true })).toBeVisible();
      await expect(main.getByText("5. Contact.", { exact: true })).toBeVisible();
    });
  },
);

test(
  "signed-in customer reaches the Privacy Policy from the app footer",
  { tag: ["@smoke", "@settings-legal"] },
  async ({ page, customer }) => {
    const main = page.getByRole("main");

    await test.step("Open Settings as the signed-in customer", async () => {
      await page.goto("/settings");
      await expect(main.getByLabel("Full name")).toHaveValue(
        customer.displayName,
      );
    });
    await test.step("Follow the Privacy footer link", async () => {
      await page
        .getByRole("contentinfo")
        .getByRole("link", { name: "Privacy" })
        .click();
      await expect(page).toHaveURL(/\/privacy$/);
      await expect(
        main.getByRole("heading", { name: "Privacy Policy", level: 1 }),
      ).toBeVisible();
    });
  },
);
