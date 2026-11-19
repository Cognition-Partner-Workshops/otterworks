import { test, expect, type Page } from "@playwright/test";

const NO_RESULTS_QUERY = "xyznonexistent9999";

function isNoResultsSearch(url: URL) {
  return (
    url.pathname === "/api/v1/search" &&
    url.searchParams.get("q") === NO_RESULTS_QUERY
  );
}

async function expectNoSearchResults(page: Page) {
  const searchInput = page.getByPlaceholder(
    "Search files, documents, and folders..."
  );
  await searchInput.fill(NO_RESULTS_QUERY);
  const [request] = await Promise.all([
    page.waitForRequest(
      (request) => request.method() === "GET" && isNoResultsSearch(new URL(request.url()))
    ),
    searchInput.press("Enter"),
  ]);
  const response = await request.response();
  const outcome = response ? `HTTP ${response.status()}` : request.failure()?.errorText;
  expect(
    response?.ok(),
    `Search request for "${NO_RESULTS_QUERY}" failed (${outcome ?? "no response"})`
  ).toBe(true);

  await expect(
    page.getByRole("heading", { name: "No results found", exact: true }),
    `Expected no results for "${NO_RESULTS_QUERY}"`
  ).toBeVisible();
  await expect(
    page.getByText(`No results for "${NO_RESULTS_QUERY}". Try different keywords.`, { exact: true })
  ).toBeVisible();
}

test.describe("Search Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/search", { waitUntil: "domcontentloaded" });
  });

  test("shows Search heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Search", exact: true })
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays search input with placeholder", async ({ page }) => {
    await expect(
      page.getByPlaceholder("Search files, documents, and folders...")
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state before searching", async ({ page }) => {
    await expect(page.getByText("Search OtterWorks")).toBeVisible({
      timeout: 10_000,
    });
    await expect(
      page.getByText("Find files, documents, and folders across your workspace")
    ).toBeVisible();
  });

  test("has filter toggle button", async ({ page }) => {
    // The filter button is inside the search form
    const filterButton = page.locator("form button[type='button']").first();
    await expect(filterButton).toBeVisible({ timeout: 10_000 });
  });

  test("can type a query in the search input", async ({ page }) => {
    const searchInput = page.getByPlaceholder(
      "Search files, documents, and folders..."
    );
    await expect(searchInput).toBeVisible({ timeout: 10_000 });
    await searchInput.fill("test query");
    await expect(searchInput).toHaveValue("test query");
  });

  test("shows no results for gibberish query", async ({ page }) => {
    await expectNoSearchResults(page);
  });

  test("displays breadcrumb navigation", async ({ page }) => {
    // Breadcrumb nav (aria-label="Breadcrumb") should contain "Search"
    const breadcrumb = page.getByLabel("Breadcrumb").getByText("Search");
    await expect(breadcrumb).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Search no-results regression", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/v1/notifications/unread-count", (route) =>
      route.fulfill({ json: { count: 0 } })
    );
  });

  test("reaches no results on a CPU-throttled browser", async ({ page }) => {
    const session = await page.context().newCDPSession(page);
    await session.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.route(isNoResultsSearch, async (route) => {
      // Hold the response until the browser has rendered the pending state.
      await expect(page.getByRole("status", { name: "Loading" })).toBeVisible();
      await route.fulfill({ json: { results: [], total: 0 } });
    });

    await page.goto("/search", { waitUntil: "domcontentloaded" });
    await expectNoSearchResults(page);
  });

  test("fails with the status when the search request returns HTTP 500", async ({ page }) => {
    await page.route(isNoResultsSearch, (route) =>
      route.fulfill({ status: 500, json: { error: "Search failed" } })
    );

    await page.goto("/search", { waitUntil: "domcontentloaded" });
    await expect(expectNoSearchResults(page)).rejects.toThrow(
      `Search request for "${NO_RESULTS_QUERY}" failed (HTTP 500)`
    );
  });

  test("fails with the network error when the search request is aborted", async ({ page }) => {
    await page.route(isNoResultsSearch, (route) => route.abort());

    await page.goto("/search", { waitUntil: "domcontentloaded" });
    await expect(expectNoSearchResults(page)).rejects.toThrow(
      `Search request for "${NO_RESULTS_QUERY}" failed (net::ERR_FAILED)`
    );
  });

  test("fails when the search returns a matching result", async ({ page }) => {
    await page.route(isNoResultsSearch, (route) =>
      route.fulfill({
        json: {
          results: [{ id: "matching-doc", type: "document", title: NO_RESULTS_QUERY }],
          total: 1,
        },
      })
    );

    await page.goto("/search", { waitUntil: "domcontentloaded" });
    await expect(expectNoSearchResults(page)).rejects.toThrow(
      `Expected no results for "${NO_RESULTS_QUERY}"`
    );
    await expect(page.getByRole("link", { name: NO_RESULTS_QUERY })).toBeVisible();
  });
});
