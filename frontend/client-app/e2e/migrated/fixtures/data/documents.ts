import type { MockDocument, Workspace } from "../otterworks-api";
import type { ToscaInstance } from "../types";

// doc-101 is the Tosca module Href; doc-102–doc-104 are fixture IDs.
const documents: MockDocument[] = [
  {
    id: "doc-101",
    title: "Quarterly Planning",
    content:
      "Review objectives, delivery dates, and ownership for the next quarter.",
    content_type: "text/markdown",
    owner_id: "user-123",
    folder_id: null,
    is_deleted: false,
    is_template: false,
    word_count: 10,
    version: 1,
    created_at: "2025-02-01T10:30:00Z",
    updated_at: "2025-02-18T10:30:00Z",
  },
  {
    id: "doc-102",
    title: "Release Checklist",
    content:
      "Confirm approvals, smoke tests, and release notes before publishing.",
    content_type: "text/markdown",
    owner_id: "user-123",
    folder_id: null,
    is_deleted: false,
    is_template: false,
    word_count: 9,
    version: 1,
    created_at: "2025-02-01T10:30:00Z",
    updated_at: "2025-02-17T10:30:00Z",
  },
  {
    id: "doc-103",
    title: "Support Handoff",
    content:
      "Open items and escalation contacts for the support rotation.",
    content_type: "text/markdown",
    owner_id: "user-123",
    folder_id: null,
    is_deleted: false,
    is_template: false,
    word_count: 9,
    version: 1,
    created_at: "2025-02-01T10:30:00Z",
    updated_at: "2025-02-16T10:30:00Z",
  },
  {
    id: "doc-104",
    title: "Workspace Guide",
    content: "A short guide to folders, search, and shared documents.",
    content_type: "text/markdown",
    owner_id: "user-123",
    folder_id: null,
    is_deleted: false,
    is_template: false,
    word_count: 9,
    version: 1,
    created_at: "2025-02-01T10:30:00Z",
    updated_at: "2025-02-15T10:30:00Z",
  },
];

const workspace: Workspace = {
  user: {
    id: "user-123",
    email: "alex.morgan@example.test",
    displayName: "Alex Morgan",
    createdAt: "2025-01-15T12:00:00.000Z",
  },
  documents,
};

export const DocumentList: ToscaInstance = {
  testCaseId: "TC-DOC-001",
  sheet: "Documents",
  instance: "DocumentList",
  row: {
    TestCaseId: "TC-DOC-001",
    Instance: "DocumentList",
    Title: "Quarterly Planning",
    ExpectedDocumentCount: "",
    Filter: "",
  },
  workspace,
};

export const OpenDocument: ToscaInstance = {
  testCaseId: "TC-DOC-002",
  sheet: "Documents",
  instance: "OpenDocument",
  row: {
    TestCaseId: "TC-DOC-002",
    Instance: "OpenDocument",
    Title: "Quarterly Planning",
    ExpectedDocumentCount: "",
    Filter: "",
  },
  workspace,
};

export const DashboardCount: ToscaInstance & {
  expected: { documentCount: number };
} = {
  testCaseId: "TC-DOC-003",
  sheet: "Documents",
  instance: "DashboardCount",
  row: {
    TestCaseId: "TC-DOC-003",
    Instance: "DashboardCount",
    Title: "",
    ExpectedDocumentCount: "3",
    Filter: "",
  },
  workspace,
  // Data sheet value 3 is stale; see parity table TC-DOC-003.
  expected: { documentCount: 4 },
};

export const FilterDocument: ToscaInstance = {
  testCaseId: "TC-DOC-004",
  sheet: "Documents",
  instance: "FilterDocument",
  row: {
    TestCaseId: "TC-DOC-004",
    Instance: "FilterDocument",
    Title: "Quarterly Planning",
    ExpectedDocumentCount: "",
    Filter: "Planning",
  },
  workspace,
};
