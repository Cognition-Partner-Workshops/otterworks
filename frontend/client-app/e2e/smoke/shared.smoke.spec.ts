import { test, expect, escapeRegExp } from "../fixtures/signed-in";

test.use({ trace: "retain-on-failure" });

test.describe("/shared smoke (signed in)", () => {
  test(
    "a file another customer shared with me is listed on Shared with me and links to its details",
    { tag: ["@smoke", "@smoke-collections", "@route-shared"] },
    async ({ page, sharedFile }) => {
      const main = page.getByRole("main");

      await test.step("Open /shared as the signed-in recipient", async () => {
        await page.goto("/shared");
        await expect(page).toHaveURL(/\/shared$/);
        await expect(
          main.getByRole("heading", { level: 1, name: "Shared with me" }),
        ).toBeVisible();
      });

      await test.step("Verify the shared file is listed and opens its details page", async () => {
        const card = main.getByRole("link", {
          name: new RegExp(escapeRegExp(sharedFile.name)),
        });
        await expect(card).toBeVisible();
        await expect(card).toHaveAttribute("href", `/files/${sharedFile.id}`);
        await expect(main.getByText("Nothing shared with you yet")).toHaveCount(0);
      });
    },
  );
});
