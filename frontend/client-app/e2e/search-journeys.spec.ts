import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { uniqueEmail, loginUser } from "./fixtures/test-helpers";

/**
 * Search QA (top layer): authenticated search journeys against seeded data.
 * Seeds a document straight into the search index through the gateway, then
 * drives the UI as that user.
 */
const API_URL = process.env.API_URL || "http://localhost:8080";
const PASSWORD = "Passw0rd!23";

type Seed = { email: string; word: string; docId: string; fileId: string };

async function seedUser(request: APIRequestContext): Promise<Seed> {
  const email = uniqueEmail();
  const reg = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: { displayName: "Search QA", email, password: PASSWORD },
  });
  expect(reg.ok(), await reg.text()).toBeTruthy();
  const { accessToken, user } = await reg.json();
  const headers = { Authorization: `Bearer ${accessToken}` };
  const word = `qa${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const docId = crypto.randomUUID();
  const fileId = crypto.randomUUID();
  const doc = await request.post(`${API_URL}/api/v1/search/index/document`, {
    headers,
    data: { id: docId, title: `Otter plan ${word}`, content: `notes about ${word}`, owner_id: user.id },
  });
  expect(doc.status(), await doc.text()).toBe(201);
  const file = await request.post(`${API_URL}/api/v1/search/index/file`, {
    headers,
    data: { id: fileId, name: `${word}-sheet.csv`, mime_type: "text/csv", owner_id: user.id },
  });
  expect(file.status(), await file.text()).toBe(201);
  return { email, word, docId, fileId };
}

async function signIn(page: Page, seed: Seed) {
  await loginUser(page, seed.email, PASSWORD);
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
}

test.describe("Search journeys (signed in)", () => {
  let seed: Seed;

  test.beforeEach(async ({ page, request }) => {
    seed = await seedUser(request);
    await signIn(page, seed);
  });

  test("full-text query returns the seeded document and file", async ({ page }) => {
    await page.goto("/search");
    const input = page.getByPlaceholder("Search files, documents, and folders...");
    await input.fill(seed.word);
    await input.press("Enter");
    await expect(page.getByText(`Otter plan ${seed.word}`)).toBeVisible();
    await expect(page.getByText(`${seed.word}-sheet.csv`)).toBeVisible();
  });

  test("Files type filter hides documents", async ({ page }) => {
    await page.goto(`/search?q=${seed.word}`);
    await expect(page.getByText(`Otter plan ${seed.word}`)).toBeVisible();
    await page.locator("form button[type='button']").first().click();
    await page.getByRole("button", { name: "Files", exact: true }).click();
    await expect(page.getByText(`${seed.word}-sheet.csv`)).toBeVisible();
    await expect(page.getByText(`Otter plan ${seed.word}`)).toHaveCount(0);
  });

  test("clicking a document result opens the document", async ({ page }) => {
    await page.goto(`/search?q=${seed.word}`);
    await page.getByText(`Otter plan ${seed.word}`).click();
    await expect(page).toHaveURL(new RegExp(`/documents/${seed.docId}`));
  });

  test("header search bar navigates to results", async ({ page }) => {
    const bar = page.getByPlaceholder("Search files, documents...");
    await bar.fill(seed.word);
    await bar.press("Enter");
    await expect(page).toHaveURL(new RegExp(`/search\\?q=${seed.word}`));
    await expect(page.getByText(`Otter plan ${seed.word}`)).toBeVisible();
  });

  test("unknown term shows the no-results state", async ({ page }) => {
    await page.goto(`/search?q=zzxq${seed.word}nomatch`);
    await expect(page.getByText("No results found")).toBeVisible();
  });

  // [REAL] /api/v1/search/suggest exists but the UI never calls it: typing
  // without submitting shows no suggestions/results (no search-as-you-type).
  test("search-as-you-type shows matches before submitting", async ({ page }) => {
    await page.goto("/search");
    await page.getByPlaceholder("Search files, documents, and folders...").pressSequentially(seed.word.slice(0, 8));
    await expect(page.getByText(`Otter plan ${seed.word}`)).toBeVisible({ timeout: 5_000 });
  });
});
