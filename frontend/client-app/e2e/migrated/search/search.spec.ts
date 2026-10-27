import { test, expect } from "./fixtures";
import { searchInput } from "../support/search";
import { legacyDetails } from "../support/traceability";

function source(id: string) {
  const tosca = legacyDetails({
    suite: "tosca",
    id,
    group: "tosca-Search",
    source: `tests/legacy-suites/tosca/TestCases/Search/${id}.xml`,
  });
  if (id === "TC-SRCH-001") {
    const cypress = legacyDetails({
      suite: "cypress",
      id: "CY-document-search-01",
      group: "cypress-document-search",
      source: "tests/legacy-suites/cypress/cypress/e2e/document-search.cy.js",
      method: "finds a document by title",
    });
    return { tag: [...tosca.tag, ...cypress.tag], annotation: [tosca.annotation, cypress.annotation] };
  }
  return {
    tag: tosca.tag,
    annotation: tosca.annotation,
  };
}

test("TC-SRCH-001 Find a document by title", source("TC-SRCH-001"), async ({ page, TitleSearch }) => {
  const input = searchInput(page);
  await test.step("TC-SRCH-001-STEP-01 Input SearchInput", async () => {
    await input.fill(TitleSearch.Query);
    await input.press("Enter");
    await expect(input).toHaveValue(TitleSearch.Query);
  });
  await test.step("TC-SRCH-001-STEP-02 Verify SearchResult", async () => {
    const main = page.getByRole("main");
    const resultLink = main.getByRole("link", { name: new RegExp(TitleSearch.Result) });
    await expect(resultLink).toBeVisible();
    const resultId = TitleSearch.documents.find((document) => document.title === TitleSearch.Result)?.id;
    await expect(resultLink).toHaveAttribute("href", `/documents/${resultId}`);
    // The result count is plain text, not an accessible role.
    await expect(main.getByText(`1 result for “${TitleSearch.Query}”`, { exact: true })).toBeVisible();
    const otherTitles = [
      ...TitleSearch.documents
        .filter((document) => document.title !== TitleSearch.Result)
        .map((document) => document.title),
      ...TitleSearch.files.map((file) => file.name),
    ];
    for (const title of otherTitles) {
      await expect(main.getByRole("link", { name: new RegExp(title) })).toHaveCount(0);
    }
  });
  await test.step("CY-document-search-01-STEP-01 Visit /search?q=quarterly as a signed-in user", async () => {
    await page.goto(`/search?q=${TitleSearch.Query}`);
    await expect(page).toHaveURL(/\/search\?q=quarterly$/);
  });
  await test.step("CY-document-search-01-STEP-03 Verify search result Quarterly Planning", async () => {
    const result = page
      .getByRole("main")
      .getByRole("link", { name: new RegExp(TitleSearch.Result) });
    await expect(result).toBeVisible();
    const resultId = TitleSearch.documents.find((document) => document.title === TitleSearch.Result)?.id;
    await expect(result).toHaveAttribute("href", `/documents/${resultId}`);
  });
  await test.step("CY-document-search-01-STEP-04 Verify search input value", async () => {
    await expect(searchInput(page)).toHaveValue(TitleSearch.Query);
  });
});

test("TC-SRCH-002 Filter search results by type", source("TC-SRCH-002"), async ({ page, DocumentType }) => {
  const input = searchInput(page);
  await test.step("TC-SRCH-002 Select Type filter (CSV Type, no Tosca TestStep)", async () => {
    // The icon-only filter toggle is the only button in main and has no accessible name.
    await page.getByRole("main").getByRole("button").click();
    const typeLabels: Record<string, string> = {
      all: "All types",
      file: "Files",
      document: "Documents",
      folder: "Folders",
    };
    await page
      .getByRole("button", { name: typeLabels[DocumentType.Type], exact: true })
      .click();
  });
  await test.step("TC-SRCH-002-STEP-01 Input SearchInput", async () => {
    await input.fill(DocumentType.Query);
    await input.press("Enter");
    await expect(input).toHaveValue(DocumentType.Query);
  });
  await test.step("TC-SRCH-002-STEP-02 Verify SearchHeading", async () => {
    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
  });
  await test.step("TC-SRCH-002-STEP-03 Verify SearchResult", async () => {
    const main = page.getByRole("main");
    const resultLink = main.getByRole("link", { name: new RegExp(DocumentType.Result) });
    await expect(resultLink).toBeVisible();
    const resultId = DocumentType.documents.find((document) => document.title === DocumentType.Result)?.id;
    await expect(resultLink).toHaveAttribute("href", `/documents/${resultId}`);
    await expect(main.getByRole("link", { name: new RegExp(DocumentType.files[0].name) })).toHaveCount(0);
    // The result count is plain text, not an accessible role.
    await expect(main.getByText(`1 result for “${DocumentType.Query}”`, { exact: true })).toBeVisible();
  });
});

test("TC-SRCH-003 Show an empty search result", source("TC-SRCH-003"), async ({ page, NoResults }) => {
  const input = searchInput(page);
  await test.step("TC-SRCH-003-STEP-01 Input SearchInput", async () => {
    await input.fill(NoResults.Query);
    await input.press("Enter");
    await expect(input).toHaveValue(NoResults.Query);
  });
  await test.step("TC-SRCH-003-STEP-02 Verify SearchHeading", async () => {
    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
  });
  await test.step("TC-SRCH-003-STEP-03 Verify SearchResult", async () => {
    const main = page.getByRole("main");
    await expect(
      page.getByRole("heading", { name: NoResults.EmptyResultTitle, exact: true }),
    ).toBeVisible();
    for (const title of [
      ...NoResults.documents.map((document) => document.title),
      ...NoResults.files.map((file) => file.name),
    ]) {
      await expect(main.getByRole("link", { name: new RegExp(title) })).toHaveCount(0);
    }
  });
});
