import { test, expect } from "./fixtures";

const LEGACY_SOURCE = "tests/legacy-suites/cypress/cypress/e2e/document-search.cy.js";

test(
  "CY-document-search-01 finds a document by title",
  {
    tag: ["@CY-document-search-01", "@cypress-document-search"],
    annotation: { type: "cypress", description: `${LEGACY_SOURCE}#finds a document by title` },
  },
  async ({ page, FindDocumentByTitle }) => {
    const main = page.getByRole("main");

    await test.step("CY-document-search-01-STEP-01 Visit /search?q=quarterly as a signed-in user", async () => {
      await page.goto(`/search?q=${FindDocumentByTitle.Query}`);
    });

    // Legacy STEP-02 cy.wait("@search") waited on a stubbed alias; dropped, the web-first assertions below replace it.

    await test.step("CY-document-search-01-STEP-03 Verify search result Quarterly Planning", async () => {
      const result = main.getByRole("link", { name: new RegExp(FindDocumentByTitle.Title) });
      await expect(result).toBeVisible();
      await expect(result).toHaveAttribute("href", `/documents/${FindDocumentByTitle.DocumentId}`);
    });

    await test.step("CY-document-search-01-STEP-04 Verify search input value", async () => {
      // The page search input has no label or aria-label (accessible name only from its placeholder); scope by role to main.
      await expect(main.getByRole("textbox")).toHaveValue(FindDocumentByTitle.Query);
    });
  },
);
