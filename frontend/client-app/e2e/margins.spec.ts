import { test, expect } from "./smoke/margins-billing/margins-billing.fixtures";

// OTD-15 margins dashboard (AC-08…AC-13). Each test runs as a freshly
// registered customer (real gateway JWT), so requests flow through the real
// gateway + analytics-service. The SKU catalogue is the analytics seed
// (services/analytics-service/src/main/resources/seed/market-series/products.csv).
const SEEDED_SKUS = 40;
const SEEDED_SEAFOOD_SKUS = 18;
const SEEDED_SLM_SKUS = 12;

function marginOf(rowText: string): number {
  return parseFloat(rowText.trim().split(/\s+/).at(-1)!);
}

test.describe("Margins dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/margins");
    await expect(page.getByRole("heading", { name: "Margins", level: 1 })).toBeVisible();
  });

  test("renders KPI tiles, charts, caption, badge and grid (AC-08/AC-13)", async ({ page }) => {
    const main = page.getByRole("main");

    await test.step("KPI tiles show their labels", async () => {
      for (const label of ["Gross Margin %", "COGS / unit", "Salmon Index", "Freight Index"]) {
        await expect(main.getByText(label, { exact: true })).toBeVisible();
      }
    });

    await test.step("caption names the data date and source", async () => {
      await expect(
        main.getByText(/^Data as of \d{4}-\d{2}-\d{2}.* — Source: Trading Economics \(manual pull\)$/),
      ).toBeVisible();
      // AC-13: fresh stack default is synthetic; a manual pull switches it to live.
      await expect(main.getByText(/^(synthetic|live)$/)).toBeVisible();
    });

    await test.step("both charts are rendered", async () => {
      await expect(main.getByRole("heading", { name: "Commodity & freight prices (180d)" })).toBeVisible();
      await expect(main.getByRole("heading", { name: "Average margin % (180d)" })).toBeVisible();
    });

    await test.step("grid lists every seeded SKU", async () => {
      await expect(
        main.getByRole("heading", { name: `SKU profitability (${SEEDED_SKUS} of ${SEEDED_SKUS})` }),
      ).toBeVisible();
      // +1 for the header row
      await expect(main.getByRole("table").getByRole("row")).toHaveCount(SEEDED_SKUS + 1);
    });
  });

  test("grid sorting and filtering work (AC-09)", async ({ page }) => {
    const main = page.getByRole("main");
    const table = main.getByRole("table");
    const dataRows = table.getByRole("row").filter({ has: page.getByRole("cell") });
    const margins = async () => (await dataRows.allInnerTexts()).map(marginOf);

    await test.step("sort by Margin % ascending", async () => {
      await expect(dataRows).toHaveCount(SEEDED_SKUS);
      await table.getByRole("button", { name: "Margin %" }).click();
      await expect.poll(async () => {
        const values = await margins();
        return values.every((v, i) => i === 0 || values[i - 1] <= v);
      }).toBe(true);
    });

    await test.step("sort by Margin % descending", async () => {
      await table.getByRole("button", { name: "Margin %" }).click();
      await expect.poll(async () => {
        const values = await margins();
        return values.every((v, i) => i === 0 || values[i - 1] >= v);
      }).toBe(true);
    });

    await test.step("text filter narrows rows to matching SKUs", async () => {
      await main.getByPlaceholder("Filter by SKU, name, supplier…").fill("SLM-");
      await expect(dataRows).toHaveCount(SEEDED_SLM_SKUS);
      await expect(
        main.getByRole("heading", { name: `SKU profitability (${SEEDED_SLM_SKUS} of ${SEEDED_SKUS})` }),
      ).toBeVisible();
      for (const text of await dataRows.allInnerTexts()) expect(text).toMatch(/^SLM-/);
      await main.getByPlaceholder("Filter by SKU, name, supplier…").fill("");
      await expect(dataRows).toHaveCount(SEEDED_SKUS);
    });

    await test.step("category filter keeps only Seafood rows", async () => {
      await main.getByRole("combobox").selectOption("Seafood");
      await expect(dataRows).toHaveCount(SEEDED_SEAFOOD_SKUS);
      await expect(dataRows.filter({ has: page.getByRole("cell", { name: "Seafood", exact: true }) }))
        .toHaveCount(SEEDED_SEAFOOD_SKUS);
    });
  });

  test("Export CSV downloads backend-generated CSV (AC-10)", async ({ page }) => {
    const main = page.getByRole("main");
    await expect(main.getByRole("row", { name: /^SLM-001 / })).toBeVisible();

    const download = await test.step("click Export CSV", async () => {
      const downloadPromise = page.waitForEvent("download");
      await main.getByRole("button", { name: "Export CSV" }).click();
      return downloadPromise;
    });

    await test.step("the file is the backend margins CSV", async () => {
      expect(download.suggestedFilename()).toMatch(/^sku-margins-\d{4}-\d{2}-\d{2}\.csv$/);
      const chunks: Buffer[] = [];
      for await (const chunk of await download.createReadStream()) chunks.push(chunk as Buffer);
      const csv = Buffer.concat(chunks).toString("utf-8");
      expect(csv.split("\n")[0]).toBe(
        "sku,name,category,supplier,list_price_usd,commodity_cost_usd,freight_cost_usd,overhead_cost_usd,cogs_usd,margin_pct",
      );
      expect(csv).toContain("SLM-001");
      await expect(page.getByText("Margins CSV exported")).toBeVisible();
    });
  });

  test("sidebar navigation and direct URL work (AC-12)", async ({ page }) => {
    await test.step("open Margins from the dashboard sidebar", async () => {
      await page.goto("/dashboard");
      await page.getByRole("link", { name: "Margins" }).click();
      await expect(page).toHaveURL(/\/margins$/);
      await expect(page.getByRole("heading", { name: "Margins", level: 1 })).toBeVisible();
    });

    await test.step("navigate to Files", async () => {
      await page.getByRole("link", { name: "Files", exact: true }).click();
      await expect(page).toHaveURL(/\/files$/);
    });

    await test.step("browser back returns to Margins", async () => {
      await page.goBack();
      await expect(page).toHaveURL(/\/margins$/);
      await expect(page.getByRole("heading", { name: "Margins", level: 1 })).toBeVisible();
    });
  });
});

test.describe("Margins with a stubbed analytics response", () => {
  test("shows friendly error state when margins API fails (AC-11)", async ({ page }) => {
    await page.route("**/api/v1/analytics/margins", (route) =>
      route.fulfill({ status: 500, body: "boom" }),
    );

    await test.step("open /margins while the margins API returns 500", async () => {
      await page.goto("/margins");
    });

    await test.step("the error state offers a retry", async () => {
      await expect(page.getByRole("heading", { name: "Margins data is unavailable" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
    });
  });

  test("renders a SKU row returned by the margins API", async ({ page }) => {
    await page.route("**/api/v1/analytics/margins", (route) =>
      route.fulfill({
        json: {
          as_of_date: "2026-07-16",
          source: "synthetic",
          last_sync_at: null,
          kpis: { gross_margin_pct: 48, avg_cogs_usd: 6.5, salmon_index: 4.2, freight_index: 1200 },
          rows: [
            {
              sku: "SLM-001",
              name: "Atlantic Salmon",
              category: "Seafood",
              supplier: "North Star",
              list_price_usd: 12.5,
              commodity_cost_usd: 5,
              freight_cost_usd: 0.5,
              overhead_cost_usd: 1,
              cogs_usd: 6.5,
              margin_pct: 48,
            },
          ],
        },
      }),
    );

    await test.step("open /margins", async () => {
      await page.goto("/margins");
    });

    await test.step("the stubbed row and KPIs are rendered", async () => {
      const main = page.getByRole("main");
      await expect(main.getByText("Data as of 2026-07-16 — Source: Trading Economics (manual pull)")).toBeVisible();
      await expect(
        main.getByRole("row", { name: "SLM-001 Atlantic Salmon Seafood North Star $12.50 $6.50 48.0%" }),
      ).toBeVisible();
      await expect(main.getByRole("heading", { name: "SKU profitability (1 of 1)" })).toBeVisible();
    });
  });
});
