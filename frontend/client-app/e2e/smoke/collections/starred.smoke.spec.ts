import { test, expect, escapeRegExp } from "./collections.fixtures";

test.use({ trace: "retain-on-failure" });

test.describe("/starred smoke (signed in)", () => {
  test(
    "a file and a document I starred are listed on Starred under Files and Documents",
    { tag: ["@smoke", "@smoke-collections", "@route-starred"] },
    async ({ page, starredFile, starredDocument }) => {
      const main = page.getByRole("main");

      await test.step("Open /starred as the signed-in customer", async () => {
        await page.goto("/starred");
        await expect(page).toHaveURL(/\/starred$/);
        await expect(
          main.getByRole("heading", { level: 1, name: "Starred" }),
        ).toBeVisible();
      });

      await test.step("Verify the starred file is listed under Files", async () => {
        await expect(
          main.getByRole("heading", { level: 2, name: "Files" }),
        ).toBeVisible();
        const fileCard = main.getByRole("link", {
          name: new RegExp(escapeRegExp(starredFile.name)),
        });
        await expect(fileCard).toBeVisible();
        await expect(fileCard).toHaveAttribute("href", `/files/${starredFile.id}`);
      });

      await test.step("Verify the starred document is listed under Documents", async () => {
        await expect(
          main.getByRole("heading", { level: 2, name: "Documents" }),
        ).toBeVisible();
        const documentCard = main.getByRole("link", {
          name: new RegExp(escapeRegExp(starredDocument.title)),
        });
        await expect(documentCard).toBeVisible();
        await expect(documentCard).toHaveAttribute(
          "href",
          `/documents/${starredDocument.id}`,
        );
      });

      await test.step("Verify both items show as starred", async () => {
        await expect(
          main.getByRole("button", { name: "Unstar", exact: true }),
        ).toHaveCount(2);
      });
    },
  );
});
