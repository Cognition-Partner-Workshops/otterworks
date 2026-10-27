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

export type MockFile = {
  id: string;
  name: string;
  mime_type: string;
  owner_id: string;
  folder_id: string;
  tags: string[];
  size: number;
  created_at: string;
  updated_at: string;
};

export type Workspace = {
  user: {
    id: string;
    email: string;
    displayName: string;
    createdAt: string;
    // Only needed by TestCases that sign in through the login form.
    password?: string;
  };
  documents: MockDocument[];
  files?: MockFile[];
};

type MockAccount = Workspace["user"];

// Unsigned JWT-shaped token: the client only reads the `sub` claim.
export function mockAccessToken(userId: string): string {
  const claims = Buffer.from(JSON.stringify({ sub: userId })).toString(
    "base64url",
  );
  return `header.${claims}.sig`;
}

function subjectOf(authorization: string | undefined): string | null {
  const match = authorization?.match(/^Bearer\s+[^.]+\.([^.]+)\.[^.]+$/i);
  if (!match) return null;
  try {
    const claims = JSON.parse(Buffer.from(match[1], "base64url").toString());
    return typeof claims.sub === "string" ? claims.sub : null;
  } catch {
    return null;
  }
}

// auth-service GlobalExceptionHandler body.
function authServiceError(status: number, error: string, message: string) {
  return {
    status,
    json: {
      timestamp: new Date().toISOString(),
      status,
      error,
      message,
    },
  };
}

// auth-service AuthResponse (Spring's default camelCase Jackson naming).
function authResponse(account: MockAccount) {
  return {
    accessToken: mockAccessToken(account.id),
    refreshToken: `refresh-${account.id}`,
    tokenType: "Bearer",
    expiresIn: 3600,
    user: {
      id: account.id,
      email: account.email,
      displayName: account.displayName,
      avatarUrl: null,
    },
  };
}

// Bean Validation's @Email accepts a local part, "@" and a domain.
const BEAN_VALIDATION_EMAIL = /^[^@\s]+@[^@\s]+$/;

function isBlank(value: unknown): boolean {
  return typeof value !== "string" || value.trim() === "";
}

export async function mockOtterWorksApi(
  page: Page,
  workspace: Workspace,
  testInfo: TestInfo,
): Promise<() => Promise<void>> {
  const unmockedApiCalls: string[] = [];
  const accounts: MockAccount[] = [workspace.user];

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());
    const method = request.method();
    const path = pathname.replace(/\/$/, "");

    if (method === "POST" && path === "/api/v1/auth/login") {
      const body = request.postDataJSON() ?? {};
      const fieldErrors = [
        isBlank(body.email) && "email: must not be blank",
        !isBlank(body.email) &&
          !BEAN_VALIDATION_EMAIL.test(body.email) &&
          "email: must be a well-formed email address",
        isBlank(body.password) && "password: must not be blank",
      ].filter(Boolean);
      if (fieldErrors.length > 0) {
        await route.fulfill(
          authServiceError(400, "Bad Request", fieldErrors.join(", ")),
        );
        return;
      }

      const account = accounts.find(
        (candidate) => candidate.email === body.email,
      );
      if (!account || account.password !== body.password) {
        await route.fulfill(
          authServiceError(400, "Bad Request", "Invalid credentials"),
        );
        return;
      }

      await route.fulfill({ json: authResponse(account) });
      return;
    }

    if (method === "POST" && path === "/api/v1/auth/register") {
      const body = request.postDataJSON() ?? {};
      const fieldErrors = [
        isBlank(body.email) && "email: must not be blank",
        !isBlank(body.email) &&
          !BEAN_VALIDATION_EMAIL.test(body.email) &&
          "email: must be a well-formed email address",
        isBlank(body.password) && "password: must not be blank",
        typeof body.password === "string" &&
          (body.password.length < 8 || body.password.length > 128) &&
          "password: size must be between 8 and 128",
        isBlank(body.displayName) && "displayName: must not be blank",
        typeof body.displayName === "string" &&
          body.displayName.length > 100 &&
          "displayName: size must be between 1 and 100",
      ].filter(Boolean);
      if (fieldErrors.length > 0) {
        await route.fulfill(
          authServiceError(400, "Bad Request", fieldErrors.join(", ")),
        );
        return;
      }

      if (accounts.some((candidate) => candidate.email === body.email)) {
        await route.fulfill(
          authServiceError(400, "Bad Request", "Email already registered"),
        );
        return;
      }

      const account: MockAccount = {
        id: `user-${accounts.length + 123}`,
        email: body.email,
        displayName: body.displayName,
        createdAt: new Date().toISOString(),
        password: body.password,
      };
      accounts.push(account);
      await route.fulfill({ status: 201, json: authResponse(account) });
      return;
    }

    if (method === "GET" && path === "/api/v1/auth/profile") {
      const userId = subjectOf(request.headers()["authorization"]);
      const account = accounts.find((candidate) => candidate.id === userId);
      if (!account) {
        // api-gateway JWT middleware rejects a missing or invalid bearer.
        await route.fulfill({
          status: 401,
          json: { error: "missing or invalid authorization header" },
        });
        return;
      }

      await route.fulfill({
        json: {
          id: account.id,
          email: account.email,
          display_name: account.displayName,
          created_at: account.createdAt,
        },
      });
      return;
    }

    if (method === "POST" && path === "/api/v1/auth/logout") {
      await route.fulfill({ status: 204 });
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

    if (method === "GET" && path === "/api/v1/search") {
      const parseInteger = (value: string | null, defaultValue: string) => {
        const rawValue = value ?? defaultValue;
        return /^\s*[+-]?\d+\s*$/.test(rawValue)
          ? Number(rawValue)
          : null;
      };
      const requestedPage = parseInteger(searchParams.get("page"), "1");
      const requestedSize = parseInteger(searchParams.get("size"), "20");

      if (requestedPage === null || requestedSize === null) {
        await route.fulfill({
          status: 400,
          json: { error: "Invalid page or size parameter" },
        });
        return;
      }

      const query = searchParams.get("q") ?? "";

      if (!query) {
        await route.fulfill({
          status: 400,
          json: { error: "Query parameter 'q' is required" },
        });
        return;
      }

      const pageNumber = Math.max(1, requestedPage);
      const size = Math.max(1, Math.min(100, requestedSize));
      const docType = searchParams.get("type") || null;
      const indices: ("documents" | "files")[] =
        docType === "document"
          ? ["documents"]
          : docType === "file"
            ? ["files"]
            : ["documents", "files"];
      const multiIndex = indices.length > 1;
      const queryTokens = query
        .toLowerCase()
        .split(/[^\p{L}\p{N}]+/u)
        .filter(Boolean);
      const tokenize = (text: string) =>
        text
          .toLowerCase()
          .split(/[^\p{L}\p{N}]+/u)
          .filter(Boolean);
      // Approximate MeiliSearch's default token-prefix matching for the fixture search.
      const matchesQuery = (text: string) => {
        const textTokens = tokenize(text);
        const lastQueryToken = queryTokens[queryTokens.length - 1];
        return (
          queryTokens.length > 0 &&
          queryTokens
            .slice(0, -1)
            .every((token) => textTokens.includes(token)) &&
          textTokens.some((token) => token.startsWith(lastQueryToken))
        );
      };
      const highlight = (text: string) =>
        text.replace(/[\p{L}\p{N}]+/gu, (word) => {
          const matchedToken = queryTokens
            .filter((token) => word.toLowerCase().startsWith(token))
            .sort((first, second) => second.length - first.length)[0];
          return matchedToken
            ? `<em>${word.slice(0, matchedToken.length)}</em>${word.slice(matchedToken.length)}`
            : word;
        });
      type SearchRecord = {
        id: string;
        title: string;
        content: string;
        owner_id: string;
        tags: string[];
        created_at: string;
        updated_at: string;
      } & (
        | { type: "document" }
        | {
            type: "file";
            mime_type: string;
            folder_id: string;
            size: number;
          }
      );
      const documents: SearchRecord[] = workspace.documents
        .filter(
          (document) =>
            !document.is_deleted && document.owner_id === workspace.user.id,
        )
        .map((document) => ({
          id: document.id,
          title: document.title,
          content: document.content,
          owner_id: document.owner_id,
          tags: [] as string[],
          created_at: document.created_at,
          updated_at: document.updated_at,
          type: "document" as const,
        }));
      const files: SearchRecord[] = (workspace.files ?? [])
        .filter((file) => file.owner_id === workspace.user.id)
        .map((file) => ({
          id: file.id,
          title: file.name,
          content: "",
          owner_id: file.owner_id,
          tags: file.tags,
          created_at: file.created_at,
          updated_at: file.updated_at,
          type: "file" as const,
          mime_type: file.mime_type,
          folder_id: file.folder_id,
          size: file.size,
        }));
      const indexRecords: Record<"documents" | "files", SearchRecord[]> = {
        documents,
        files,
      };
      const results: Record<string, unknown>[] = [];
      let total = 0;

      for (const index of indices) {
        const records = indexRecords[index].filter(
          (record) =>
            (!docType || record.type === docType) &&
            matchesQuery(`${record.title} ${record.content}`),
        );
        const rankedRecords = records
          .map((record, fixtureOrder) => ({
            record,
            fixtureOrder,
            titleMatches: matchesQuery(record.title),
          }))
          .sort(
            (first, second) =>
              Number(second.titleMatches) -
                Number(first.titleMatches) ||
              first.fixtureOrder - second.fixtureOrder,
          );
        total += records.length;
        const pageRecords = multiIndex
          ? rankedRecords.slice(0, pageNumber * size)
          : rankedRecords.slice(
              (pageNumber - 1) * size,
              pageNumber * size,
            );

        for (const { record } of pageRecords) {
          const highlightedTitle = highlight(record.title);
          const highlightedContent = highlight(record.content);
          const isFile = record.type === "file";
          const highlights: Record<string, string[]> = {};

          if (highlightedTitle.includes("<em>")) {
            highlights[isFile ? "name" : "title"] = [highlightedTitle];
          }
          if (!isFile && highlightedContent.includes("<em>")) {
            highlights.content = [highlightedContent];
          }

          results.push({
            id: record.id,
            title: record.title,
            content_snippet: isFile ? "" : highlightedContent.slice(0, 200),
            type: record.type,
            owner_id: record.owner_id,
            tags: record.tags,
            score: 0,
            highlights,
            created_at: record.created_at,
            updated_at: record.updated_at,
            ...(record.type === "file"
              ? {
                  mime_type: record.mime_type,
                  folder_id: record.folder_id,
                  size: record.size,
                }
              : {}),
          });
        }
      }

      await route.fulfill({
        json: {
          results: multiIndex
            ? results.slice((pageNumber - 1) * size, pageNumber * size)
            : results,
          total,
          page: pageNumber,
          page_size: size,
          query,
        },
      });
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
