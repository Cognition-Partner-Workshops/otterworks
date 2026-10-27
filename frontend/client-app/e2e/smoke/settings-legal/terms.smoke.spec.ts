import { test, expect } from "./settings-legal.fixtures";

test(
  "signed-in customer opening /terms reads the Terms of Service",
  { tag: ["@smoke", "@settings-legal"] },
  async ({ page }) => {
    const main = page.getByRole("main");

    await test.step("Open the Terms of Service page", async () => {
      await page.goto("/terms");
    });
    await test.step("Confirm the Terms of Service heading", async () => {
      await expect(
        main.getByRole("heading", { name: "Terms of Service", level: 1 }),
      ).toBeVisible();
    });
    await test.step("Read each Terms of Service clause", async () => {
      await expect(
        main.getByText("1. Acceptance of Terms.", { exact: true }),
      ).toBeVisible();
      await expect(
        main.getByText("2. Use of the Service.", { exact: true }),
      ).toBeVisible();
      await expect(main.getByText("3. Accounts.", { exact: true })).toBeVisible();
      await expect(
        main.getByText("4. Termination.", { exact: true }),
      ).toBeVisible();
      await expect(
        main.getByText("5. Governing Law.", { exact: true }),
      ).toBeVisible();
    });
  },
);

test(
  "signed-in customer reaches the Terms of Service from the app footer",
  { tag: ["@smoke", "@settings-legal"] },
  async ({ page, customer }) => {
    const main = page.getByRole("main");

    await test.step("Open Settings as the signed-in customer", async () => {
      await page.goto("/settings");
      await expect(main.getByLabel("Full name")).toHaveValue(
        customer.displayName,
      );
    });
    await test.step("Follow the Terms footer link", async () => {
      await page
        .getByRole("contentinfo")
        .getByRole("link", { name: "Terms" })
        .click();
      await expect(page).toHaveURL(/\/terms$/);
      await expect(
        main.getByRole("heading", { name: "Terms of Service", level: 1 }),
      ).toBeVisible();
    });
  },
);
