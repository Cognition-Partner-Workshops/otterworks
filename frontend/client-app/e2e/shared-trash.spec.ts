import {
  test,
  expect,
  signedOut,
} from "./smoke/collections/collections.fixtures";

test.describe("Shared Page", () => {
  test("a new customer sees the Shared with me heading and the empty state", async ({
    page,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open /shared as a fresh signed-in customer", async () => {
      await page.goto("/shared");
      await expect(page).toHaveURL(/\/shared$/);
      await expect(
        main.getByRole("heading", { level: 1, name: "Shared with me" }),
      ).toBeVisible();
    });

    await test.step("Verify nothing is shared yet", async () => {
      await expect(
        main.getByRole("heading", { name: "Nothing shared with you yet" }),
      ).toBeVisible();
      await expect(
        main.getByText("Files and documents shared with you will appear here"),
      ).toBeVisible();
    });
  });

  test.describe("signed out", () => {
    test.use({ storageState: signedOut });

    test("opening /shared without signing in redirects to the login page", async ({
      page,
    }) => {
      await test.step("Open /shared with no session", async () => {
        await page.goto("/shared");
      });

      await test.step("Verify the login page is shown", async () => {
        await expect(page).toHaveURL(/\/login$/);
        await expect(page.getByText("Sign in to your account")).toBeVisible();
      });
    });
  });
});

test.describe("Trash Page", () => {
  test("a new customer sees the Trash heading and the empty state", async ({
    page,
  }) => {
    const main = page.getByRole("main");

    await test.step("Open /trash as a fresh signed-in customer", async () => {
      await page.goto("/trash");
      await expect(page).toHaveURL(/\/trash$/);
      await expect(
        main.getByRole("heading", { level: 1, name: "Trash" }),
      ).toBeVisible();
      await expect(
        main.getByText("Items in trash will be permanently deleted after 30 days"),
      ).toBeVisible();
    });

    await test.step("Verify the trash is empty", async () => {
      await expect(
        main.getByRole("heading", { name: "Trash is empty" }),
      ).toBeVisible();
      await expect(main.getByRole("button", { name: "Empty Trash" })).toHaveCount(0);
    });
  });

  test.describe("signed out", () => {
    test.use({ storageState: signedOut });

    test("opening /trash without signing in redirects to the login page", async ({
      page,
    }) => {
      await test.step("Open /trash with no session", async () => {
        await page.goto("/trash");
      });

      await test.step("Verify the login page is shown", async () => {
        await expect(page).toHaveURL(/\/login$/);
        await expect(page.getByText("Sign in to your account")).toBeVisible();
      });
    });
  });
});
