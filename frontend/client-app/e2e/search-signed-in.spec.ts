import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { uniqueEmail } from "./fixtures/test-helpers";

const API_URL = process.env.API_URL || "http://localhost:8080";

interface Session {
  accessToken: string;
  refreshToken: string;
}

async function registerViaApi(request: APIRequestContext): Promise<Session> {
  const password = `Pw-${randomBytes(8).toString("hex")}!9A`;
  const res = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { email: uniqueEmail(), password, displayName: "Search QA" },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return { accessToken: body.accessToken, refreshToken: body.refreshToken };
}

async function signIn(page: Page, session: Session) {
  await page.addInitScript(([access, refresh]) => {
    localStorage.setItem("otter_access_token", access);
    localStorage.setItem("otter_refresh_token", refresh);
  }, [session.accessToken, session.refreshToken]);
}

function authHeaders(session: Session) {
  return { Authorization: `Bearer ${session.accessToken}` };
}

async function createDocument(request: APIRequestContext, session: Session, title: string, content: string) {
  const res = await request.post(`${API_URL}/api/v1/documents/`, {
    headers: authHeaders(session),
    data: { title, content },
  });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()) as { id: string };
}

async function waitForIndexed(request: APIRequestContext, session: Session, q: string, min = 1) {
  await expect
    .poll(
      async () => {
        const res = await request.get(`${API_URL}/api/v1/search/`, {
          headers: authHeaders(session),
          params: { q },
        });
        return res.ok() ? (await res.json()).total : -1;
      },
      { timeout: 20_000 },
    )
    .toBeGreaterThanOrEqual(min);
}

function tag() {
  return randomBytes(4).toString("hex");
}

test.describe("Search (signed in)", () => {
  let session: Session;

  test.beforeEach(async ({ page, request }) => {
    session = await registerViaApi(request);
    await signIn(page, session);
  });

  test("search page renders for a signed-in user", async ({ page }) => {
    await page.goto("/search");
    await expect(page).toHaveURL(/\/search/);
    await expect(page.getByRole("heading", { name: "Search", exact: true })).toBeVisible();
    await expect(page.getByPlaceholder("Search files, documents, and folders...")).toBeVisible();
  });

  test("finds a newly created document and links to it", async ({ page, request }) => {
    const t = tag();
    const doc = await createDocument(request, session, `Kelp Forecast ${t}`, `tide tables ${t}`);
    await waitForIndexed(request, session, t);

    await page.goto("/search");
    const input = page.getByPlaceholder("Search files, documents, and folders...");
    await input.fill(t);
    await input.press("Enter");

    const result = page.getByRole("link", { name: /Kelp Forecast/ });
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute("href", `/documents/${doc.id}`);
  });

  test("header search bar navigates to results", async ({ page, request }) => {
    const t = tag();
    await createDocument(request, session, `Header Hit ${t}`, `body ${t}`);
    await waitForIndexed(request, session, t);

    await page.goto("/dashboard");
    const bar = page.getByPlaceholder("Search files, documents...");
    await bar.fill(t);
    await bar.press("Enter");
    await expect(page).toHaveURL(/\/search\?q=/);
    await expect(page.getByRole("link", { name: /Header Hit/ })).toBeVisible();
  });

  test("updated document is re-indexed under its new title", async ({ page, request }) => {
    const t = tag();
    const doc = await createDocument(request, session, `Old Name ${t}`, `body ${t}`);
    await waitForIndexed(request, session, t);
    const res = await request.put(`${API_URL}/api/v1/documents/${doc.id}`, {
      headers: authHeaders(session),
      data: { title: `Fresh Name ${t}`, content: `body ${t}` },
    });
    expect(res.ok()).toBeTruthy();
    await waitForIndexed(request, session, `Fresh Name ${t}`);

    await page.goto(`/search?q=${t}`);
    await expect(page.getByRole("link", { name: /Fresh Name/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Old Name/ })).toHaveCount(0);
  });

  test("deleted document disappears from results", async ({ page, request }) => {
    const t = tag();
    const doc = await createDocument(request, session, `Doomed Doc ${t}`, `body ${t}`);
    await waitForIndexed(request, session, t);
    const res = await request.delete(`${API_URL}/api/v1/documents/${doc.id}`, {
      headers: authHeaders(session),
    });
    expect(res.ok()).toBeTruthy();
    await expect
      .poll(
        async () =>
          (await (await request.get(`${API_URL}/api/v1/search/`, { headers: authHeaders(session), params: { q: t } })).json())
            .total,
        { timeout: 20_000 },
      )
      .toBe(0);

    await page.goto(`/search?q=${t}`);
    await expect(page.getByText("No results found")).toBeVisible();
  });

  test("type filters narrow results", async ({ page, request }) => {
    const t = tag();
    await createDocument(request, session, `Filter Doc ${t}`, `body ${t}`);
    await waitForIndexed(request, session, t);

    await page.goto(`/search?q=${t}`);
    await expect(page.getByRole("link", { name: /Filter Doc/ })).toBeVisible();

    await page.locator("form button[type=button]").first().click();
    await page.getByRole("button", { name: "Files" }).click();
    await expect(page.getByText("No results found")).toBeVisible();
    await page.getByRole("button", { name: "Documents" }).click();
    await expect(page.getByRole("link", { name: /Filter Doc/ })).toBeVisible();
  });

  test("shows no-results state for unknown terms", async ({ page }) => {
    await page.goto(`/search?q=zz${tag()}nomatch`);
    await expect(page.getByText("No results found")).toBeVisible();
  });

  test("does not show another user's documents", async ({ page, request }) => {
    const t = tag();
    const other = await registerViaApi(request);
    await createDocument(request, other, `Private ${t}`, `secret ${t}`);
    await waitForIndexed(request, other, t);

    await page.goto(`/search?q=${t}`);
    await expect(page.getByText("No results found")).toBeVisible();
  });

  test("newly created folder appears under the Folders filter", async ({ page, request }) => {
    test.fail(true, "[REAL] folders are never indexed by search-service; Folders filter is always empty");
    test.setTimeout(20_000);
    const t = tag();
    const res = await request.post(`${API_URL}/api/v1/folders`, {
      headers: authHeaders(session),
      data: { name: `Folder${t}` },
    });
    expect(res.ok(), await res.text()).toBeTruthy();

    await page.goto(`/search?q=Folder${t}`);
    await expect(page.getByRole("link", { name: `Folder${t}` })).toBeVisible({ timeout: 8_000 });
  });
});
