import type { Page, TestInfo } from "@playwright/test";

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
  // Settings
  settings?: MockSettings;
};

// Settings — auth-service UserSettingsDTO (camelCase).
export type MockSettings = {
  notificationEmail: boolean;
  notificationInApp: boolean;
  notificationDesktop: boolean;
  theme: string;
  language: string;
};

export async function mockOtterWorksApi(
  page: Page,
  workspace: Workspace,
  testInfo: TestInfo,
): Promise<() => Promise<void>> {
  const unmockedApiCalls: string[] = [];

  // Settings — per-test state; auth-service UserDTO and UserSettings defaults.
  const user = { ...workspace.user, avatarUrl: null as string | null,
    roles: ["USER"], emailVerified: false, updatedAt: workspace.user.createdAt,
    lastLoginAt: null };
  const settings: MockSettings = { notificationEmail: true, notificationInApp: true,
    notificationDesktop: false, theme: "system", language: "en", ...workspace.settings };

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());
    const method = request.method();
    const path = pathname.replace(/\/$/, "");

    if (method === "GET" && path === "/api/v1/auth/profile") {
      await route.fulfill({
        json: {
          // Settings — AuthController returns UserDTO in camelCase.
          ...user,
        },
      });
      return;
    }

    // Settings — AuthController uses PUT, not PATCH, for profile updates.
    if (path === "/api/v1/auth/profile") {
      if (method !== "PUT") {
        await route.fulfill({ status: 405, json: { error: "Method Not Allowed" } });
        return;
      }
      const body = request.postDataJSON();
      if ((body.displayName != null && (body.displayName.length < 1 || body.displayName.length > 100)) ||
          (body.avatarUrl != null && body.avatarUrl.length > 500)) {
        await route.fulfill({ status: 400, json: { error: "Bad Request" } });
        return;
      }
      if (body.displayName != null) user.displayName = body.displayName;
      if (body.avatarUrl != null) user.avatarUrl = body.avatarUrl;
      user.updatedAt = new Date().toISOString();
      await route.fulfill({ json: user });
      return;
    }

    // Settings — SettingsController / UserSettingsService apply non-null fields only.
    if (path === "/api/v1/settings") {
      if (method === "PATCH") {
        const body = request.postDataJSON();
        for (const key of Object.keys(settings) as (keyof MockSettings)[]) {
          if (body[key] != null) Object.assign(settings, { [key]: body[key] });
        }
      } else if (method !== "GET") {
        await route.fulfill({ status: 405, json: { error: "Method Not Allowed" } });
        return;
      }
      await route.fulfill({ json: settings });
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
