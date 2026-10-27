import { test, expect } from "./fixtures";

function source(id: string) {
  return {
    tag: [`@${id}`, "@tosca-Search"],
    annotation: {
      type: "tosca",
      description: `tests/legacy-suites/tosca/TestCases/Search/${id}.xml`,
    },
  };
}

test("TC-SRCH-001 Find a document by title", source("TC-SRCH-001"), async ({ page, TitleSearch }) => {
  await test.step("TC-SRCH-001-STEP-01 Input SearchInput", async () => {
    const searchInput = page.getByRole("textbox", {
      name: "Search files, documents, and folders...",
      exact: true,
    });
    await searchInput.fill(TitleSearch.Query);
    await searchInput.press("Enter");
    await expect(searchInput).toHaveValue(TitleSearch.Query);
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
});

test("TC-SRCH-002 Filter search results by type", source("TC-SRCH-002"), async ({ page, DocumentType }) => {
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
    const searchInput = page.getByRole("textbox", {
      name: "Search files, documents, and folders...",
      exact: true,
    });
    await searchInput.fill(DocumentType.Query);
    await searchInput.press("Enter");
    await expect(searchInput).toHaveValue(DocumentType.Query);
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
  await test.step("TC-SRCH-003-STEP-01 Input SearchInput", async () => {
    const searchInput = page.getByRole("textbox", {
      name: "Search files, documents, and folders...",
      exact: true,
    });
    await searchInput.fill(NoResults.Query);
    await searchInput.press("Enter");
    await expect(searchInput).toHaveValue(NoResults.Query);
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
