import { test as base } from "@playwright/test";
import { seedWorkspace } from "../support/workspace";

type DesignRow = { TestCaseId: string; Instance: string; Title: string; ExpectedDocumentCount: string; Filter: string };
type Instance = DesignRow & Awaited<ReturnType<typeof seedWorkspace>>;
type Fixtures = { DocumentList: Instance; OpenDocument: Instance; DashboardCount: Instance & { ToscaExpectedDocumentCount: string }; FilterDocument: Instance };

export const test = base.extend<Fixtures>({
  DocumentList: async ({ request, page }, use) => {
    const workspace = await seedWorkspace(request, page);
    await page.goto("/documents");
    await use({ TestCaseId: "TC-DOC-001", Instance: "DocumentList", Title: "Quarterly Planning", ExpectedDocumentCount: "", Filter: "", ...workspace });
  },
  OpenDocument: async ({ request, page }, use) => {
    const workspace = await seedWorkspace(request, page);
    await page.goto("/documents");
    await use({ TestCaseId: "TC-DOC-002", Instance: "OpenDocument", Title: "Quarterly Planning", ExpectedDocumentCount: "", Filter: "", ...workspace });
  },
  DashboardCount: async ({ request, page }, use) => {
    const workspace = await seedWorkspace(request, page);
    await page.goto("/dashboard");
    // ExecutionLogs/Screenshots/dashboard.png and Modules/Dashboard.xml MA-DASH-002 InnerText show 4; API total is 4.
    await use({ TestCaseId: "TC-DOC-003", Instance: "DashboardCount", Title: "", ToscaExpectedDocumentCount: "3", ExpectedDocumentCount: String(workspace.documents.length), Filter: "", ...workspace });
  },
  FilterDocument: async ({ request, page }, use) => {
    const workspace = await seedWorkspace(request, page);
    await page.goto("/documents");
    await use({ TestCaseId: "TC-DOC-004", Instance: "FilterDocument", Title: "Quarterly Planning", ExpectedDocumentCount: "", Filter: "Planning", ...workspace });
  },
});
export { expect } from "@playwright/test";
