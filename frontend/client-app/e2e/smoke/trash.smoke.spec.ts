import { test, expect } from "../fixtures/signed-in";

test.use({ account: "fresh" });

test.use({ trace: "retain-on-failure" });

test.describe("/trash smoke (signed in)", () => {
  test(
    "a file I moved to trash is listed on Trash with Restore and Delete actions",
    { tag: ["@smoke", "@smoke-collections", "@route-trash"] },
    async ({ page, trashedFile }) => {
      const main = page.getByRole("main");

      await test.step("Open /trash as the signed-in customer", async () => {
        await page.goto("/trash");
        await expect(page).toHaveURL(/\/trash$/);
        await expect(
          main.getByRole("heading", { level: 1, name: "Trash" }),
        ).toBeVisible();
      });

      await test.step("Verify the trashed file is listed with its actions", async () => {
        await expect(main.getByText(trashedFile.name, { exact: true })).toBeVisible();
        await expect(
          main.getByRole("button", { name: "Restore", exact: true }),
        ).toHaveCount(1);
        await expect(
          main.getByRole("button", { name: "Delete", exact: true }),
        ).toHaveCount(1);
        await expect(
          main.getByRole("button", { name: "Empty Trash" }),
        ).toBeVisible();
      });
    },
  );

  test(
    "restoring my trashed file removes it from Trash and returns it to Files",
    { tag: ["@smoke", "@smoke-collections", "@route-trash"] },
    async ({ page, trashedFile }) => {
      const main = page.getByRole("main");

      await test.step("Open /trash and restore the trashed file", async () => {
        await page.goto("/trash");
        await expect(main.getByText(trashedFile.name, { exact: true })).toBeVisible();
        const row = main.getByText(trashedFile.name, { exact: true }).locator("xpath=../..");
        await row.getByRole("button", { name: "Restore", exact: true }).click();
      });

      await test.step("Verify Trash no longer lists the file", async () => {
        await expect(page.getByText("File restored")).toBeVisible();
        await expect(main.getByText(trashedFile.name, { exact: true })).toHaveCount(0);
        await expect(
          main.getByRole("heading", { name: "Trash is empty" }),
        ).toBeVisible();
      });

      await test.step("Verify the file is back on /files", async () => {
        await page.goto("/files");
        await expect(
          main.getByRole("link", { name: trashedFile.name }),
        ).toBeVisible();
      });
    },
  );
});
