import { DocumentList } from "./documents";
import type { Workspace } from "../otterworks-api";
import type { ToscaInstance } from "../types";

// File/share UUIDs are invented; name, size and date come from sharing.png.
const fileId = "10000000-0000-4000-8000-000000000001";
const workspace: Workspace = {
  user: DocumentList.workspace.user,
  documents: DocumentList.workspace.documents,
  files: [{
    id: fileId, name: "Roadmap.pdf", mime_type: "application/pdf",
    size_bytes: 245760, s3_key: "sharing/Roadmap.pdf", folder_id: null,
    owner_id: "10000000-0000-4000-8000-000000000002", version: 1,
    is_trashed: false, created_at: "2025-02-18T10:00:00Z", updated_at: "2025-02-18T10:00:00Z",
  }],
  shares: [{
    id: "10000000-0000-4000-8000-000000000003", file_id: fileId,
    shared_with: DocumentList.workspace.user.id, permission: "viewer",
    shared_by: "10000000-0000-4000-8000-000000000002", created_at: "2025-02-18T10:00:00Z",
  }],
  // starred.png shows only Quarterly Planning; stars are client-local, not a service listing.
  starred: [{ itemId: "doc-101", itemType: "document", starredAt: "2025-02-18T10:00:00Z" }],
};

export const SharedFile: ToscaInstance = {
  testCaseId: "TC-SHARE-001", sheet: "Sharing", instance: "SharedFile",
  row: { TestCaseId: "TC-SHARE-001", Instance: "SharedFile", FileName: "Roadmap.pdf", DocumentTitle: "", Action: "" },
  workspace,
};
export const OpenSharedFile: ToscaInstance = {
  testCaseId: "TC-SHARE-002", sheet: "Sharing", instance: "OpenSharedFile",
  row: { TestCaseId: "TC-SHARE-002", Instance: "OpenSharedFile", FileName: "Roadmap.pdf", DocumentTitle: "", Action: "" },
  workspace,
};
export const StarredDocument: ToscaInstance = {
  testCaseId: "TC-SHARE-003", sheet: "Sharing", instance: "StarredDocument",
  row: { TestCaseId: "TC-SHARE-003", Instance: "StarredDocument", FileName: "", DocumentTitle: "Quarterly Planning", Action: "" },
  workspace,
};
