import type { Workspace } from "../otterworks-api";
import type { ToscaInstance } from "../types";

// Kept for traceability only: TC-TPL-001..003 are retired and have no spec,
// because the client app has no templates screen. See parity/templates.md.
// RUN-TEMPLATE-2024-08 left no screenshots, so this workspace is the
// Documents fixture user with no documents; user-123 is a fixture ID.
const workspace: Workspace = {
  user: {
    id: "user-123",
    email: "alex.morgan@example.test",
    displayName: "Alex Morgan",
    createdAt: "2025-01-15T12:00:00.000Z",
  },
  documents: [],
};

export const TemplateCollection: ToscaInstance = {
  testCaseId: "TC-TPL-001",
  sheet: "Templates",
  instance: "TemplateCollection",
  row: {
    TestCaseId: "TC-TPL-001",
    Instance: "TemplateCollection",
    TemplateName: "Project brief",
    Result: "",
    Query: "",
  },
  workspace,
};

// Query is empty in the sheet, so the 2024-08 pass typed nothing into the
// filter; see parity/templates.md TC-TPL-002.
export const TemplateFilter: ToscaInstance = {
  testCaseId: "TC-TPL-002",
  sheet: "Templates",
  instance: "TemplateFilter",
  row: {
    TestCaseId: "TC-TPL-002",
    Instance: "TemplateFilter",
    TemplateName: "Project brief",
    Result: "Project brief",
    Query: "",
  },
  workspace,
};

export const CreateFromTemplate: ToscaInstance = {
  testCaseId: "TC-TPL-003",
  sheet: "Templates",
  instance: "CreateFromTemplate",
  row: {
    TestCaseId: "TC-TPL-003",
    Instance: "CreateFromTemplate",
    TemplateName: "Project brief",
    Result: "",
    Query: "",
  },
  workspace,
};
