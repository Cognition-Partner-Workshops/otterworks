import { test, expect } from "./fixtures/tosca";
import {
  SharedFile,
  OpenSharedFile,
  StarredDocument,
} from "./fixtures/data/sharing";

const sharingCsv = "tests/legacy-suites/tosca/TestCaseDesign/Sharing.csv";

test.describe("TC-SHARE-001 View a shared file", () => {
  test.use({ toscaData: SharedFile });

  test(
    "TC-SHARE-001 View a shared file",
    {
      tag: ["@TC-SHARE-001", "@tosca-sharing"],
      annotation: [
        {
          type: "tosca-testcase",
          description: "tests/legacy-suites/tosca/TestCases/Sharing/TC-SHARE-001.xml",
        },
        { type: "tosca-data", description: `${sharingCsv}#SharedFile` },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      await page.goto("/shared");

      await test.step("TC-SHARE-001-STEP-01 Verify SharedHeading", async () => {
        await expect(
          main.getByRole("heading", { level: 1, name: "Shared with me", exact: true }),
        ).toBeVisible();
      });

      await test.step("TC-SHARE-001-STEP-02 Verify SharedFileLink", async () => {
        await expect(
          main.getByRole("link", { name: toscaData.row.FileName }),
        ).toBeVisible();
      });
    },
  );
});

test.describe("TC-SHARE-002 Open a shared file", () => {
  test.use({ toscaData: OpenSharedFile });

  test(
    "TC-SHARE-002 Open a shared file",
    {
      tag: ["@TC-SHARE-002", "@tosca-sharing"],
      annotation: [
        {
          type: "tosca-testcase",
          description: "tests/legacy-suites/tosca/TestCases/Sharing/TC-SHARE-002.xml",
        },
        { type: "tosca-data", description: `${sharingCsv}#OpenSharedFile` },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      const item = main.getByRole("link", { name: toscaData.row.FileName });
      const file = toscaData.workspace.files?.find(
        (candidate) => candidate.name === toscaData.row.FileName,
      );
      if (!file) throw new Error(`Missing file fixture: ${toscaData.row.FileName}`);
      await page.goto("/shared");

      await test.step("TC-SHARE-002-STEP-01 Verify SharedHeading", async () => {
        await expect(
          main.getByRole("heading", { level: 1, name: "Shared with me", exact: true }),
        ).toBeVisible();
      });

      await test.step(
        "TC-SHARE-002-STEP-02 Wait (replaced: Roadmap.pdf link visible)",
        async () => {
          await expect(item).toBeVisible();
        },
      );

      await test.step("TC-SHARE-002-STEP-03 Click OpenSharedItem", async () => {
        await item.click();
        await expect(page).toHaveURL(`/files/${file.id}`);
        await expect(
          main.getByRole("heading", {
            level: 1,
            name: toscaData.row.FileName,
            exact: true,
          }),
        ).toBeVisible();
      });
    },
  );
});

test.describe("TC-SHARE-003 View starred documents", () => {
  test.use({ toscaData: StarredDocument });

  test(
    "TC-SHARE-003 View starred documents",
    {
      tag: ["@TC-SHARE-003", "@tosca-sharing"],
      annotation: [
        {
          type: "tosca-testcase",
          description: "tests/legacy-suites/tosca/TestCases/Sharing/TC-SHARE-003.xml",
        },
        { type: "tosca-data", description: `${sharingCsv}#StarredDocument` },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      await page.goto("/starred");

      await test.step("TC-SHARE-003-STEP-01 Verify StarredHeading", async () => {
        await expect(
          main.getByRole("heading", { level: 1, name: "Starred", exact: true }),
        ).toBeVisible();
      });

      await test.step("TC-SHARE-003-STEP-02 Verify DocumentCard", async () => {
        await expect(
          main.getByRole("link", { name: toscaData.row.DocumentTitle }),
        ).toBeVisible();
      });
    },
  );
});
