import { test, expect } from "./margins.fixtures";

test(
  "margins page shows the SKU profitability grid from the analytics service",
  { tag: ["@smoke", "@page-margins"], annotation: { type: "route", description: "/margins" } },
  async ({ page, request, customer }) => {
    const response = await request.get("/api/v1/analytics/margins", { headers: customer.headers });
    await expect(response).toBeOK();
    const skuCount: number = (await response.json()).rows.length;
    expect(skuCount).toBeGreaterThan(0);

    await page.goto("/margins");

    await expect(page.getByRole("heading", { name: "Margins", level: 1 })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: `SKU profitability (${skuCount} of ${skuCount})` }),
    ).toBeVisible();
    // header row + one row per SKU
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(skuCount + 1);
  },
);
