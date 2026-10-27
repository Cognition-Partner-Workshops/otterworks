import { test, expect } from "../fixtures/signed-in";

test.use({ account: "fresh" });

test.use({ trace: "retain-on-failure" });

test.describe("/files smoke", () => {
  test("a signed-in customer sees the file they uploaded listed on /files", async ({
    page,
    uploadedFile,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open /files", async () => {
      await page.goto("/files");
      await expect(
        main.getByRole("heading", { level: 1, name: "Files" }),
      ).toBeVisible();
    });

    await test.step("Verify the uploaded file is listed and links to its detail page", async () => {
      const fileLink = main.getByRole("link", { name: uploadedFile.name });
      await expect(fileLink).toBeVisible();
      await expect(fileLink).toHaveAttribute("href", `/files/${uploadedFile.id}`);
    });
  });
});
