import { test as base } from "@playwright/test";
import { seedSearchWorkspace } from "../support/search";

type DesignRow = { TestCaseId: string; Instance: string; Query: string; Result: string; Type: string };
type SearchWorkspace = Awaited<ReturnType<typeof seedSearchWorkspace>>;
type SearchInstance = DesignRow & SearchWorkspace;
type NoResultsInstance = SearchInstance & { ToscaResultText: string; EmptyResultTitle: string };
type Fixtures = {
  TitleSearch: SearchInstance;
  DocumentType: SearchInstance;
  NoResults: NoResultsInstance;
};

export const test = base.extend<Fixtures>({
  TitleSearch: async ({ request, page }, use) => {
    const workspace = await seedSearchWorkspace(request, page);
    await page.goto("/search");
    await use({
      TestCaseId: "TC-SRCH-001",
      Instance: "TitleSearch",
      Query: "quarterly",
      Result: "Quarterly Planning",
      Type: "all",
      ...workspace,
    });
  },
  DocumentType: async ({ request, page }, use) => {
    const workspace = await seedSearchWorkspace(request, page);
    await page.goto("/search");
    await use({
      TestCaseId: "TC-SRCH-002",
      Instance: "DocumentType",
      Query: "release",
      Result: "Release Checklist",
      Type: "document",
      ...workspace,
    });
  },
  NoResults: async ({ request, page }, use) => {
    const workspace = await seedSearchWorkspace(request, page);
    await page.goto("/search");
    await use({
      TestCaseId: "TC-SRCH-003",
      Instance: "NoResults",
      Query: "unmatchedquery",
      Result: "",
      Type: "all",
      // TC-SRCH-003-STEP-03 expects "0 results" on the SearchResult link, but src/pages/search.tsx renders EmptyState "No results found" for an empty result set and no "0 results" text exists in client-app src; the API returns total 0; the log's Screenshots/search.png shows the "quarterly" query, not this case.
      ToscaResultText: "0 results",
      EmptyResultTitle: "No results found",
      ...workspace,
    });
  },
});

export { expect } from "@playwright/test";
