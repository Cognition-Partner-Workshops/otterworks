import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { loginUser, expectDashboard, uniqueEmail } from "../fixtures/test-helpers";

/**
 * QA: critical sharing paths against the running stack.
 * Users and files are seeded through the same-origin /api/v1 proxy; the
 * sharing actions themselves are driven through the UI.
 */

const PASSWORD = "Passw0rd!23";

interface SeededUser {
  id: string;
  email: string;
  name: string;
  token: string;
}

async function registerViaApi(request: APIRequestContext, name: string): Promise<SeededUser> {
  const email = uniqueEmail();
  const response = await request.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD, displayName: name },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  return { id: body.user.id, email, name, token: body.accessToken };
}

async function uploadViaApi(request: APIRequestContext, owner: SeededUser, fileName: string) {
  const response = await request.post("/api/v1/files/upload", {
    headers: { Authorization: `Bearer ${owner.token}` },
    multipart: { file: { name: fileName, mimeType: "text/plain", buffer: Buffer.from("qa sharing e2e") } },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()).file.id as string;
}

async function sharedIdsViaApi(request: APIRequestContext, user: SeededUser) {
  const response = await request.get("/api/v1/files/shared", {
    headers: { Authorization: `Bearer ${user.token}` },
  });
  expect(response.status()).toBe(200);
  const body = await response.json();
  return (body.files as { id: string }[]).map((f) => f.id);
}

async function signIn(page: Page, user: SeededUser) {
  await page.context().clearCookies();
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await loginUser(page, user.email, PASSWORD);
  await expectDashboard(page);
}

test.describe("QA sharing", () => {
  test("owner shares a file as Viewer and the collaborator sees it under Shared with me", async ({ page, request }) => {
    const owner = await registerViaApi(request, "QA Owner");
    const collaborator = await registerViaApi(request, "QA Collaborator");
    const fileName = `qa-e2e-share-${Date.now()}.txt`;
    const fileId = await uploadViaApi(request, owner, fileName);

    await signIn(page, owner);
    await page.goto(`/files/${fileId}`);
    await page.getByRole("button", { name: "Share", exact: true }).first().click();
    await expect(page.getByRole("heading", { name: `Share “${fileName}”` })).toBeVisible();
    await page.getByPlaceholder("Add people by email").fill(collaborator.email);
    await page.getByRole("button", { name: "Share", exact: true }).last().click();
    await expect(page.getByText(collaborator.email, { exact: true })).toBeVisible();

    await expect.poll(() => sharedIdsViaApi(request, collaborator)).toContain(fileId);

    await signIn(page, collaborator);
    await page.goto("/shared");
    await expect(page.getByRole("heading", { name: "Shared with me" })).toBeVisible();
    await expect(page.getByText(fileName)).toBeVisible();
  });

  test("owner upgrades to Editor then revokes access from the share dialog", async ({ page, request }) => {
    const owner = await registerViaApi(request, "QA Owner");
    const collaborator = await registerViaApi(request, "QA Collaborator");
    const fileName = `qa-e2e-revoke-${Date.now()}.txt`;
    const fileId = await uploadViaApi(request, owner, fileName);
    const share = await request.post(`/api/v1/files/${fileId}/share`, {
      headers: { Authorization: `Bearer ${owner.token}` },
      data: { shared_with: collaborator.id, permission: "viewer", shared_by: owner.id },
    });
    expect(share.status()).toBe(201);

    await signIn(page, owner);
    await page.goto(`/files/${fileId}`);
    await page.getByRole("button", { name: "Share", exact: true }).first().click();
    const row = page.locator("div.group").filter({ hasText: collaborator.email });
    await expect(row).toBeVisible();
    await row.locator("select").selectOption("edit");
    await expect
      .poll(async () => {
        const detail = await request.get(`/api/v1/files/${fileId}`, {
          headers: { Authorization: `Bearer ${owner.token}` },
        });
        const body = await detail.json();
        return body.shared_with.find((s: { shared_with: string }) => s.shared_with === collaborator.id)?.permission;
      })
      .toBe("editor");

    await row.getByTitle("Remove access").click();
    await expect(page.getByText(collaborator.email, { exact: true })).toHaveCount(0);
    await expect.poll(() => sharedIdsViaApi(request, collaborator)).not.toContain(fileId);

    await signIn(page, collaborator);
    await page.goto("/shared");
    await expect(page.getByRole("heading", { name: "Shared with me" })).toBeVisible();
    await expect(page.getByText(fileName)).toHaveCount(0);
  });

  test("non-shared user is denied a private file", async ({ page, request }) => {
    const owner = await registerViaApi(request, "QA Owner");
    const outsider = await registerViaApi(request, "QA Outsider");
    const fileName = `qa-e2e-private-${Date.now()}.txt`;
    const fileId = await uploadViaApi(request, owner, fileName);

    await signIn(page, outsider);
    await page.goto("/shared");
    await expect(page.getByRole("heading", { name: "Shared with me" })).toBeVisible();
    await expect(page.getByText(fileName)).toHaveCount(0);

    await page.goto(`/files/${fileId}`);
    await expect(page.getByText("File not found")).toBeVisible();
    await expect(page.getByText(fileName)).toHaveCount(0);
  });
});
