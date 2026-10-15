import {
  test,
  expect,
  type Browser,
  type APIRequestContext,
  type BrowserContext,
  type Page,
  type WebSocketRoute,
} from "@playwright/test";
import { randomBytes } from "node:crypto";

/**
 * Collaboration QA: real-time co-editing over y-websocket between two isolated
 * browser contexts (separate storage, so BroadcastChannel cannot mask server sync).
 * Requires the web app built with VITE_COLLAB_WS_URL pointing at collab-service.
 */

const API_URL = process.env.API_URL || "http://localhost:8080";

interface Account {
  email: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
}

function runId(): string {
  return randomBytes(4).toString("hex");
}

async function registerAccount(
  request: APIRequestContext,
  prefix: string,
): Promise<Account> {
  const id = runId();
  const email = `collab-e2e-${prefix}-${id}@otterworks.test`;
  const displayName = `${prefix} ${id}`;
  const res = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: {
      email,
      password: `Pw-${randomBytes(6).toString("hex")}!9`,
      displayName,
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return {
    email,
    displayName,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

async function createDocument(
  request: APIRequestContext,
  account: Account,
  title: string,
): Promise<string> {
  const res = await request.post(`${API_URL}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${account.accessToken}` },
    data: { title, content: "" },
  });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()).id;
}

async function openEditor(
  browser: Browser,
  account: Account,
  documentId: string,
): Promise<Page> {
  const context = await browser.newContext();
  await context.addInitScript(
    ([access, refresh]) => {
      localStorage.setItem("otter_access_token", access);
      localStorage.setItem("otter_refresh_token", refresh);
    },
    [account.accessToken, account.refreshToken],
  );
  const page = await context.newPage();
  await page.goto(`/documents/${documentId}`);
  return page;
}

/**
 * Proxies the collab WebSocket through Playwright so a test can sever it and keep
 * it down (context.setOffline does not drop already-open WebSockets in Chromium).
 */
async function controlCollabSocket(context: BrowserContext) {
  let offline = false;
  const open: WebSocketRoute[] = [];
  await context.routeWebSocket(
    (url) => url.pathname.startsWith("/document-"),
    (ws) => {
      if (offline) {
        void ws.close();
        return;
      }
      ws.connectToServer();
      open.push(ws);
    },
  );
  return {
    async drop() {
      offline = true;
      await Promise.all(open.splice(0).map((ws) => ws.close()));
    },
    restore() {
      offline = false;
    },
  };
}

function editor(page: Page) {
  return page.locator(".ProseMirror");
}

async function expectConnected(page: Page) {
  await expect(editor(page)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("All changes saved")).toBeVisible({
    timeout: 15_000,
  });
}

async function typeAtEnd(page: Page, text: string) {
  await editor(page).click();
  await page.keyboard.press("ControlOrMeta+End");
  await page.keyboard.type(text);
}

test.describe("Collaboration (two browser contexts)", () => {
  test.describe.configure({ mode: "serial" });

  test("edits sync both ways in real time between two isolated contexts", async ({
    browser,
    request,
  }) => {
    const owner = await registerAccount(request, "coedit");
    const docId = await createDocument(request, owner, `Co-edit ${runId()}`);
    const a = await openEditor(browser, owner, docId);
    const b = await openEditor(browser, owner, docId);
    await expectConnected(a);
    await expectConnected(b);

    const fromA = `from-A-${runId()}`;
    await typeAtEnd(a, fromA);
    await expect(editor(b)).toContainText(fromA);

    const fromB = ` from-B-${runId()}`;
    await typeAtEnd(b, fromB);
    await expect(editor(a)).toContainText(fromB);
    await expect(editor(a)).toContainText(fromA);

    await a.context().close();
    await b.context().close();
  });

  test("shows the remote user's caret label via awareness", async ({
    browser,
    request,
  }) => {
    const owner = await registerAccount(request, "cursor");
    const docId = await createDocument(request, owner, `Cursor ${runId()}`);
    const a = await openEditor(browser, owner, docId);
    const b = await openEditor(browser, owner, docId);
    await expectConnected(a);
    await expectConnected(b);

    await typeAtEnd(a, `caret-${runId()}`);
    await expect(
      b
        .locator(".collaboration-cursor__label")
        .filter({ hasText: owner.displayName }),
    ).toBeVisible();

    await a.context().close();
    await b.context().close();
  });

  test("late joiner receives existing content and survives a reload", async ({
    browser,
    request,
  }) => {
    const owner = await registerAccount(request, "history");
    const docId = await createDocument(request, owner, `History ${runId()}`);
    const a = await openEditor(browser, owner, docId);
    await expectConnected(a);
    const marker = `persisted-${runId()}`;
    await typeAtEnd(a, marker);

    const late = await openEditor(browser, owner, docId);
    await expectConnected(late);
    await expect(editor(late)).toContainText(marker);

    await late.reload();
    await expectConnected(late);
    await expect(editor(late)).toContainText(marker);

    await a.context().close();
    await late.context().close();
  });

  test("goes offline, then reconnects and catches up on edits made meanwhile", async ({
    browser,
    request,
  }) => {
    const owner = await registerAccount(request, "reconnect");
    const docId = await createDocument(request, owner, `Reconnect ${runId()}`);
    const a = await openEditor(browser, owner, docId);
    const bContext = await browser.newContext();
    const link = await controlCollabSocket(bContext);
    await bContext.addInitScript(
      ([access, refresh]) => {
        localStorage.setItem("otter_access_token", access);
        localStorage.setItem("otter_refresh_token", refresh);
      },
      [owner.accessToken, owner.refreshToken],
    );
    const b = await bContext.newPage();
    await b.goto(`/documents/${docId}`);
    await expectConnected(a);
    await expectConnected(b);

    await link.drop();
    await expect(b.getByText(/Offline|Reconnecting/)).toBeVisible({
      timeout: 15_000,
    });

    const whileOffline = `while-offline-${runId()}`;
    await typeAtEnd(a, whileOffline);
    await expect(editor(b)).not.toContainText(whileOffline);

    link.restore();
    await expectConnected(b);
    await expect(editor(b)).toContainText(whileOffline, { timeout: 15_000 });

    await a.context().close();
    await b.context().close();
  });

  test("[REAL] header online count reflects live co-editors", async ({
    browser,
    request,
  }) => {
    test.fail(
      true,
      "[REAL] document header '<n> online' is driven by document.collaborators, not collab-service presence; it shows 0 online while two editors are connected",
    );
    const owner = await registerAccount(request, "online");
    const docId = await createDocument(request, owner, `Online ${runId()}`);
    const a = await openEditor(browser, owner, docId);
    const b = await openEditor(browser, owner, docId);
    await expectConnected(a);
    await expectConnected(b);
    await expect(a.getByText("0 online")).toHaveCount(0, { timeout: 5_000 });

    await a.context().close();
    await b.context().close();
  });

  test("[REAL] a user the document was shared with can open it to co-edit", async ({
    browser,
    request,
  }) => {
    test.fail(
      true,
      "[REAL] sharing with an email for 'edit' does not grant that user access: GET /documents/:id is owner-only, so the invitee sees 'Document not found'",
    );
    const owner = await registerAccount(request, "sharer");
    const invitee = await registerAccount(request, "invitee");
    const docId = await createDocument(request, owner, `Shared ${runId()}`);

    const a = await openEditor(browser, owner, docId);
    await expectConnected(a);
    await a.getByRole("button", { name: "Share" }).click();
    await a.getByPlaceholder("Enter email address").fill(invitee.email);
    await a.getByRole("button", { name: "Invite" }).click();
    await expect(a.getByText("Invite sent successfully")).toBeVisible();

    const b = await openEditor(browser, invitee, docId);
    await expectConnected(b);

    await a.context().close();
    await b.context().close();
  });
});
