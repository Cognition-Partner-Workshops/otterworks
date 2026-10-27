import { test as base } from "@playwright/test";
import { seedSharedFile, seedStarredDocument } from "../support/sharing";
import { deleteDocument } from "../support/workspace";

type DesignRow = { TestCaseId: string; Instance: string; FileName: string; DocumentTitle: string; Action: string };
type SharedInstance = DesignRow & Awaited<ReturnType<typeof seedSharedFile>>;
type StarredInstance = DesignRow & {
  userId: string;
  documentId: string;
  headers: { Authorization: string };
  documents: { id: string; title: string }[];
  LegacyUserId: string;
  LegacyEmail: string;
  LegacyDocumentId: string;
  LegacyContent: string;
  LegacyStarredItems: Record<string, { itemId: string; itemType: string; starredAt: string }>;
};
type Fixtures = { SharedFile: SharedInstance; OpenSharedFile: SharedInstance; StarredDocument: StarredInstance };

export const test = base.extend<Fixtures>({
  SharedFile: async ({ request, page }, use) => {
    const row = { TestCaseId: "TC-SHARE-001", Instance: "SharedFile", FileName: "Roadmap.pdf", DocumentTitle: "", Action: "" };
    const file = await seedSharedFile(request, page, row.FileName);
    await page.goto("/shared");
    await use({ ...row, ...file });
  },
  OpenSharedFile: async ({ request, page }, use) => {
    const row = { TestCaseId: "TC-SHARE-002", Instance: "OpenSharedFile", FileName: "Roadmap.pdf", DocumentTitle: "", Action: "" };
    const file = await seedSharedFile(request, page, row.FileName);
    await page.goto("/shared");
    await use({ ...row, ...file });
  },
  StarredDocument: async ({ request, page }, use) => {
    const row = {
      TestCaseId: "TC-SHARE-003",
      Instance: "StarredDocument",
      FileName: "",
      DocumentTitle: "Quarterly Planning",
      Action: "",
      LegacyUserId: "user-123",
      LegacyEmail: "alex.morgan@example.test",
      LegacyDocumentId: "doc-101",
      LegacyContent: "Review objectives, delivery dates, and ownership for the next quarter.",
      LegacyStarredItems: {
        "user-123:doc-101": {
          itemId: "doc-101",
          itemType: "document",
          starredAt: "2025-02-18T08:00:00.000Z",
        },
      },
    };
    const workspace = await seedStarredDocument(request, page, row.DocumentTitle);
    await use({ ...row, ...workspace });
    for (const document of workspace.documents) {
      await deleteDocument(request, workspace.headers, document.id);
    }
  },
});
export { expect } from "@playwright/test";
