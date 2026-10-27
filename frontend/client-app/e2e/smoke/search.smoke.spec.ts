import { test, expect } from "../fixtures/fixtures";

test(
  "search finds the signed-in customer's document by keyword",
  {
    tag: ["@smoke", "@page-search"],
    annotation: { type: "route", description: "/search" },
  },
  async ({ page, searchableDocument }) => {
    await page.goto("/search");
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { name: "Search", exact: true })).toBeVisible();

    // a11y gap: the search input has no <label>; its accessible name comes only from the placeholder.
    const searchInput = main.getByRole("textbox", { name: "Search files, documents, and folders..." });
    await searchInput.fill(searchableDocument.keyword);
    await searchInput.press("Enter");

    const result = main.getByRole("link").filter({ hasText: searchableDocument.title });
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute("href", `/documents/${searchableDocument.id}`);
    // a11y gap: the result count is a plain <p> with no role or label.
    await expect(main.getByText(`1 result for “${searchableDocument.keyword}”`, { exact: true })).toBeVisible();
  },
);
