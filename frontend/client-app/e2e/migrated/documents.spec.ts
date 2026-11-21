import { test, expect } from "./fixtures/tosca";
import {
  DashboardCount,
  DocumentList,
  FilterDocument,
  OpenDocument,
} from "./fixtures/data/documents";

const documentsCsv = "tests/legacy-suites/tosca/TestCaseDesign/Documents.csv";

test.describe("TC-DOC-001 View the document list", () => {
  test.use({ toscaData: DocumentList });

  test(
    "TC-DOC-001 View the document list",
    {
      tag: ["@TC-DOC-001", "@tosca-documents"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Documents/TC-DOC-001.xml",
        },
        {
          type: "tosca-data",
          description: `${documentsCsv}#DocumentList`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      await page.goto("/documents");

      await test.step(
        "TC-DOC-001-STEP-01 Verify DocumentsHeading",
        async () => {
          await expect(
            main.getByRole("heading", { level: 1, name: "Documents" }),
          ).toBeVisible();
        },
      );

      await test.step("TC-DOC-001-STEP-02 Verify DocumentCard", async () => {
        await expect(
          main.getByRole("link", { name: toscaData.row.Title }),
        ).toBeVisible();
      });
    },
  );
});

test.describe("TC-DOC-002 Open a document", () => {
  test.use({ toscaData: OpenDocument });

  test(
    "TC-DOC-002 Open a document",
    {
      tag: ["@TC-DOC-002", "@tosca-documents"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Documents/TC-DOC-002.xml",
        },
        {
          type: "tosca-data",
          description: `${documentsCsv}#OpenDocument`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      await page.goto("/documents");

      await test.step("TC-DOC-002-STEP-01 Click DocumentCard", async () => {
        await main.getByRole("link", { name: toscaData.row.Title }).click();
      });

      await test.step("TC-DOC-002-STEP-02 Verify DocumentTitle", async () => {
        await expect(page).toHaveURL(/\/documents\/doc-101$/);
        await expect(
          main.getByRole("heading", {
            level: 1,
            name: toscaData.row.Title,
          }),
        ).toBeVisible();
      });
    },
  );
});

test.describe("TC-DOC-003 Verify the dashboard document count", () => {
  test.use({ toscaData: DashboardCount });

  test(
    "TC-DOC-003 Verify the dashboard document count",
    {
      tag: ["@TC-DOC-003", "@tosca-documents"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Documents/TC-DOC-003.xml",
        },
        {
          type: "tosca-data",
          description: `${documentsCsv}#DashboardCount`,
        },
      ],
    },
    async ({ page }) => {
      const main = page.getByRole("main");
      await page.goto("/dashboard");

      await test.step(
        "TC-DOC-003-STEP-01 Verify DashboardHeading",
        async () => {
          await expect(
            main.getByRole("heading", { level: 1, name: "Dashboard" }),
          ).toBeVisible();
        },
      );

      await test.step("TC-DOC-003-STEP-02 Verify DocumentCount", async () => {
        // Standard exception: the Documents stat card has no accessible name.
        const documentsLabel = main.getByText("Documents", { exact: true });
        const statCard = documentsLabel.locator("..");
        await expect(statCard).toHaveText(
          new RegExp(
            `^\\s*${DashboardCount.expected.documentCount}\\s*Documents\\s*$`,
          ),
        );
      });

      await test.step(
        "TC-DOC-003-STEP-03 Verify DocumentsLabel",
        async () => {
          await expect(
            main.getByText("Documents", { exact: true }),
          ).toBeVisible();
        },
      );
    },
  );
});

test.describe("TC-DOC-004 Filter documents by title", () => {
  test.use({ toscaData: FilterDocument });

  test(
    "TC-DOC-004 Filter documents by title",
    {
      tag: ["@TC-DOC-004", "@tosca-documents"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Documents/TC-DOC-004.xml",
        },
        {
          type: "tosca-data",
          description: `${documentsCsv}#FilterDocument`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      await page.goto("/documents");

      await test.step("TC-DOC-004-STEP-01 Input DocumentFilter", async () => {
        await main
          .getByRole("textbox", { name: "Filter documents..." })
          .fill(toscaData.row.Filter);
      });

      await test.step("TC-DOC-004-STEP-02 Verify DocumentCard", async () => {
        await expect(
          main.getByRole("link", { name: toscaData.row.Title }),
        ).toBeVisible();

        const filter = toscaData.row.Filter.toLowerCase();
        const filteredOutDocuments = toscaData.workspace.documents.filter(
          (document) => !document.title.toLowerCase().includes(filter),
        );

        for (const document of filteredOutDocuments) {
          await expect(
            main.getByRole("link", { name: document.title }),
          ).toHaveCount(0);
        }
      });
    },
  );
});
