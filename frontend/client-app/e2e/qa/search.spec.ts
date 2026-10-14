import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { loginUser } from "../fixtures/test-helpers";

const API = process.env.OTTERWORKS_API_BASE_URL ?? "http://localhost:8080";
const SEARCH_PLACEHOLDER = "Search files, documents, and folders...";

type Session = { email: string; password: string; token: string; userId: string };

function word(prefix: string): string {
  const letters = "abcdefghijklmnopqrstuvwxyz";
  let s = prefix;
  for (let i = 0; i < 10; i++) s += letters[Math.floor(Math.random() * letters.length)];
  return s;
}

async function registerViaApi(request: APIRequestContext): Promise<Session> {
  const email = `qa-search-e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.test`;
  const password = "OtterworksTest123!";
  const res = await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password, displayName: "QA Search E2E" },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return { email, password, token: body.accessToken, userId: body.user.id };
}

async function createDocument(request: APIRequestContext, s: Session, title: string, content: string) {
  const res = await request.post(`${API}/api/v1/documents/`, {
    headers: { Authorization: `Bearer ${s.token}` },
    data: { title, content },
  });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()) as { id: string };
}

async function indexFile(request: APIRequestContext, s: Session, name: string) {
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  const res = await request.post(`${API}/api/v1/search/index/file`, {
    headers: { Authorization: `Bearer ${s.token}` },
    data: { id, name, mime_type: "text/plain", owner_id: s.userId, size: 42, created_at: now, updated_at: now },
  });
  expect(res.status(), await res.text()).toBe(201);
  return id;
}

async function waitIndexed(request: APIRequestContext, s: Session, q: string, id: string) {
  await expect
    .poll(
      async () => {
        const res = await request.get(`${API}/api/v1/search/`, {
          headers: { Authorization: `Bearer ${s.token}` },
          params: { q },
        });
        if (!res.ok()) return [];
        return ((await res.json()).results ?? []).map((r: { id: string }) => r.id);
      },
      { timeout: 20_000 }
    )
    .toContain(id);
}

async function login(page: Page, s: Session) {
  await loginUser(page, s.email, s.password);
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
}

test.describe("QA: search critical paths", () => {
  let session: Session;

  test.beforeEach(async ({ page, request }) => {
    session = await registerViaApi(request);
    await login(page, session);
  });

  test("new document is indexed, found from the header search bar and opens on click", async ({ page, request }) => {
    const term = word("e2edoc");
    const doc = await createDocument(request, session, `Otter ${term} plan`, `content ${term}`);
    await waitIndexed(request, session, term, doc.id);

    const header = page.getByPlaceholder("Search files, documents...");
    await header.fill(`  ${term}  `);
    await header.press("Enter");

    await expect(page).toHaveURL(new RegExp(`/search\\?q=${term}$`));
    await expect(page.getByPlaceholder(SEARCH_PLACEHOLDER)).toHaveValue(term);
    const row = page.getByRole("link", { name: new RegExp(`Otter ${term} plan`) });
    await expect(row).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(`1 result for`)).toBeVisible();

    await row.click();
    await expect(page).toHaveURL(new RegExp(`/documents/${doc.id}`));
  });

  test("type filter narrows results to files", async ({ page, request }) => {
    const term = word("e2etype");
    const doc = await createDocument(request, session, `${term} notes`, term);
    const fileId = await indexFile(request, session, `${term}.txt`);
    await waitIndexed(request, session, term, doc.id);
    await waitIndexed(request, session, term, fileId);

    await page.goto(`/search?q=${term}`);
    await expect(page.getByText(/2 results for/)).toBeVisible({ timeout: 10_000 });

    await page.locator("form button[type='button']").first().click();
    await page.getByRole("button", { name: "Files", exact: true }).click();
    await expect(page.getByRole("link", { name: new RegExp(`${term}\\.txt`) })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(`${term} notes`) })).toHaveCount(0);
    await expect(page.getByRole("link", { name: new RegExp(`${term}\\.txt`) })).toHaveAttribute("href", `/files/${fileId}`);
  });

  test("no-result and cleared/empty states", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByText("Search OtterWorks")).toBeVisible();

    const input = page.getByPlaceholder(SEARCH_PLACEHOLDER);
    const gibberish = word("zzznothing");
    await input.fill(gibberish);
    await input.press("Enter");
    await expect(page.getByText("No results found")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(`No results for "${gibberish}". Try different keywords.`)).toBeVisible();

    await page.locator("form button[type='button']").nth(1).click();
    await expect(input).toHaveValue("");
    await expect(page.getByText("Search OtterWorks")).toBeVisible();
  });

  test("result count pluralises from the total", async ({ page, request }) => {
    const term = word("e2ecount");
    const a = await createDocument(request, session, `${term} one`, term);
    const b = await createDocument(request, session, `${term} two`, term);
    await waitIndexed(request, session, term, a.id);
    await waitIndexed(request, session, term, b.id);

    await page.goto(`/search?q=${term}`);
    await expect(page.getByText(/^2 results for/)).toBeVisible({ timeout: 10_000 });
  });

  test("search-as-you-type surfaces matches before submitting", async ({ page, request }) => {
    const term = word("e2etype");
    const doc = await createDocument(request, session, `${term} live`, term);
    await waitIndexed(request, session, term, doc.id);

    await page.goto("/search");
    const suggestCalls: string[] = [];
    page.on("request", (r) => {
      if (/\/api\/v1\/search\/(suggest)?\?/.test(r.url())) suggestCalls.push(r.url());
    });
    await page.getByPlaceholder(SEARCH_PLACEHOLDER).pressSequentially(term.slice(0, 8), { delay: 50 });

    await expect(page.getByText(new RegExp(`${term} live`))).toBeVisible({ timeout: 5_000 });
    expect(suggestCalls.length).toBeGreaterThan(0);
  });
});
