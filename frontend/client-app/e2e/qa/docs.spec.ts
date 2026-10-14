import { test, expect, type Page } from "@playwright/test";
import { registerUser, expectDashboard } from "../fixtures/test-helpers";

// Docs-area QA: critical document paths against the real local stack.

async function apiToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem("otter_access_token"));
  expect(token).toBeTruthy();
  return token as string;
}

async function getDocument(page: Page, id: string) {
  const res = await page.request.get(`/api/v1/documents/${id}`, {
    headers: { Authorization: `Bearer ${await apiToken(page)}` },
  });
  expect(res.status()).toBe(200);
  return res.json();
}

async function createFromList(page: Page): Promise<string> {
  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /New document/i }).click();
  await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  return page.url().split("/").pop() as string;
}

test.describe("QA docs", () => {
  test.beforeEach(async ({ page }) => {
    await registerUser(page);
    await expectDashboard(page);
  });

  test("create, type, autosave and persist across reload", async ({ page }) => {
    const id = await createFromList(page);
    const editor = page.locator(".ProseMirror");
    await expect(editor).toBeVisible();

    await editor.click();
    await page.keyboard.type("QA autosave body", { delay: 30 });
    await expect(page.getByText("All changes saved")).toBeVisible({ timeout: 10_000 });

    await expect
      .poll(async () => (await getDocument(page, id)).content, { timeout: 10_000 })
      .toContain("QA autosave body");

    await page.reload();
    await expect(page.locator(".ProseMirror")).toContainText("QA autosave body");
  });

  test("Tiptap toolbar formatting keeps every typed character and persists", async ({
    page,
  }) => {
    const id = await createFromList(page);
    const editor = page.locator(".ProseMirror");
    await expect(editor).toBeVisible();

    await editor.click();
    await page.keyboard.type("plain ", { delay: 30 });
    await page.getByTitle("Bold").click();
    await expect(editor).toBeFocused();
    await page.waitForTimeout(250);
    await page.keyboard.type("bold words", { delay: 30 });

    await expect(editor.locator("strong")).toHaveText("bold words");
    await expect
      .poll(async () => (await getDocument(page, id)).content, { timeout: 10_000 })
      .toMatch(/plain .*<strong>bold words<\/strong>/);

    await page.reload();
    await expect(page.locator(".ProseMirror strong")).toHaveText("bold words");
  });

  test("rename from the editor header persists and records history", async ({ page }) => {
    const id = await createFromList(page);
    const newTitle = `QA Renamed ${Date.now()}`;

    await page.getByTitle("Click to rename").click();
    const input = page.locator("input:focus");
    await input.fill(newTitle);
    const saved = page.waitForResponse(
      (r) => r.url().includes(`/documents/${id}`) && r.request().method() === "PATCH"
    );
    await input.press("Enter");
    expect((await saved).status()).toBe(200);

    await page.reload();
    await expect(page.getByTitle("Click to rename")).toHaveText(newTitle);

    const versions = await page.request.get(`/api/v1/documents/${id}/versions`, {
      headers: { Authorization: `Bearer ${await apiToken(page)}` },
    });
    expect(versions.status()).toBe(200);
    const history = await versions.json();
    expect(history.length).toBeGreaterThanOrEqual(2);
    expect(history[history.length - 1].title).toBe(newTitle);

    await page.goto("/documents");
    await expect(page.getByText(newTitle)).toBeVisible();
  });

  test("delete from the editor removes it from the list", async ({ page }) => {
    const id = await createFromList(page);
    const title = `QA Delete ${Date.now()}`;
    await page.getByTitle("Click to rename").click();
    await page.locator("input:focus").fill(title);
    await page.locator("input:focus").press("Enter");
    await expect(page.getByTitle("Click to rename")).toHaveText(title);

    await page.locator("button.text-red-600").click();
    await expect(page).toHaveURL(/\/documents$/);
    await expect(page.getByText(title)).toHaveCount(0);

    const res = await page.request.get(`/api/v1/documents/${id}`, {
      headers: { Authorization: `Bearer ${await apiToken(page)}` },
    });
    expect(res.status()).toBe(404);
  });

  test("document list filter narrows by title", async ({ page }) => {
    await createFromList(page);
    const title = `QA Filter ${Date.now()}`;
    await page.getByTitle("Click to rename").click();
    await page.locator("input:focus").fill(title);
    await page.locator("input:focus").press("Enter");
    await expect(page.getByTitle("Click to rename")).toHaveText(title);

    await createFromList(page);
    await page.goto("/documents");
    await page.getByPlaceholder("Filter documents...").fill("QA Filter");
    await expect(page.getByText(title)).toBeVisible();
    await expect(page.getByText("Untitled document")).toHaveCount(0);
  });

  test("margins page renders KPIs and rows", async ({ page }) => {
    await page.goto("/margins");
    await expect(page.getByRole("heading", { name: "Margins" })).toBeVisible();
    await expect(page.getByText("Gross Margin %")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("tbody tr").first()).toBeVisible();
  });
});
