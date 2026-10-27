import { test as base } from "@playwright/test";
import { seedSharedFile, seedStarredDocument } from "../support/sharing";

type DesignRow = { TestCaseId: string; Instance: string; FileName: string; DocumentTitle: string; Action: string };
type SharedInstance = DesignRow & Awaited<ReturnType<typeof seedSharedFile>>;
type Fixtures = { SharedFile: SharedInstance; OpenSharedFile: SharedInstance; StarredDocument: DesignRow };

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
    const row = { TestCaseId: "TC-SHARE-003", Instance: "StarredDocument", FileName: "", DocumentTitle: "Quarterly Planning", Action: "" };
    await seedStarredDocument(request, page, row.DocumentTitle);
    await page.goto("/starred");
    await use(row);
  },
});
export { expect } from "@playwright/test";
