import { test, expect } from "../fixtures/signed-in";

test.use({ trace: "retain-on-failure" });

test.describe("/files/:id smoke", () => {
  test("a signed-in customer opening their file sees its name and details", async ({
    page,
    uploadedFile,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open /files/:id for the uploaded file", async () => {
      await page.goto(`/files/${uploadedFile.id}`);
      await expect(page).toHaveURL(`/files/${uploadedFile.id}`);
    });

    await test.step("Verify the file name is the page heading", async () => {
      await expect(
        main.getByRole("heading", { level: 1, name: uploadedFile.name }),
      ).toBeVisible();
    });

    await test.step("Verify the Details panel shows the file's size, type and owner", async () => {
      await expect(main.getByRole("heading", { level: 2, name: "Details" })).toBeVisible();
      // Standard exception: Details rows are label/value paragraphs with no role; anchor on the label and step up to the row.
      const detailRow = (label: string) =>
        main.getByText(label, { exact: true }).locator("..");
      await expect(detailRow("Size")).toContainText(`${uploadedFile.sizeBytes} B`);
      await expect(detailRow("Type")).toContainText(uploadedFile.mimeType);
      await expect(detailRow("Owner")).toContainText("You");
    });

    // On the local stack LocalStack S3 sends no CORS headers for the app origin, so the
    // text preview's fetch() is blocked and the app shows its iframe fallback.
    await test.step("Verify the preview shows the file's content", async () => {
      const preview = main
        .getByTitle(`Preview of ${uploadedFile.name}`)
        .contentFrame();
      await expect(preview.getByText(uploadedFile.content)).toBeVisible();
    });
  });
});
