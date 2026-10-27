import { test, expect } from "./fixtures";
import { expectStarredItem, starDocumentViaUi } from "../support/sharing";
import { legacyDetails } from "../support/traceability";

function source(id: string) {
  const tosca = legacyDetails({
    suite: "tosca",
    id,
    group: "tosca-Sharing",
    source: `tests/legacy-suites/tosca/TestCases/Sharing/${id}.xml`,
  });
  if (id === "TC-SHARE-003") {
    const cypress = legacyDetails({
      suite: "cypress",
      id: "CY-starred-01",
      group: "cypress-starred",
      source: "tests/legacy-suites/cypress/cypress/e2e/starred.cy.js",
      method: "shows a saved document",
    });
    return { tag: [...tosca.tag, ...cypress.tag], annotation: [tosca.annotation, cypress.annotation] };
  }
  return { tag: tosca.tag, annotation: tosca.annotation };
}

test("TC-SHARE-001 View a shared file", source("TC-SHARE-001"), async ({ page, SharedFile }) => {
  await test.step("TC-SHARE-001-STEP-01 Verify SharedHeading", async () => {
    await expect(page.getByRole("heading", { name: "Shared with me", exact: true })).toBeVisible();
  });
  await test.step("TC-SHARE-001-STEP-02 Verify SharedFileLink", async () => {
    await expect(page.getByRole("main").getByRole("link", { name: /Roadmap\.pdf/ })).toContainText(SharedFile.FileName);
  });
});

test("TC-SHARE-002 Open a shared file", source("TC-SHARE-002"), async ({ page, OpenSharedFile }) => {
  await test.step("TC-SHARE-002-STEP-01 Verify SharedHeading", async () => {
    await expect(page.getByRole("heading", { name: "Shared with me", exact: true })).toBeVisible();
  });
  await test.step("TC-SHARE-002-STEP-03 Click OpenSharedItem", async () => {
    await page.getByRole("main").getByRole("link", { name: /Roadmap\.pdf/ }).click();
    await expect(page).toHaveURL(`/files/${OpenSharedFile.id}`);
    await expect(page.getByRole("heading", { name: OpenSharedFile.FileName, exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Download", exact: true })).toBeVisible();
  });
});

test("TC-SHARE-003 View starred documents", source("TC-SHARE-003"), async ({ page, StarredDocument }) => {
  await test.step("CY-starred-01-STEP-01 Star document through the app", async () => {
    await starDocumentViaUi(page, StarredDocument.DocumentTitle);
  });
  await test.step("CY-starred-01-STEP-02 Visit /starred", async () => {
    await page.goto("/starred");
  });
  await test.step("CY-starred-01-STEP-03 Verify the user's starred item", async () => {
    await expectStarredItem(page, StarredDocument.userId, StarredDocument.documentId);
  });
  await test.step("TC-SHARE-003-STEP-01 Verify StarredHeading", async () => {
    await expect(page.getByRole("heading", { name: "Starred", exact: true })).toBeVisible();
  });
  await test.step("TC-SHARE-003-STEP-02 Verify DocumentCard", async () => {
    const card = page.getByRole("main").getByRole("link", { name: new RegExp(StarredDocument.DocumentTitle) });
    await expect(card).toBeVisible();
    await expect(card).toHaveAttribute("href", `/documents/${StarredDocument.documentId}`);
    await expect(card.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
  });
});
