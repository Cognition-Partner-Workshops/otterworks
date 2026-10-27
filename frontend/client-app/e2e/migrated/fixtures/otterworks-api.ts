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
    // Only needed by TestCases that sign in through the login form.
    password?: string;
  };
  documents: MockDocument[];
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
