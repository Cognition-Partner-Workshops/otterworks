import {
  test,
  expect,
  type Browser,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { randomBytes } from "node:crypto";

/**
 * Document header presence ("N online" + avatars) is driven by live y-websocket
 * awareness. Uses isolated browser contexts so BroadcastChannel cannot fake it.
 * Requires the web app built with VITE_COLLAB_WS_URL pointing at collab-service.
 */

const API_URL = process.env.API_URL || "http://localhost:8080";

interface Account {
  displayName: string;
  accessToken: string;
  refreshToken: string;
}

async function registerAccount(request: APIRequestContext): Promise<Account> {
  const id = randomBytes(4).toString("hex");
  const displayName = `Presence ${id}`;
  const res = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: {
      email: `presence-e2e-${id}@otterworks.test`,
      password: `Pw-${randomBytes(6).toString("hex")}!9`,
      displayName,
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return {
    displayName,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

async function createDocument(
  request: APIRequestContext,
  account: Account,
): Promise<string> {
  const res = await request.post(`${API_URL}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${account.accessToken}` },
    data: { title: `Presence ${randomBytes(4).toString("hex")}`, content: "" },
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
  await expect(page.locator(".ProseMirror")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("All changes saved")).toBeVisible({
    timeout: 15_000,
  });
  return page;
}

test.describe("Live document presence", () => {
  test("header shows the connected user as online with an avatar", async ({
    browser,
    request,
  }) => {
    const owner = await registerAccount(request);
    const docId = await createDocument(request, owner);
    const page = await openEditor(browser, owner, docId);

    await expect(page.getByText("1 online").first()).toBeVisible();
    await expect(page.getByText("0 online")).toHaveCount(0);
    await expect(
      page.getByTitle(`${owner.displayName} (online)`),
    ).toBeVisible();

    await page.context().close();
  });

  test("the same user in two browser contexts counts once", async ({
    browser,
    request,
  }) => {
    const owner = await registerAccount(request);
    const docId = await createDocument(request, owner);
    const a = await openEditor(browser, owner, docId);
    const b = await openEditor(browser, owner, docId);

    await expect(a.getByText("1 online").first()).toBeVisible();
    await expect(b.getByText("1 online").first()).toBeVisible();

    await b.context().close();
    await expect(a.getByText("1 online").first()).toBeVisible();
    await a.context().close();
  });
});
