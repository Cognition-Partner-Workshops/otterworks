import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { uniqueEmail } from "./fixtures/test-helpers";

/**
 * QA pyramid (docs area): signed-in document journeys against the real stack.
 * Known defects use test.fail() with a [REAL] label so the suite stays green.
 */

const API = process.env.API_URL || "http://localhost:8080";

interface Session {
  accessToken: string;
  refreshToken: string;
}

async function register(request: APIRequestContext): Promise<Session> {
  const res = await request.post(`${API}/api/v1/auth/register`, {
    data: { email: uniqueEmail(), password: "OtterworksTest123!", displayName: "Docs QA" },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return { accessToken: body.accessToken, refreshToken: body.refreshToken };
}

async function signIn(page: Page, session: Session) {
  await page.addInitScript((s) => {
    localStorage.setItem("otter_access_token", s.accessToken);
    localStorage.setItem("otter_refresh_token", s.refreshToken);
  }, session);
}

async function createDoc(request: APIRequestContext, session: Session, title: string, content = "") {
  const res = await request.post(`${API}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: { title, content },
  });
  expect(res.status()).toBe(201);
  return res.json();
}

async function getDoc(request: APIRequestContext, session: Session, id: string) {
  return request.get(`${API}/api/v1/documents/${id}`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
}

test.describe("Docs QA (signed in)", () => {
  let session: Session;

  test.beforeEach(async ({ page, request }) => {
    session = await register(request);
    await signIn(page, session);
  });

  test("lists the user's documents and filters by name", async ({ page, request }) => {
    await createDoc(request, session, "Quarterly roadmap");
    await createDoc(request, session, "Grocery list");
    await page.goto("/documents");
    await expect(page.getByText("Quarterly roadmap")).toBeVisible();
    await expect(page.getByText("Grocery list")).toBeVisible();
    await page.getByPlaceholder("Filter documents...").fill("roadmap");
    await expect(page.getByText("Quarterly roadmap")).toBeVisible();
    await expect(page.getByText("Grocery list")).toBeHidden();
  });

  test("creates, renames, edits, saves and deletes a document", async ({ page, request }) => {
    await page.goto("/documents");
    await page.getByRole("button", { name: "New document" }).click();
    await page.waitForURL((url) => url.pathname.startsWith("/documents/") && url.pathname.length > 12);
    const id = page.url().split("/documents/")[1];

    await page.getByTitle("Click to rename").click();
    const titleInput = page.locator("h1 + input, input.border-otter-500").first();
    await titleInput.fill("QA journey doc");
    await titleInput.press("Enter");
    await expect(page.getByTitle("Click to rename")).toHaveText("QA journey doc");

    const editor = page.locator(".ProseMirror");
    await editor.click();
    await page.keyboard.type("Hello from the docs QA pyramid");
    await page.getByRole("button", { name: "Save" }).click();

    await expect
      .poll(async () => (await (await getDoc(request, session, id)).json()).content, { timeout: 10_000 })
      .toContain("Hello from the docs QA pyramid");
    const saved = await (await getDoc(request, session, id)).json();
    expect(saved.title).toBe("QA journey doc");

    await page.reload();
    await expect(page.locator(".ProseMirror")).toContainText("Hello from the docs QA pyramid");

    await page.locator("button.text-red-600").click();
    await page.waitForURL((url) => url.pathname === "/documents");
    await expect(page.getByText("QA journey doc")).toBeHidden();
    expect((await getDoc(request, session, id)).status()).toBe(404);
  });

  test("opening a missing document shows not-found", async ({ page }) => {
    await page.goto("/documents/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("Document not found")).toBeVisible();
  });

  test("[REAL] document list shows all of a user's documents (client pageSize ignored)", async ({
    page,
    request,
  }) => {
    test.fail(true, "[REAL] client sends pageSize=50 but document-service reads size (default 20)");
    for (let i = 0; i < 22; i++) {
      await createDoc(request, session, `Bulk doc ${String(i).padStart(2, "0")}`);
    }
    await page.goto("/documents");
    await expect(page.getByText("Bulk doc 00")).toBeVisible();
    await expect(page.getByText("Bulk doc", { exact: false })).toHaveCount(22, { timeout: 5_000 });
  });
});

test("documents page requires sign-in", async ({ page }) => {
  await page.goto("/documents");
  await expect(page).toHaveURL(/\/login/);
});
