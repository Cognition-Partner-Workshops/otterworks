import { randomUUID } from "node:crypto";
import { test, expect } from "./fixtures/signed-in";

const SEARCH_PLACEHOLDER = "Search files, documents, and folders...";

test.describe("Search Page", () => {
  test.beforeEach(async ({ page }) => {
    await test.step("open /search as a signed-in customer", async () => {
      await page.goto("/search");
    });
  });

  test("shows Search heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
  });

  test("displays search input with placeholder", async ({ page }) => {
    await expect(page.getByRole("main").getByPlaceholder(SEARCH_PLACEHOLDER)).toBeVisible();
  });

  test("shows empty state before searching", async ({ page }) => {
    const main = page.getByRole("main");
    await expect(main.getByText("Search OtterWorks")).toBeVisible();
    await expect(
      main.getByText("Find files, documents, and folders across your workspace")
    ).toBeVisible();
  });

  test("filter toggle shows the type filters", async ({ page }) => {
    const main = page.getByRole("main");

    await test.step("toggle the filters from the search box", async () => {
      // Standard exception: the filter toggle is an icon-only button with no accessible name,
      // so reach it the way a keyboard user does: Tab from the search box.
      await main.getByPlaceholder(SEARCH_PLACEHOLDER).focus();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Enter");
    });

    await test.step("the type filters are shown", async () => {
      for (const name of ["All types", "Files", "Documents", "Folders"]) {
        await expect(main.getByRole("button", { name, exact: true })).toBeVisible();
      }
    });
  });

  test("can type a query in the search input", async ({ page }) => {
    const searchInput = page.getByRole("main").getByPlaceholder(SEARCH_PLACEHOLDER);
    await searchInput.fill("test query");
    await expect(searchInput).toHaveValue("test query");
  });

  test("shows no results for gibberish query", async ({ page }) => {
    const main = page.getByRole("main");
    const gibberish = `xyznonexistent${randomUUID().replace(/-/g, "")}`;

    await test.step("search for a term nobody has written", async () => {
      const searchInput = main.getByPlaceholder(SEARCH_PLACEHOLDER);
      await searchInput.fill(gibberish);
      await searchInput.press("Enter");
    });

    await test.step("the no-results state names the query", async () => {
      await expect(main.getByText("No results found")).toBeVisible();
      await expect(
        main.getByText(`No results for "${gibberish}". Try different keywords.`)
      ).toBeVisible();
    });
  });

});

test.describe("Search Page (signed out)", () => {
  test.use({ account: "signedOut" });

  test("sends a signed-out visitor to the sign-in page", async ({ page }) => {
    await test.step("open /search without a session", async () => {
      await page.goto("/search");
    });

    await test.step("the visitor lands on /login", async () => {
      await expect(page).toHaveURL(/\/login$/);
      await expect(page.getByText("Sign in to your account")).toBeVisible();
    });
  });
});
