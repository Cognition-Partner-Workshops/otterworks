import { type APIRequestContext, type Page, request } from "@playwright/test";

const API_URL = process.env.API_URL || "http://localhost:8080";
const LOCALSTACK_URL = process.env.LOCALSTACK_URL || "http://localhost:4566";

export interface ApiUser {
  id: string;
  email: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
}

export async function apiContext(): Promise<APIRequestContext> {
  return request.newContext({ baseURL: API_URL });
}

export async function registerViaApi(api: APIRequestContext, displayName = "Browse Otter"): Promise<ApiUser> {
  const email = `browse-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@otterworks.test`;
  const res = await api.post("/api/v1/auth/register", {
    data: { email, password: "OtterworksTest123!", displayName },
  });
  if (res.status() !== 201) throw new Error(`register failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return {
    id: body.user.id,
    email,
    displayName,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

/** Seed browser localStorage so the SPA boots already signed in. */
export async function signInWithTokens(page: Page, user: ApiUser) {
  await page.addInitScript(
    ([access, refresh]) => {
      localStorage.setItem("otter_access_token", access);
      localStorage.setItem("otter_refresh_token", refresh);
    },
    [user.accessToken, user.refreshToken]
  );
}

export async function createFolder(
  api: APIRequestContext,
  user: ApiUser,
  name: string,
  parentId: string | null = null
): Promise<{ id: string; name: string }> {
  const res = await api.post("/api/v1/folders", {
    headers: { Authorization: `Bearer ${user.accessToken}` },
    data: { name, parent_id: parentId, owner_id: user.id },
  });
  if (res.status() !== 201) throw new Error(`create folder failed: ${res.status()} ${await res.text()}`);
  return res.json();
}

export async function createDocument(api: APIRequestContext, user: ApiUser, title: string) {
  const res = await api.post("/api/v1/documents/", {
    headers: { Authorization: `Bearer ${user.accessToken}` },
    data: { title, content: "browsing e2e" },
  });
  if (res.status() !== 201) throw new Error(`create document failed: ${res.status()} ${await res.text()}`);
  return res.json();
}

/** Insert unread in-app notifications directly into the local DynamoDB table (LocalStack). */
export async function seedNotifications(user: ApiUser, titles: string[]) {
  const ctx = await request.newContext();
  for (const title of titles) {
    const res = await ctx.post(LOCALSTACK_URL, {
      headers: {
        "X-Amz-Target": "DynamoDB_20120810.PutItem",
        "Content-Type": "application/x-amz-json-1.0",
        Authorization:
          "AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/dynamodb/aws4_request, SignedHeaders=host, Signature=0",
      },
      data: JSON.stringify({
        TableName: "otterworks-notifications",
        Item: {
          id: { S: crypto.randomUUID() },
          userId: { S: user.id },
          type: { S: "file_shared" },
          title: { S: title },
          message: { S: "A teammate shared a file with you" },
          resourceId: { S: crypto.randomUUID() },
          resourceType: { S: "file" },
          actorId: { S: "browsing-e2e" },
          read: { BOOL: false },
          deliveredVia: { L: [{ S: "IN_APP" }] },
          createdAt: { S: new Date().toISOString() },
        },
      }),
    });
    if (!res.ok()) throw new Error(`seed notification failed: ${res.status()} ${await res.text()}`);
  }
  await ctx.dispose();
}
