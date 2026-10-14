import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.API_GATEWAY_URL || "http://localhost:8080";

interface Session {
  userId: string;
  token: string;
  refresh: string;
}

async function registerViaApi(request: APIRequestContext, prefix: string): Promise<Session> {
  const email = `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.test`;
  const res = await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password: "OtterworksTest123!", displayName: `QA ${prefix}` },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return { userId: body.user.id, token: body.accessToken, refresh: body.refreshToken };
}

function auth(s: Session) {
  return { Authorization: `Bearer ${s.token}` };
}

async function createFolder(request: APIRequestContext, s: Session, name: string, parentId: string | null = null) {
  const res = await request.post(`${API}/api/v1/folders`, {
    headers: auth(s),
    data: { name, parent_id: parentId, owner_id: s.userId },
  });
  expect(res.status()).toBe(201);
  return (await res.json()) as { id: string; name: string };
}

async function upload(request: APIRequestContext, s: Session, name: string, folderId?: string) {
  const multipart: Record<string, string | { name: string; mimeType: string; buffer: Buffer }> = {
    file: { name, mimeType: "text/plain", buffer: Buffer.from(`qa ${name}`) },
    owner_id: s.userId,
  };
  if (folderId) multipart.folder_id = folderId;
  const res = await request.post(`${API}/api/v1/files/upload`, { headers: auth(s), multipart });
  expect(res.status()).toBe(201);
  return (await res.json()).file as { id: string; name: string };
}

async function signIn(page: Page, s: Session) {
  await page.addInitScript(
    ([token, refresh]) => {
      localStorage.setItem("otter_access_token", token);
      localStorage.setItem("otter_refresh_token", refresh);
    },
    [s.token, s.refresh]
  );
}

test.describe("QA browsing — critical paths", () => {
  test("dashboard and sidebar navigation reach every browsing page with empty states", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-nav");
    await signIn(page, s);

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("No recent files")).toBeVisible();

    const nav = page.locator("aside, nav").first();
    const pages: Array<[string, RegExp, string]> = [
      ["Recent", /\/recent$/, "No recent items"],
      ["Starred", /\/starred$/, "No starred items"],
      ["Trash", /\/trash$/, "Trash is empty"],
      ["Files", /\/files$/, "This folder is empty"],
    ];
    for (const [label, url, empty] of pages) {
      await nav.getByRole("link", { name: label, exact: true }).click();
      await expect(page).toHaveURL(url);
      await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible();
      await expect(page.getByText(empty)).toBeVisible();
    }
  });

  test("folder navigation updates URL and breadcrumbs; breadcrumbs navigate back", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-tree");
    const folder = await createFolder(request, s, "QA Projects");
    await upload(request, s, "inside-projects.txt", folder.id);
    await signIn(page, s);

    await page.goto("/files");
    await page.getByText("QA Projects").click();
    await expect(page).toHaveURL(new RegExp(`/files\\?folder=${folder.id}$`));
    const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumbs).toContainText("QA Projects");
    await expect(page.getByText("inside-projects.txt")).toBeVisible();

    await crumbs.getByRole("link", { name: "Files" }).click();
    await expect(page).toHaveURL(/\/files$/);
    await expect(page.getByText("QA Projects")).toBeVisible();

    await page.getByText("QA Projects").click();
    await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Home" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("deep link to a nested folder renders its contents and breadcrumb", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-deeplink");
    const parent = await createFolder(request, s, "Deep Parent");
    const child = await createFolder(request, s, "Deep Child", parent.id);
    await upload(request, s, "deep-file.txt", child.id);
    await signIn(page, s);

    await page.goto(`/files?folder=${child.id}`);
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Deep Child");
    await expect(page.getByText("deep-file.txt")).toBeVisible();
    await page.reload();
    await expect(page.getByText("deep-file.txt")).toBeVisible();
  });

  test("nested folder breadcrumb shows the full ancestor path", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-crumbs");
    const parent = await createFolder(request, s, "Crumb Parent");
    const child = await createFolder(request, s, "Crumb Child", parent.id);
    await signIn(page, s);

    await page.goto(`/files?folder=${child.id}`);
    const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumbs).toContainText("Crumb Child");
    await expect(crumbs.getByRole("link", { name: "Crumb Parent" })).toHaveAttribute(
      "href",
      `/files?folder=${parent.id}`
    );
  });

  test("root Files view does not show files that live inside folders", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-root");
    const folder = await createFolder(request, s, "Holder");
    await upload(request, s, "nested-only.txt", folder.id);
    await upload(request, s, "root-only.txt");
    await signIn(page, s);

    await page.goto("/files");
    await expect(page.getByText("root-only.txt")).toBeVisible();
    await expect(page.getByText("nested-only.txt")).toHaveCount(0);
  });

  test("sorting by name reorders files", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-sort");
    for (const n of ["bravo.txt", "alpha.txt", "charlie.txt"]) await upload(request, s, n);
    await signIn(page, s);

    await page.goto("/files");
    await expect(page.getByText("alpha.txt")).toBeVisible();
    const sort = page.locator("select").filter({ hasText: "Last modified" });
    const order = () => page.getByText(/^(alpha|bravo|charlie)\.txt$/).allTextContents();

    await sort.selectOption("name-asc");
    await expect.poll(order).toEqual(["alpha.txt", "bravo.txt", "charlie.txt"]);
    await sort.selectOption("name-desc");
    await expect.poll(order).toEqual(["charlie.txt", "bravo.txt", "alpha.txt"]);
  });

  test("move to trash, restore from trash, file returns to Files", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-trash");
    const file = await upload(request, s, "restore-me.txt");
    const trashed = await request.post(`${API}/api/v1/files/${file.id}/trash`, { headers: auth(s) });
    expect(trashed.status()).toBe(200);
    await signIn(page, s);

    await page.goto("/trash");
    await expect(page.getByText("restore-me.txt")).toBeVisible();
    await page.getByRole("button", { name: /Restore/ }).first().click();
    await expect(page.getByText("Trash is empty")).toBeVisible();

    await page.goto("/files");
    await expect(page.getByText("restore-me.txt")).toBeVisible();
  });

  test("starring a file surfaces it on the Starred page", async ({ page, request }) => {
    const s = await registerViaApi(request, "qa-e2e-star");
    await upload(request, s, "favourite.txt");
    await signIn(page, s);

    await page.goto("/files");
    await expect(page.getByText("favourite.txt")).toBeVisible();
    await page.getByRole("button", { name: "Star", exact: true }).first().click({ force: true });

    await page.goto("/starred");
    await expect(page.getByText("favourite.txt")).toBeVisible();
    await expect(page.getByText("No starred items")).toHaveCount(0);
  });
});
