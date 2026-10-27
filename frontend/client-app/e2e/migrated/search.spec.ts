import { test, expect } from "./fixtures/tosca";
import {
  DocumentType,
  NoResults,
  TitleSearch,
} from "./fixtures/data/search";

const searchCsv = "tests/legacy-suites/tosca/TestCaseDesign/Search.csv";

test.describe("TC-SRCH-001 Find a document by title", () => {
  test.use({ toscaData: TitleSearch });

  test(
    "TC-SRCH-001 Find a document by title",
    {
      tag: ["@TC-SRCH-001", "@tosca-search"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Search/TC-SRCH-001.xml",
        },
        {
          type: "tosca-data",
          description: `${searchCsv}#TitleSearch`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      const resultDocument = toscaData.workspace.documents.find(
        (document) => document.title === toscaData.row.Result,
      );
      expect(resultDocument).toBeDefined();
      await page.goto("/search");
      const searchInput = main.getByRole("textbox", {
        name: "Search files, documents, and folders...",
        exact: true,
      });

      await test.step(
        "TC-SRCH-001-STEP-01 Input SearchInput",
        async () => {
          await searchInput.fill(toscaData.row.Query);
          await searchInput.press("Enter");
        },
      );

      await test.step(
        "TC-SRCH-001-STEP-02 Verify SearchResult",
        async () => {
          const resultLink = main.getByRole("link", {
            name: toscaData.row.Result,
          });
          await expect(resultLink).toBeVisible();
          await expect(resultLink).toHaveAttribute(
            "href",
            `/documents/${resultDocument!.id}`,
          );
          await expect(
            main.getByText(`1 result for “${toscaData.row.Query}”`),
          ).toBeVisible();
        },
      );
    },
  );
});

test.describe("TC-SRCH-002 Filter search results by type", () => {
  test.use({ toscaData: DocumentType });

  test(
    "TC-SRCH-002 Filter search results by type",
    {
      tag: ["@TC-SRCH-002", "@tosca-search"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Search/TC-SRCH-002.xml",
        },
        {
          type: "tosca-data",
          description: `${searchCsv}#DocumentType`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      const resultDocument = toscaData.workspace.documents.find(
        (document) => document.title === toscaData.row.Result,
      );
      expect(resultDocument).toBeDefined();
      const releaseNotes = toscaData.workspace.files?.find(
        (file) => file.id === "file-201",
      );
      expect(releaseNotes).toBeDefined();
      await page.goto("/search");
      const searchInput = main.getByRole("textbox", {
        name: "Search files, documents, and folders...",
        exact: true,
      });

      await test.step(
        "TC-SRCH-002-STEP-01 Input SearchInput",
        async () => {
          await searchInput.fill(toscaData.row.Query);
          await searchInput.press("Enter");
          await expect(
            main.getByRole("link", { name: toscaData.row.Result }),
          ).toBeVisible();
          await expect(
            main.getByRole("link", { name: releaseNotes!.name }),
          ).toBeVisible();

          // Standard exception: icon-only filter toggle has no accessible name or text; reached by Tab from the search box (see parity TC-SRCH-002).
          await searchInput.press("Tab");
          await page.keyboard.press("Space");
          const typeLabels = {
            all: "All types",
            file: "Files",
            document: "Documents",
            folder: "Folders",
          } as const;
          const typeLabel =
            typeLabels[toscaData.row.Type as keyof typeof typeLabels];
          const searchRequest = page.waitForRequest((request) => {
            const url = new URL(request.url());
            return (
              url.pathname === "/api/v1/search" &&
              url.searchParams.get("type") === toscaData.row.Type
            );
          });
          await main
            .getByRole("button", { name: typeLabel, exact: true })
            .click();
          await searchRequest;
        },
      );

      await test.step(
        "TC-SRCH-002-STEP-02 Verify SearchHeading",
        async () => {
          await expect(
            main.getByRole("heading", { level: 1, name: "Search" }),
          ).toBeVisible();
        },
      );

      await test.step(
        "TC-SRCH-002-STEP-03 Verify SearchResult",
        async () => {
          const resultLink = main.getByRole("link", {
            name: toscaData.row.Result,
          });
          await expect(resultLink).toBeVisible();
          await expect(resultLink).toHaveAttribute(
            "href",
            `/documents/${resultDocument!.id}`,
          );
          await expect(
            main.getByRole("link", { name: releaseNotes!.name }),
          ).toHaveCount(0);
          await expect(
            main.getByText(`1 result for “${toscaData.row.Query}”`),
          ).toBeVisible();
        },
      );
    },
  );
});

test.describe("TC-SRCH-003 Show an empty search result", () => {
  test.use({ toscaData: NoResults });

  test(
    "TC-SRCH-003 Show an empty search result",
    {
      tag: ["@TC-SRCH-003", "@tosca-search"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Search/TC-SRCH-003.xml",
        },
        {
          type: "tosca-data",
          description: `${searchCsv}#NoResults`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const main = page.getByRole("main");
      await page.goto("/search");
      const searchInput = main.getByRole("textbox", {
        name: "Search files, documents, and folders...",
        exact: true,
      });

      await test.step(
        "TC-SRCH-003-STEP-01 Input SearchInput",
        async () => {
          await searchInput.fill(toscaData.row.Query);
          await searchInput.press("Enter");
        },
      );

      await test.step(
        "TC-SRCH-003-STEP-02 Verify SearchHeading",
        async () => {
          await expect(
            main.getByRole("heading", { level: 1, name: "Search" }),
          ).toBeVisible();
        },
      );

      await test.step(
        "TC-SRCH-003-STEP-03 Verify SearchResult",
        async () => {
          await expect(
            main.getByRole("heading", {
              level: 3,
              name: NoResults.expected.emptyStateTitle,
            }),
          ).toBeVisible();
          await expect(
            main.getByText(
              `No results for "${toscaData.row.Query}". Try different keywords.`,
            ),
          ).toBeVisible();

          for (const document of toscaData.workspace.documents) {
            await expect(
              main.getByRole("link", { name: document.title }),
            ).toHaveCount(0);
          }
          for (const file of toscaData.workspace.files ?? []) {
            await expect(
              main.getByRole("link", { name: file.name }),
            ).toHaveCount(0);
          }
          await expect(main.getByText(/\d+ results? for/)).toHaveCount(0);
        },
      );
    },
  );
});
