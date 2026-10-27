import { randomUUID } from "node:crypto";
import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";

// Legacy data, verbatim from tests/legacy-suites/cypress/cypress/fixtures/user.json.
const legacyUser = {
  id: "user-123",
  email: "alex.morgan@example.test",
  displayName: "Alex Morgan",
  createdAt: "2025-01-15T12:00:00.000Z",
} as const;

// Legacy data, verbatim from tests/legacy-suites/cypress/cypress/fixtures/search-results.json (results[0]).
const legacySearchResult = {
  id: "doc-101",
  type: "document",
  title: "Quarterly Planning",
  content_snippet: "Review quarterly objectives and dates.",
  updated_at: "2025-02-18T10:30:00.000Z",
} as const;

// Legacy data, verbatim from document-search.cy.js: cy.visitAsUser("/search?q=quarterly").
const legacyQuery = "quarterly";

type SearchWorkspace = {
  LegacyUserId: string;
  LegacyEmail: string;
  Email: string;
  DisplayName: string;
  LegacyDocumentId: string;
  DocumentId: string;
  Type: string;
  Title: string;
  ContentSnippet: string;
  Query: string;
  accessToken: string;
};

type Fixtures = { FindDocumentByTitle: SearchWorkspace };

async function seedSearchableDocument(request: APIRequestContext, page: Page): Promise<SearchWorkspace> {
  // The legacy email/id were a stubbed profile; a real registration needs a fresh unique address and gets a server-issued id.
  const email = `document-search-${randomUUID()}@example.com`;
  const registration = await request.post("/api/v1/auth/register", {
    data: { displayName: legacyUser.displayName, email, password: "Document-Search-2026!" },
  });
  await expect(registration).toBeOK();
  const tokens = await registration.json();
  expect(tokens.user.email).toBe(email);
  const headers = { Authorization: `Bearer ${tokens.accessToken}` };

  const created = await request.post("/api/v1/documents", {
    headers,
    data: { title: legacySearchResult.title, content: legacySearchResult.content_snippet },
  });
  await expect(created).toBeOK();
  const document = await created.json();
  expect(document.title).toBe(legacySearchResult.title);

  // Indexing is asynchronous (document-service -> SNS -> SQS -> search-service -> MeiliSearch).
  await expect
    .poll(
      async () => {
        const response = await request.get("/api/v1/search", { headers, params: { q: legacyQuery } });
        if (!response.ok()) return `HTTP ${response.status()}`;
        const body = await response.json();
        return (body.results ?? []).map((hit: { id: string }) => hit.id);
      },
      { message: "seeded document is returned by the real search API", timeout: 30_000 },
    )
    .toEqual([document.id]);

  await page.addInitScript(({ accessToken, refreshToken }) => {
    localStorage.setItem("otter_access_token", accessToken);
    localStorage.setItem("otter_refresh_token", refreshToken);
  }, tokens);

  return {
    LegacyUserId: legacyUser.id,
    LegacyEmail: legacyUser.email,
    Email: email,
    DisplayName: legacyUser.displayName,
    // Legacy stub id "doc-101"; document-service assigns the real id, which the result link must point to.
    LegacyDocumentId: legacySearchResult.id,
    DocumentId: document.id,
    Type: legacySearchResult.type,
    Title: legacySearchResult.title,
    ContentSnippet: legacySearchResult.content_snippet,
    Query: legacyQuery,
    accessToken: tokens.accessToken,
  };
}

export const test = base.extend<Fixtures>({
  FindDocumentByTitle: async ({ request, page }, provide) => {
    await provide(await seedSearchableDocument(request, page));
  },
});
export { expect } from "@playwright/test";
