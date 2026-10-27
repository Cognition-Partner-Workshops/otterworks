import { test, expect } from "./smoke/files/files.fixtures";

test.use({ trace: "retain-on-failure" });

test.describe("Files page (signed in)", () => {
  test("a new customer with no files sees the Files heading and the empty-folder state", async ({
    page,
    customer,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open /files", async () => {
      await page.goto("/files");
      await expect(main.getByRole("heading", { level: 1, name: "Files" })).toBeVisible();
      await expect(page.getByRole("banner").getByText(customer.displayName)).toBeVisible();
    });

    await test.step("Verify the empty-folder state", async () => {
      await expect(
        main.getByRole("heading", { name: "This folder is empty" }),
      ).toBeVisible();
      await expect(main.getByRole("button", { name: "Upload files" })).toBeVisible();
    });
  });

  test("the Upload button opens the upload dropzone", async ({ page, customer }) => {
    const main = page.getByRole("main");

    await test.step("Open /files", async () => {
      await page.goto("/files");
      await expect(main.getByRole("heading", { level: 1, name: "Files" })).toBeVisible();
      await expect(page.getByRole("banner").getByText(customer.displayName)).toBeVisible();
    });

    await test.step("Click Upload", async () => {
      await main.getByRole("button", { name: "Upload", exact: true }).click();
    });

    await test.step("Verify the dropzone is shown", async () => {
      await expect(
        main.getByText("Drag & drop files here, or click to browse"),
      ).toBeVisible();
    });
  });

  test("the grid/list toggle switches the file listing between grid and list layouts", async ({
    page,
    uploadedFile,
  }) => {
    const main = page.getByRole("main");
    const gridFilesHeading = main.getByRole("heading", { level: 2, name: "Files" });
    const listNameColumn = main.getByRole("button", { name: "Name", exact: true });

    await test.step("Open /files in the default grid layout", async () => {
      await page.goto("/files");
      await expect(main.getByRole("link", { name: uploadedFile.name })).toBeVisible();
      await expect(gridFilesHeading).toBeVisible();
      await expect(listNameColumn).toBeHidden();
    });

    // Standard exception: the grid/list toggle buttons are icon-only with no accessible
    // name; reach them by keyboard from the sort select (grid = 1st Tab, list = 2nd Tab).
    await test.step("Switch to the list layout", async () => {
      await main.getByRole("combobox").focus();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Enter");
      await expect(listNameColumn).toBeVisible();
      await expect(gridFilesHeading).toBeHidden();
      await expect(main.getByRole("link", { name: uploadedFile.name })).toBeVisible();
    });

    await test.step("Switch back to the grid layout", async () => {
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Enter");
      await expect(gridFilesHeading).toBeVisible();
      await expect(listNameColumn).toBeHidden();
    });
  });
});

test.describe("Files page (signed out)", () => {
  test("a signed-out visitor opening /files is sent to the sign-in page", async ({ page }) => {
    await test.step("Open /files without a session", async () => {
      await page.goto("/files");
    });

    await test.step("Verify the redirect to /login", async () => {
      await expect(page).toHaveURL(/\/login$/);
      await expect(page.getByText("Sign in to your account")).toBeVisible();
    });
  });
});
