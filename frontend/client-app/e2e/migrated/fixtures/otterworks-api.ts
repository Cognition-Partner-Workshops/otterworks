import type { Page, TestInfo } from "@playwright/test";

// --- Sharing folder ---
export type MockFile = {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  s3_key: string;
  folder_id: string | null;
  owner_id: string;
  version: number;
  is_trashed: boolean;
  created_at: string;
  updated_at: string;
};
export type MockShare = {
  id: string;
  file_id: string;
  shared_with: string;
  permission: "viewer" | "editor";
  shared_by: string;
  created_at: string;
};

export type MockDocument = {
  id: string;
  title: string;
  content: string;
  content_type: string;
  owner_id: string;
  folder_id: string | null;
  is_deleted: boolean;
  is_template: boolean;
  word_count: number;
  version: number;
  created_at: string;
  updated_at: string;
};

export type Workspace = {
  user: {
    id: string;
    email: string;
    displayName: string;
    createdAt: string;
  };
  documents: MockDocument[];
  // --- Sharing folder ---
  files?: MockFile[];
  shares?: MockShare[];
  starred?: { itemId: string; itemType: "file" | "folder" | "document"; starredAt: string }[];
};

export async function mockOtterWorksApi(
  page: Page,
  workspace: Workspace,
  testInfo: TestInfo,
): Promise<() => Promise<void>> {
  const unmockedApiCalls: string[] = [];

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());
    const method = request.method();
    const path = pathname.replace(/\/$/, "");

    // --- Sharing folder ---
    // handlers::list_shared_files: share scan order, deduplication, no sorting.
    if (method === "GET" && path === "/api/v1/files/shared") {
      const ids = [...new Set((workspace.shares ?? [])
        .filter((share) => share.shared_with === workspace.user.id)
        .map((share) => share.file_id))];
      const files = ids.flatMap((id) => (workspace.files ?? [])
        .filter((file) => file.id === id && !file.is_trashed));
      const pageNumber = Math.max(1, Number(searchParams.get("page") ?? 1));
      const size = Math.min(100, Number(searchParams.get("page_size") ?? 50));
      await route.fulfill({ json: {
        files: files.slice((pageNumber - 1) * size, pageNumber * size),
        total: files.length, page: pageNumber, page_size: size,
      } });
      return;
    }

    const fileMatch = path.match(/^\/api\/v1\/files\/([^/]+)(\/download)?$/);
    if (method === "GET" && fileMatch && workspace.files) {
      const file = workspace.files.find((candidate) => candidate.id === fileMatch[1]);
      if (!file) {
        await route.fulfill({ status: 404, json: {
          error: "file_not_found", message: `File not found: ${fileMatch[1]}`,
        } });
      } else if (fileMatch[2]) {
        await route.fulfill({ json: {
          url: `${new URL(request.url()).origin}/sharing-preview.pdf`, expires_in_secs: 3600,
        } });
      } else {
        await route.fulfill({ json: { ...file,
          shared_with: (workspace.shares ?? []).filter((share) => share.file_id === file.id),
        } });
      }
      return;
    }

    if (method === "GET" && path === "/api/v1/auth/profile") {
      await route.fulfill({
        json: {
          id: workspace.user.id,
          email: workspace.user.email,
          display_name: workspace.user.displayName,
          created_at: workspace.user.createdAt,
        },
      });
      return;
    }

    if (method === "GET" && path === "/api/v1/documents") {
      const documents = workspace.documents
        .filter((document) => !document.is_deleted && !document.is_template)
        .sort((first, second) =>
          second.updated_at.localeCompare(first.updated_at),
        );
      const total = documents.length;
      const requestedPage = Number(searchParams.get("page") ?? "1");
      const requestedSize = Number(searchParams.get("size") ?? "20");
      const pageNumber = Number.isFinite(requestedPage)
        ? Math.max(1, requestedPage)
        : 1;
      const size = Number.isFinite(requestedSize)
        ? Math.max(1, Math.min(100, requestedSize))
        : 20;

      await route.fulfill({
        json: {
          items: documents.slice((pageNumber - 1) * size, pageNumber * size),
          total,
          page: pageNumber,
          size,
          pages: Math.ceil(total / size),
        },
      });
      return;
    }

    const documentMatch = path.match(/^\/api\/v1\/documents\/([^/]+)$/);
    if (method === "GET" && documentMatch) {
      const document = workspace.documents.find(
        (candidate) =>
          candidate.id === documentMatch[1] && !candidate.is_deleted,
      );

      if (document) {
        await route.fulfill({ json: document });
      } else {
        await route.fulfill({
          status: 404,
          json: { detail: "Document not found" },
        });
      }
      return;
    }

    if (method === "GET" && path === "/api/v1/files") {
      await route.fulfill({ json: { files: [], total: 0 } });
      return;
    }

    if (method === "GET" && path === "/api/v1/files/activity") {
      await route.fulfill({ json: { items: [] } });
      return;
    }

    if (method === "GET" && path === "/api/v1/notifications/unread-count") {
      await route.fulfill({ json: { count: 0 } });
      return;
    }

    unmockedApiCalls.push(`${method} ${request.url()}`);
    await route.fulfill({ status: 200, json: {} });
  });

  return async () => {
    await testInfo.attach("unmocked-api-calls", {
      body: JSON.stringify(unmockedApiCalls, null, 2),
      contentType: "application/json",
    });
  };
}
