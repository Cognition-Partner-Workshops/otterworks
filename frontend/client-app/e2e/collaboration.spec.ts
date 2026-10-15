import { test, expect, type Browser, type BrowserContext, type Page, type WebSocketRoute } from "@playwright/test";
import { uniqueEmail, loginUser, expectDashboard } from "./fixtures/test-helpers";

const API_URL = process.env.API_URL || "http://localhost:8080";
const PASSWORD = "Passw0rd!23";

interface Owner {
  email: string;
  displayName: string;
  documentId: string;
}

async function createOwnerWithDocument(browser: Browser, title: string): Promise<Owner> {
  const ctx = await browser.newContext();
  const displayName = `Collab QA ${Math.random().toString(36).slice(2, 6)}`;
  const email = uniqueEmail();
  const reg = await ctx.request.post(`${API_URL}/api/v1/auth/register`, {
    data: { displayName, email, password: PASSWORD },
  });
  expect(reg.status(), await reg.text()).toBe(201);
  const { accessToken } = await reg.json();
  const doc = await ctx.request.post(`${API_URL}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { title, content: "" },
  });
  expect(doc.status(), await doc.text()).toBe(201);
  const { id } = await doc.json();
  await ctx.close();
  return { email, displayName, documentId: id };
}

async function openEditor(context: BrowserContext, owner: Owner): Promise<Page> {
  const page = await context.newPage();
  await loginUser(page, owner.email, PASSWORD);
  await expectDashboard(page);
  await page.goto(`/documents/${owner.documentId}`);
  await expect(page.getByText("All changes saved")).toBeVisible({ timeout: 15_000 });
  return page;
}

function editor(page: Page) {
  return page.locator(".ProseMirror");
}

async function docText(page: Page): Promise<string> {
  return editor(page).evaluate((el) => {
    const clone = el.cloneNode(true) as HTMLElement;
    clone.querySelectorAll(".collaboration-cursor__caret").forEach((c) => c.remove());
    return clone.textContent ?? "";
  });
}

async function typeAtStart(page: Page, text: string) {
  await editor(page).click();
  await page.keyboard.press("ControlOrMeta+Home");
  await page.keyboard.type(text, { delay: 20 });
}

async function typeAtEnd(page: Page, text: string) {
  await editor(page).click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.type(text, { delay: 20 });
}

test.describe("Real-time collaboration (two sessions, one document)", () => {
  test.skip(!!process.env.CI, "requires the local stack (gateway + collab-service)");

  let owner: Owner;
  let left: BrowserContext;
  let right: BrowserContext;

  test.beforeEach(async ({ browser }, testInfo) => {
    owner = await createOwnerWithDocument(browser, `Collab ${testInfo.title}`);
    left = await browser.newContext();
    right = await browser.newContext();
  });

  test.afterEach(async () => {
    await left?.close();
    await right?.close();
  });

  test("edits from either side appear on the other", async () => {
    const a = await openEditor(left, owner);
    const b = await openEditor(right, owner);

    await typeAtEnd(a, "Hello from the left window");
    await expect(editor(b)).toContainText("Hello from the left window");

    await typeAtEnd(b, " and the right one");
    await expect(editor(a)).toContainText("Hello from the left window and the right one");
  });

  test("simultaneous typing in different places keeps both edits intact", async () => {
    const a = await openEditor(left, owner);
    const b = await openEditor(right, owner);
    await typeAtEnd(a, "base");
    await expect(editor(b)).toContainText("base");

    await Promise.all([typeAtStart(a, "LEFT "), typeAtEnd(b, " RIGHT")]);

    await expect.poll(() => docText(a)).toBe("LEFT base RIGHT");
    await expect.poll(() => docText(b)).toBe("LEFT base RIGHT");
  });

  test("simultaneous typing at the same spot converges with no lost keystrokes", async () => {
    const a = await openEditor(left, owner);
    const b = await openEditor(right, owner);
    await typeAtEnd(a, "base ");
    await expect(editor(b)).toContainText("base");

    await Promise.all([typeAtEnd(a, "LEFT"), typeAtEnd(b, "RIGHT")]);

    await expect.poll(async () => (await docText(a)) === (await docText(b))).toBe(true);
    const merged = (await docText(a)).replace(/^base\s*/, "");
    expect([...merged].sort().join("")).toBe([..."LEFTRIGHT"].sort().join(""));
  });

  test("remote caret is labelled with the collaborator's name", async () => {
    const a = await openEditor(left, owner);
    const b = await openEditor(right, owner);
    await typeAtEnd(a, "cursor here");

    const label = b.locator(".collaboration-cursor__label");
    await expect(label).toHaveText(owner.displayName);
  });

  test("dropped websocket shows status, reconnects and syncs offline edits", async () => {
    let blocked = false;
    const sockets: WebSocketRoute[] = [];
    await left.routeWebSocket(/:8084\/document-/, (ws) => {
      if (blocked) {
        ws.close();
        return;
      }
      ws.connectToServer();
      sockets.push(ws);
    });

    const a = await openEditor(left, owner);
    const b = await openEditor(right, owner);

    blocked = true;
    await Promise.all(sockets.map((ws) => ws.close()));
    await expect(a.getByText(/Offline|Reconnecting…/)).toBeVisible();

    await typeAtEnd(a, "typed while offline");
    await expect(editor(b)).not.toContainText("typed while offline");

    blocked = false;
    await expect(a.getByText("All changes saved")).toBeVisible({ timeout: 20_000 });
    await expect(editor(b)).toContainText("typed while offline");
  });

  test("content persists after every session closes", async () => {
    const a = await openEditor(left, owner);
    await typeAtEnd(a, "still here tomorrow");
    await expect(a.getByText("All changes saved")).toBeVisible();
    await a.waitForTimeout(1500);
    await left.close();

    const fresh = await openEditor(right, owner);
    await expect(editor(fresh)).toContainText("still here tomorrow");
  });
});
