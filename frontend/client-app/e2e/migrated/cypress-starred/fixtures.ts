import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

const LEGACY_SPEC = "tests/legacy-suites/cypress/cypress/e2e/starred.cy.js";

// Legacy data, verbatim: cypress/fixtures/user.json, cypress/fixtures/document.json,
// the visitAsUser token from cypress/support/e2e.js and the starredItems option in starred.cy.js.
export const legacy = {
  spec: LEGACY_SPEC,
  user: {
    id: "user-123",
    email: "alex.morgan@example.test",
    displayName: "Alex Morgan",
    createdAt: "2025-01-15T12:00:00.000Z",
  },
  document: {
    id: "doc-101",
    title: "Quarterly Planning",
    content: "Review objectives, delivery dates, and ownership for the next quarter.",
    ownerId: "user-123",
    ownerName: "Alex Morgan",
    parentId: null,
    sharedWith: [],
    collaborators: [],
    tags: ["planning"],
    wordCount: 68,
    createdAt: "2025-02-14T09:00:00.000Z",
    updatedAt: "2025-02-18T10:30:00.000Z",
  },
  accessToken: "header.eyJzdWIiOiJ1c2VyLTEyMyJ9.sig",
  refreshToken: "refresh-token",
  starredItems: {
    "user-123:doc-101": {
      itemId: "doc-101",
      itemType: "document",
      starredAt: "2025-02-18T08:00:00.000Z",
    },
  },
} as const;

export type SavedDocument = {
  Title: string;
  Content: string;
  DisplayName: string;
  /** Legacy fixtures/user.json email; auth-service registers each email once, so the real user gets a unique one. */
  LegacyEmail: string;
  Email: string;
  Password: string;
  /** Legacy fake JWT sub / user.json id; auth-service assigns the real user id (GET /api/v1/auth/profile). */
  LegacyUserId: string;
  UserId: string;
  /** Legacy document.json id; document-service assigns the real id (POST /api/v1/documents response). */
  LegacyDocumentId: string;
  DocumentId: string;
  /** Legacy otter_starred_items seed; the real star is written by the app's Star button (starredApi is localStorage-only, no HTTP API). */
  LegacyStarredItems: typeof legacy.starredItems;
};

export const test = base.extend<{ SavedDocument: SavedDocument }>({
  SavedDocument: async ({ request, page }, provide) => {
    const email = `cypress-starred-${randomUUID()}@example.com`;
    const password = "Starred-Test-2026!";
    const registration = await request.post("/api/v1/auth/register", {
      data: { displayName: legacy.user.displayName, email, password },
    });
    await expect(registration).toBeOK();
    const tokens = await registration.json();
    const headers = { Authorization: `Bearer ${tokens.accessToken}` };

    const profile = await request.get("/api/v1/auth/profile", { headers });
    await expect(profile).toBeOK();
    const user = await profile.json();
    expect(user.email).toBe(email);
    expect(user.id).not.toBe(legacy.user.id);

    const created = await request.post("/api/v1/documents", {
      headers,
      data: { title: legacy.document.title, content: legacy.document.content },
    });
    await expect(created).toBeOK();
    const document = await created.json();
    expect(document.title).toBe(legacy.document.title);

    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);

    await provide({
      Title: legacy.document.title,
      Content: legacy.document.content,
      DisplayName: legacy.user.displayName,
      LegacyEmail: legacy.user.email,
      Email: email,
      Password: password,
      LegacyUserId: legacy.user.id,
      UserId: user.id,
      LegacyDocumentId: legacy.document.id,
      DocumentId: document.id,
      LegacyStarredItems: legacy.starredItems,
    });

    await expect(await request.delete(`/api/v1/documents/${document.id}`, { headers })).toBeOK();
  },
});

export { expect };
