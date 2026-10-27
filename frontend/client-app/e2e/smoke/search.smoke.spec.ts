import { test, expect } from "../fixtures/signed-in";

test.describe("Search page (signed in)", () => {
  test(
    "a signed-in customer searches for their document and the result links to it",
    { tag: ["@smoke", "@smoke-search"] },
    async ({ page, customer, searchableDocument }) => {
      const main = page.getByRole("main");

      await test.step("open /search as the signed-in customer", async () => {
        await page.goto("/search");
        await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
        await expect(page.getByRole("banner").getByText(customer.displayName)).toBeVisible();
      });

      await test.step("search for the customer's document", async () => {
        const searchBox = main.getByPlaceholder("Search files, documents, and folders...");
        await searchBox.fill(searchableDocument.searchTerm);
        await searchBox.press("Enter");
      });

      await test.step("the customer's document is listed and links to its editor", async () => {
        await expect(
          main.getByText(`1 result for \u201c${searchableDocument.searchTerm}\u201d`)
        ).toBeVisible();
        const result = main.getByRole("link", { name: new RegExp(searchableDocument.title) });
        await expect(result).toHaveCount(1);
        await expect(result).toHaveAttribute("href", `/documents/${searchableDocument.id}`);
      });
    }
  );
});
