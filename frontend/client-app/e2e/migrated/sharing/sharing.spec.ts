import { test, expect } from "./fixtures";

function source(id: string) {
  return { tag: [`@${id}`, "@tosca-Sharing"], annotation: { type: "tosca", description: `tests/legacy-suites/tosca/TestCases/Sharing/${id}.xml` } };
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
  await test.step("TC-SHARE-003-STEP-01 Verify StarredHeading", async () => {
    await expect(page.getByRole("heading", { name: "Starred", exact: true })).toBeVisible();
  });
  await test.step("TC-SHARE-003-STEP-02 Verify DocumentCard", async () => {
    await expect(page.getByRole("main").getByRole("link", { name: new RegExp(StarredDocument.DocumentTitle) })).toBeVisible();
  });
});
