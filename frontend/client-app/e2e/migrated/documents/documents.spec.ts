import { test, expect } from "./fixtures";

function source(id: string) {
  return { tag: [`@${id}`, "@tosca-Documents"], annotation: { type: "tosca", description: `tests/legacy-suites/tosca/TestCases/Documents/${id}.xml` } };
}

test("TC-DOC-001 View the document list", source("TC-DOC-001"), async ({ page, DocumentList }) => {
  await test.step("TC-DOC-001-STEP-01 Verify DocumentsHeading", async () => {
    await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  });
  await test.step("TC-DOC-001-STEP-02 Verify DocumentCard", async () => {
    await expect(page.getByRole("link", { name: new RegExp(DocumentList.Title) })).toBeVisible();
  });
});

test("TC-DOC-002 Open a document", source("TC-DOC-002"), async ({ page, OpenDocument }) => {
  await test.step("TC-DOC-002-STEP-01 Click DocumentCard", async () => {
    await page.getByRole("link", { name: new RegExp(OpenDocument.Title) }).click();
  });
  await test.step("TC-DOC-002-STEP-02 Verify DocumentTitle in editor", async () => {
    const document = OpenDocument.documents.find((doc) => doc.title === OpenDocument.Title)!;
    await expect(page).toHaveURL(`/documents/${document.id}`);
    await expect(page.getByRole("heading", { name: OpenDocument.Title, exact: true })).toBeVisible();
  });
});

test("TC-DOC-003 Verify the dashboard document count", source("TC-DOC-003"), async ({ page, DashboardCount }) => {
  // The statistic is plain paragraphs without an accessible name or grouping role.
  const statistic = page.getByRole("paragraph").filter({ hasText: /^Documents$/ });
  await test.step("TC-DOC-003-STEP-01 Verify DashboardHeading", async () => {
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  });
  await test.step("TC-DOC-003-STEP-02 Verify DocumentCount", async () => {
    // The count/label container has no accessible role or name.
    await expect(page.getByText(/^\d+\s*Documents$/)).toHaveText(new RegExp(`^${DashboardCount.ExpectedDocumentCount}\\s*Documents$`));
  });
  await test.step("TC-DOC-003-STEP-03 Verify DocumentsLabel", async () => {
    await expect(statistic).toHaveText("Documents");
  });
});

test("TC-DOC-004 Filter documents by title", source("TC-DOC-004"), async ({ page, FilterDocument }) => {
  await test.step("TC-DOC-004-STEP-01 Input DocumentFilter", async () => {
    // The filter input has no associated label or accessible name.
    await page.getByPlaceholder("Filter documents...").fill(FilterDocument.Filter);
  });
  await test.step("TC-DOC-004-STEP-02 Verify DocumentCard", async () => {
    await expect(page.getByRole("link", { name: new RegExp(FilterDocument.Title) })).toBeVisible();
    for (const document of FilterDocument.documents.filter((doc) => !doc.title.includes(FilterDocument.Filter))) {
      await expect(page.getByRole("link", { name: new RegExp(document.title) })).toHaveCount(0);
    }
  });
});
