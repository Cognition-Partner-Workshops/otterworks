import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8080";

interface Account {
  id: string;
  email: string;
  name: string;
  accessToken: string;
  refreshToken: string;
}

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function register(request: APIRequestContext, label: string): Promise<Account> {
  const email = `share-${label}-${uid()}@otterworks.test`;
  const name = `Share ${label} ${uid()}`;
  const res = await request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password: "OtterworksTest123!", displayName: name },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return { id: body.user.id, email, name, accessToken: body.accessToken, refreshToken: body.refreshToken };
}

function auth(user: Account) {
  return { Authorization: `Bearer ${user.accessToken}` };
}

async function uploadFile(request: APIRequestContext, owner: Account, name: string): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/files/upload`, {
    headers: auth(owner),
    multipart: { file: { name, mimeType: "text/plain", buffer: Buffer.from(`body of ${name}`) } },
  });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()).file.id;
}

async function shareViaApi(request: APIRequestContext, owner: Account, fileId: string, to: Account) {
  const res = await request.post(`${API_BASE}/api/v1/files/${fileId}/share`, {
    headers: auth(owner),
    data: { shared_with: to.id, permission: "viewer", shared_by: owner.id },
  });
  expect(res.status(), await res.text()).toBe(201);
}

async function signIn(page: Page, user: Account) {
  await page.goto("/login");
  await page.evaluate(
    ([access, refresh]) => {
      localStorage.setItem("otter_access_token", access);
      localStorage.setItem("otter_refresh_token", refresh);
    },
    [user.accessToken, user.refreshToken]
  );
}

function fileCard(page: Page, fileName: string) {
  return page.locator(".group").filter({ hasText: fileName }).first();
}

async function openShareDialog(page: Page, fileName: string) {
  await page.goto("/files");
  const card = fileCard(page, fileName);
  await expect(card).toBeVisible({ timeout: 15_000 });
  await card.hover();
  await card.getByRole("button").last().click();
  await page.getByRole("button", { name: "Share", exact: true }).click();
  await expect(page.getByPlaceholder("Add people by email")).toBeVisible();
}

test.describe("Sharing (signed in)", () => {
  test("owner shares a file from the Files page and the recipient sees it in Shared with me", async ({
    page,
    request,
  }) => {
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const fileName = `ui-share-${uid()}.txt`;
    const fileId = await uploadFile(request, owner, fileName);

    await signIn(page, owner);
    await openShareDialog(page, fileName);
    await page.getByPlaceholder("Add people by email").fill(friend.email);
    const shareResponse = page.waitForResponse(
      (r) => r.url().includes(`/files/${fileId}/share`) && r.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Share", exact: true }).last().click();
    expect((await shareResponse).status()).toBe(201);

    await signIn(page, friend);
    await page.goto("/shared");
    await expect(page.getByRole("heading", { name: "Shared with me" })).toBeVisible();
    await expect(page.getByText(fileName)).toBeVisible({ timeout: 15_000 });
  });

  test("recipient with nothing shared sees the empty state", async ({ page, request }) => {
    const loner = await register(request, "loner");
    await signIn(page, loner);
    await page.goto("/shared");
    await expect(page.getByText("Nothing shared with you yet")).toBeVisible({ timeout: 15_000 });
  });

  test("trashing a shared file hides it from the recipient; restoring brings it back", async ({
    page,
    request,
  }) => {
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const fileName = `ui-trash-${uid()}.txt`;
    const fileId = await uploadFile(request, owner, fileName);
    await shareViaApi(request, owner, fileId, friend);

    const trash = await request.post(`${API_BASE}/api/v1/files/${fileId}/trash`, { headers: auth(owner) });
    expect(trash.status()).toBe(200);

    await signIn(page, friend);
    await page.goto("/shared");
    await expect(page.getByText("Nothing shared with you yet")).toBeVisible({ timeout: 15_000 });
    await page.goto("/trash");
    await expect(page.getByText("Trash is empty")).toBeVisible({ timeout: 15_000 });

    await signIn(page, owner);
    await page.goto("/trash");
    await expect(page.getByText(fileName)).toBeVisible({ timeout: 15_000 });
    await page.getByTitle("Restore").first().click();
    await expect(page.getByText("Trash is empty")).toBeVisible({ timeout: 15_000 });

    await signIn(page, friend);
    await page.goto("/shared");
    await expect(page.getByText(fileName)).toBeVisible({ timeout: 15_000 });
  });

  test("revoking access from the API removes the file from Shared with me", async ({ page, request }) => {
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const fileName = `ui-revoke-${uid()}.txt`;
    const fileId = await uploadFile(request, owner, fileName);
    await shareViaApi(request, owner, fileId, friend);

    await signIn(page, friend);
    await page.goto("/shared");
    await expect(page.getByText(fileName)).toBeVisible({ timeout: 15_000 });

    const revoke = await request.delete(`${API_BASE}/api/v1/files/${fileId}/share/${friend.id}`, {
      headers: auth(owner),
    });
    expect(revoke.status()).toBe(204);
    await page.reload();
    await expect(page.getByText("Nothing shared with you yet")).toBeVisible({ timeout: 15_000 });
  });

  test("document share link opens the document for another signed-in user", async ({ request }) => {
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const created = await request.post(`${API_BASE}/api/v1/documents/`, {
      headers: auth(owner),
      data: { title: `Link doc ${uid()}`, content: "link body", owner_id: owner.id },
    });
    expect(created.status(), await created.text()).toBe(201);
    const doc = await created.json();
    const minted = await request.post(`${API_BASE}/api/v1/documents/${doc.id}/share`, { headers: auth(owner) });
    expect(minted.status()).toBe(200);
    const { token } = await minted.json();
    const opened = await request.get(`${API_BASE}/api/v1/documents/shared`, {
      headers: auth(friend),
      params: { document_id: doc.id, token },
    });
    expect(opened.status()).toBe(200);
    expect((await opened.json()).content).toBe("link body");
  });

  test("[REAL] share dialog lists existing collaborators after reload", async ({ page, request }) => {
    test.fail(true, "[REAL] GET /files list omits shared_with, so the Files-page dialog always says no one has access");
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const fileName = `ui-collab-${uid()}.txt`;
    const fileId = await uploadFile(request, owner, fileName);
    await shareViaApi(request, owner, fileId, friend);

    await signIn(page, owner);
    await openShareDialog(page, fileName);
    await expect(page.getByText(friend.email)).toBeVisible({ timeout: 5_000 });
  });

  test("[REAL] document Invite grants the invitee access", async ({ page, request }) => {
    test.fail(true, "[REAL] document-editor Invite posts {users} to /documents/{id}/share, which only mints a link token");
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const created = await request.post(`${API_BASE}/api/v1/documents/`, {
      headers: auth(owner),
      data: { title: `Invite doc ${uid()}`, content: "invite body", owner_id: owner.id },
    });
    const doc = await created.json();
    await request.post(`${API_BASE}/api/v1/documents/${doc.id}/share`, {
      headers: auth(owner),
      data: { users: [{ userId: "", name: "", email: friend.email, permission: "edit" }] },
    });
    await signIn(page, friend);
    const res = await request.get(`${API_BASE}/api/v1/documents/${doc.id}`, { headers: auth(friend) });
    expect(res.status()).toBe(200);
  });

  test("[REAL] a viewer cannot move the owner's shared file to trash", async ({ request }) => {
    test.fail(true, "[REAL] file-service never enforces viewer permission (or ownership) on trash");
    const owner = await register(request, "owner");
    const friend = await register(request, "friend");
    const fileId = await uploadFile(request, owner, `ui-viewer-${uid()}.txt`);
    await shareViaApi(request, owner, fileId, friend);
    const res = await request.post(`${API_BASE}/api/v1/files/${fileId}/trash`, { headers: auth(friend) });
    await request.post(`${API_BASE}/api/v1/files/${fileId}/restore`, { headers: auth(owner) });
    expect(res.status()).toBe(403);
  });
});
