import { test, expect } from "./fixtures/tosca";
import { SharedFile, OpenSharedFile, StarredDocument } from "./fixtures/data/sharing";

for (const instance of [SharedFile, OpenSharedFile, StarredDocument]) {
  const id = instance.testCaseId;
  const name = {
    "TC-SHARE-001": "View a shared file",
    "TC-SHARE-002": "Open a shared file",
    "TC-SHARE-003": "View starred documents",
  }[id];

  test.describe(`${id} ${name}`, () => {
    test.use({ toscaData: instance });
    test(`${id} ${name}`, {
      tag: [`@${id}`, "@tosca-sharing"],
      annotation: [
        { type: "tosca-testcase", description: `tests/legacy-suites/tosca/TestCases/Sharing/${id}.xml` },
        { type: "tosca-data", description: `tests/legacy-suites/tosca/TestCaseDesign/Sharing.csv#${instance.instance}` },
      ],
    }, async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      const starred = id === "TC-SHARE-003";
      await page.goto(starred ? "/starred" : "/shared");
      await test.step(`${id}-STEP-01 Verify ${starred ? "StarredHeading" : "SharedHeading"}`, async () => {
        await expect(main.getByRole("heading", { level: 1, name: starred ? "Starred" : "Shared with me", exact: true })).toBeVisible();
      });
      const item = main.getByRole("link", { name: starred ? toscaData.row.DocumentTitle : toscaData.row.FileName });
      await test.step(`${id}-STEP-02 ${id === "TC-SHARE-002" ? "Wait 5000 ms (replaced with file readiness)" : `Verify ${starred ? "DocumentCard" : "SharedFileLink"}`}`, async () => {
        await expect(item).toBeVisible();
      });
      if (id === "TC-SHARE-002") {
        await test.step(`${id}-STEP-03 Click OpenSharedItem`, async () => {
          const href = await item.getAttribute("href");
          expect(href).toMatch(/^\/files\/[^/]+$/);
          await item.click();
          await expect(page).toHaveURL(new RegExp(`${href}$`));
          await expect(main.getByRole("heading", { level: 1, name: toscaData.row.FileName, exact: true })).toBeVisible();
        });
      }
    });
  });
}
