import type { MockDocument, MockFile, Workspace } from "../otterworks-api";
import type { ToscaInstance } from "../types";

const documents: MockDocument[] = [
  // doc-101 is the Tosca module Href; content/date are from the Tosca search.png screenshot.
  {
    id: "doc-101",
    title: "Quarterly Planning",
    content: "Review quarterly objectives and dates.",
    content_type: "text/markdown",
    owner_id: "user-123",
    folder_id: null,
    is_deleted: false,
    is_template: false,
    word_count: 5,
    version: 1,
    created_at: "2025-02-01T10:30:00Z",
    updated_at: "2025-02-18T10:30:00Z",
  },
  // doc-102–doc-104 are invented fixture IDs; only doc-101 comes from the Tosca module Href.
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
    content: "Open items and escalation contacts for the support rotation.",
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

// These fixture-only files let TC-SRCH-002 prove type filtering and owner scoping; file-201/file-202 and owner user-456 are invented fixture IDs.
const files: MockFile[] = [
  {
    id: "file-201",
    name: "Release Notes.pdf",
    mime_type: "application/pdf",
    owner_id: "user-123",
    folder_id: "",
    tags: [],
    size: 48213,
    created_at: "2025-02-10T09:00:00Z",
    updated_at: "2025-02-17T09:00:00Z",
  },
  {
    id: "file-202",
    name: "Quarterly Forecast.xlsx",
    mime_type:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    owner_id: "user-456",
    folder_id: "",
    tags: [],
    size: 20480,
    created_at: "2025-02-12T09:00:00Z",
    updated_at: "2025-02-12T09:00:00Z",
  },
];

const workspace: Workspace = {
  user: {
    // user-123 matches the Documents fixture.
    id: "user-123",
    email: "alex.morgan@example.test",
    displayName: "Alex Morgan",
    createdAt: "2025-01-15T12:00:00.000Z",
  },
  documents,
  files,
};

export const TitleSearch: ToscaInstance = {
  testCaseId: "TC-SRCH-001",
  sheet: "Search",
  instance: "TitleSearch",
  row: {
    TestCaseId: "TC-SRCH-001",
    Instance: "TitleSearch",
    Query: "quarterly",
    Result: "Quarterly Planning",
    Type: "all",
  },
  workspace,
};

export const DocumentType: ToscaInstance = {
  testCaseId: "TC-SRCH-002",
  sheet: "Search",
  instance: "DocumentType",
  row: {
    TestCaseId: "TC-SRCH-002",
    Instance: "DocumentType",
    Query: "release",
    Result: "Release Checklist",
    Type: "document",
  },
  workspace,
};

export const NoResults: ToscaInstance & {
  expected: { emptyStateTitle: string };
} = {
  testCaseId: "TC-SRCH-003",
  sheet: "Search",
  instance: "NoResults",
  row: {
    TestCaseId: "TC-SRCH-003",
    Instance: "NoResults",
    Query: "unmatchedquery",
    Result: "",
    Type: "all",
  },
  workspace,
  // TestStep 3 verifies "0 results", which the app never renders; see parity table TC-SRCH-003.
  expected: { emptyStateTitle: "No results found" },
};
