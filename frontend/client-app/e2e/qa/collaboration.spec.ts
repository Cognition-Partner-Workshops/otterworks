import { test, expect, type APIRequestContext, type Browser, type BrowserContext, type Page, type WebSocketRoute } from "@playwright/test";
import { loginUser } from "../fixtures/test-helpers";

/**
 * QA: real-time collaboration critical paths against the local stack
 * (web app :3000, gateway :8080, collab-service Yjs websocket :8084).
 */

const API_BASE = process.env.OTTERWORKS_API_BASE_URL || "http://localhost:8080";
const PASSWORD = "OtterworksTest123!";

interface QaUser {
  email: string;
  name: string;
  token: string;
}

async function registerViaApi(prefix: string, request: APIRequestContext): Promise<QaUser> {
  const email = `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@otterworks.test`;
  const name = `${prefix} ${Math.random().toString(36).slice(2, 5)}`;
  const res = await request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, displayName: name },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return { email, name, token: body.accessToken };
}

async function createDocument(request: APIRequestContext, user: QaUser, title: string): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${user.token}` },
    data: { title, content: "" },
  });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()).id;
}

async function openWindow(browser: Browser, user: QaUser, documentId: string) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const sockets: WebSocketRoute[] = [];
  await page.routeWebSocket(/:8084\//, (ws) => {
    sockets.push(ws);
    ws.connectToServer();
  });
  await loginUser(page, user.email, PASSWORD);
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
  await page.goto(`/documents/${documentId}`);
  const editor = page.locator(".ProseMirror");
  await expect(editor).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("All changes saved")).toBeVisible({ timeout: 15_000 });
  return { context, page, editor, sockets };
}

async function typeAt(page: Page, where: "Home" | "End", text: string) {
  const editor = page.locator(".ProseMirror");
  await editor.click();
  await page.keyboard.press(`Control+${where}`);
  await page.keyboard.type(text);
}

const typeAtEnd = (page: Page, text: string) => typeAt(page, "End", text);

/** Document text without remote-cursor caret/label decorations. */
async function docText(page: Page): Promise<string> {
  return page.locator(".ProseMirror").evaluate((el) => {
    const clone = el.cloneNode(true) as HTMLElement;
    clone.querySelectorAll(".collaboration-cursor__caret").forEach((n) => n.remove());
    return clone.textContent ?? "";
  });
}

test.describe("QA collaboration (two windows, Yjs over collab-service)", () => {
  test.describe.configure({ timeout: 90_000 });

  let user: QaUser;
  let documentId: string;
  const contexts: BrowserContext[] = [];

  test.beforeEach(async ({ request }) => {
    user = await registerViaApi("qa-collab-e2e", request);
    documentId = await createDocument(request, user, `QA collab ${Date.now()}`);
  });

  test.afterEach(async () => {
    while (contexts.length) await contexts.pop()!.close();
  });

  test("edits in one window appear live in the other and concurrent edits converge", async ({ browser }) => {
    const a = await openWindow(browser, user, documentId);
    const b = await openWindow(browser, user, documentId);
    contexts.push(a.context, b.context);

    await typeAtEnd(a.page, "Hello from window A.");
    await expect(b.editor).toContainText("Hello from window A.", { timeout: 10_000 });

    // Concurrent edits at different positions must both survive and converge.
    await Promise.all([typeAt(a.page, "Home", "alpha-edit "), typeAt(b.page, "End", " bravo-edit")]);
    for (const w of [a, b]) {
      await expect.poll(() => docText(w.page), { timeout: 10_000 }).toContain("alpha-edit");
      await expect.poll(() => docText(w.page), { timeout: 10_000 }).toContain("bravo-edit");
    }
    await expect.poll(async () => (await docText(a.page)) === (await docText(b.page)), { timeout: 10_000 }).toBe(true);
  });

  test("remote collaboration cursor shows the other user's name", async ({ browser }) => {
    const a = await openWindow(browser, user, documentId);
    const b = await openWindow(browser, user, documentId);
    contexts.push(a.context, b.context);

    await typeAtEnd(a.page, "cursor test");
    await expect(b.editor).toContainText("cursor test");
    const remoteCaret = b.page.locator(".collaboration-cursor__caret");
    await expect(remoteCaret.first()).toBeAttached({ timeout: 10_000 });
    await expect(b.page.locator(".collaboration-cursor__label").first()).toHaveText(user.name);
  });

  test("reconnects after the websocket drops and catches up on missed edits", async ({ browser }) => {
    const a = await openWindow(browser, user, documentId);
    const b = await openWindow(browser, user, documentId);
    contexts.push(a.context, b.context);

    await typeAtEnd(a.page, "before-drop");
    await expect(b.editor).toContainText("before-drop");

    const before = b.sockets.length;
    for (const ws of b.sockets) await ws.close({ code: 1006 }).catch(() => {});
    await expect(b.page.getByText(/Offline|Reconnecting…/)).toBeVisible({ timeout: 5_000 });
    await typeAtEnd(a.page, " during-drop");

    await expect.poll(() => b.sockets.length, { timeout: 15_000 }).toBeGreaterThan(before);
    await expect(b.page.getByText("All changes saved")).toBeVisible({ timeout: 15_000 });
    await expect(b.editor).toContainText("during-drop", { timeout: 10_000 });

    await typeAtEnd(b.page, " after-reconnect");
    await expect(a.editor).toContainText("after-reconnect", { timeout: 10_000 });
  });

  test("document header shows the other window as an online collaborator", async ({ browser }) => {
    const a = await openWindow(browser, user, documentId);
    const b = await openWindow(browser, user, documentId);
    contexts.push(a.context, b.context);
    await typeAtEnd(b.page, "presence");
    await expect(a.editor).toContainText("presence");
    await expect(a.page.getByText(/^[1-9]\d* online$/).first()).toBeVisible({ timeout: 10_000 });
  });

  test("a different account cannot open someone else's private document", async ({ browser, request }) => {
    const outsider = await registerViaApi("qa-collab-outsider", request);
    const context = await browser.newContext();
    contexts.push(context);
    const page = await context.newPage();
    await loginUser(page, outsider.email, PASSWORD);
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
    await page.goto(`/documents/${documentId}`);
    await expect(page.getByText("Document not found")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".ProseMirror")).toHaveCount(0);
  });
});
