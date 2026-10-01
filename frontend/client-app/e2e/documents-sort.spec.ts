import { test, expect, type Page } from "@playwright/test";

// Self-contained: auth profile and documents API are mocked so the spec
// exercises only the client-side sort dropdown and its ?sort= URL state.
const documents = [
  {
    id: "doc-beta",
    title: "Beta roadmap",
    createdAt: "2026-09-01T09:00:00Z",
    updatedAt: "2026-09-20T09:00:00Z",
  },
  {
    id: "doc-alpha",
    title: "Alpha meeting notes",
    createdAt: "2026-01-10T09:00:00Z",
    updatedAt: "2026-09-28T09:00:00Z",
  },
  {
    id: "doc-charlie",
    title: "Charlie launch checklist",
    createdAt: "2026-08-15T09:00:00Z",
    updatedAt: "2026-09-29T09:00:00Z",
  },
].map((doc) => ({
  content: "",
  ownerId: "user-1",
  ownerName: "Olive Otter",
  parentId: null,
  sharedWith: [],
  collaborators: [],
  tags: [],
  wordCount: 0,
  ...doc,
}));

const byLastEdited = ["Charlie launch checklist", "Alpha meeting notes", "Beta roadmap"];
const byName = ["Alpha meeting notes", "Beta roadmap", "Charlie launch checklist"];
const byCreated = ["Beta roadmap", "Charlie launch checklist", "Alpha meeting notes"];

async function mockBackend(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("otter_access_token", "e2e-token");
  });
  await page.route("**/api/v1/**", (route) => route.fulfill({ json: {} }));
  await page.route("**/api/v1/auth/profile", (route) =>
    route.fulfill({
      json: { id: "user-1", email: "olive@otterworks.test", displayName: "Olive Otter" },
    })
  );
  await page.route(
    (url) => url.pathname === "/api/v1/documents",
    (route) =>
      route.fulfill({
        json: { data: documents, total: documents.length, page: 1, pageSize: 50, totalPages: 1 },
      })
  );
}

async function documentTitles(page: Page) {
  const cards = page.locator('a[href^="/documents/doc-"]');
  await expect(cards).toHaveCount(documents.length);
  return Promise.all(
    (await cards.all()).map(async (card) =>
      (await card.locator("p.font-medium").first().innerText()).trim()
    )
  );
}

test.describe("Documents sort dropdown", () => {
  test.beforeEach(async ({ page }) => {
    await mockBackend(page);
  });

  test("defaults to Last edited when no ?sort= is set", async ({ page }) => {
    await page.goto("/documents");
    const sortSelect = page.getByLabel("Sort documents");
    await expect(sortSelect).toHaveValue("updated");
    await expect(sortSelect.locator("option")).toHaveText([
      "Last edited",
      "Name A to Z",
      "Date created",
    ]);
    expect(await documentTitles(page)).toEqual(byLastEdited);
  });

  test("switching options reorders documents and updates ?sort=", async ({ page }) => {
    await page.goto("/documents");
    const sortSelect = page.getByLabel("Sort documents");

    await sortSelect.selectOption({ label: "Date created" });
    await expect(page).toHaveURL(/[?&]sort=created\b/);
    await expect.poll(() => documentTitles(page)).toEqual(byCreated);

    await sortSelect.selectOption({ label: "Name A to Z" });
    await expect(page).toHaveURL(/[?&]sort=name\b/);
    await expect.poll(() => documentTitles(page)).toEqual(byName);

    await sortSelect.selectOption({ label: "Last edited" });
    await expect(page).toHaveURL(/[?&]sort=updated\b/);
    await expect.poll(() => documentTitles(page)).toEqual(byLastEdited);
  });

  test("restores the sort from the URL after a reload", async ({ page }) => {
    await page.goto("/documents?sort=created");
    const sortSelect = page.getByLabel("Sort documents");
    await expect(sortSelect).toHaveValue("created");
    expect(await documentTitles(page)).toEqual(byCreated);

    await sortSelect.selectOption({ label: "Name A to Z" });
    await expect(page).toHaveURL(/[?&]sort=name\b/);
    await page.reload();
    await expect(page.getByLabel("Sort documents")).toHaveValue("name");
    expect(await documentTitles(page)).toEqual(byName);
  });

  test("falls back to Last edited for an unknown ?sort= value", async ({ page }) => {
    await page.goto("/documents?sort=bogus");
    await expect(page.getByLabel("Sort documents")).toHaveValue("updated");
    expect(await documentTitles(page)).toEqual(byLastEdited);
  });
});
