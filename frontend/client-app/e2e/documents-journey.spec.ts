import { test, expect, type Page } from "@playwright/test";
import { registerUser, expectDashboard } from "./fixtures/test-helpers";

async function signUp(page: Page) {
  await registerUser(page, { name: "Docs QA" });
  await expectDashboard(page);
}

async function createDocument(page: Page): Promise<string> {
  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /New document/i }).first().click();
  await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  return page.url().split("/").pop() as string;
}

async function rename(page: Page, title: string) {
  await page.getByTitle("Click to rename").click();
  const input = page.locator("input.border-otter-500");
  await input.fill(title);
  const saved = page.waitForResponse(
    (r) => r.request().method() === "PATCH" && /\/api\/v1\/documents\//.test(r.url())
  );
  await input.press("Enter");
  expect((await saved).status()).toBe(200);
  await expect(page.getByTitle("Click to rename")).toHaveText(title);
}

test.describe("Document journeys", () => {
  test("new user sees the empty state and can create a first document", async ({ page }) => {
    await signUp(page);
    await page.goto("/documents");
    await expect(page.getByText("No documents yet")).toBeVisible();
    await page.getByRole("button", { name: "Create document" }).click();
    await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/, { timeout: 15_000 });
    await expect(page.getByTitle("Click to rename")).toHaveText("Untitled document");
  });

  test("rename persists across reload and shows in the list and filter", async ({ page }) => {
    await signUp(page);
    const id = await createDocument(page);
    const title = `QA Rename ${Date.now()}`;
    await rename(page, title);

    await page.reload();
    await expect(page.getByTitle("Click to rename")).toHaveText(title);

    await page.goto("/documents");
    await expect(page.getByText(title)).toBeVisible();
    await page.getByPlaceholder("Filter documents...").fill("no-such-doc-zzz");
    await expect(page.getByText("No matching documents")).toBeVisible();
    await page.getByPlaceholder("Filter documents...").fill(title.slice(0, 12));
    await expect(page.getByText(title)).toBeVisible();
    await page.getByText(title).click();
    await page.waitForURL((url) => url.pathname === `/documents/${id}`);
  });

  test("typing in the editor autosaves and survives reload", async ({ page }) => {
    await signUp(page);
    await createDocument(page);
    const editor = page.locator(".ProseMirror").first();
    await expect(editor).toBeVisible({ timeout: 15_000 });

    const autosave = page.waitForResponse(
      (r) =>
        r.request().method() === "PATCH" &&
        /\/api\/v1\/documents\//.test(r.url()) &&
        (r.request().postData() ?? "").includes("autosave check"),
      { timeout: 15_000 }
    );
    await editor.click();
    await page.keyboard.type("autosave check from playwright");
    expect((await autosave).status()).toBe(200);

    await page.reload();
    await expect(page.locator(".ProseMirror").first()).toContainText(
      "autosave check from playwright",
      { timeout: 15_000 }
    );
  });

  test("delete from the editor returns to an updated list", async ({ page }) => {
    await signUp(page);
    await createDocument(page);
    const title = `QA Delete ${Date.now()}`;
    await rename(page, title);

    await page.locator("button.text-red-600").first().click();
    await expect(page).toHaveURL(/\/documents$/, { timeout: 15_000 });
    await expect(page.getByText(title)).toHaveCount(0);
    await expect(page.getByText("No documents yet")).toBeVisible();
  });

  test("opening an unknown document shows not found", async ({ page }) => {
    await signUp(page);
    await page.goto("/documents/00000000-0000-0000-0000-000000000000");
    await expect(page.getByText("Document not found")).toBeVisible({ timeout: 15_000 });
    await page.getByRole("link", { name: "Back to documents" }).click();
    await expect(page).toHaveURL(/\/documents$/);
  });
});
