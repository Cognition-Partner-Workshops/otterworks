import { test, expect } from "../fixtures/signed-in";

test.describe("Margins smoke (signed in)", () => {
  test("a signed-in customer sees SKU profitability rows on /margins", async ({ page, customer }) => {
    await test.step("open /margins as the signed-in customer", async () => {
      await page.goto("/margins");
      await expect(page).toHaveURL(/\/margins$/);
      await expect(page.getByRole("banner").getByText(customer.displayName)).toBeVisible();
      await expect(page.getByRole("heading", { name: "Margins", level: 1 })).toBeVisible();
    });

    await test.step("the SKU profitability grid lists margin rows", async () => {
      const main = page.getByRole("main");
      await expect(main.getByRole("heading", { name: /^SKU profitability \((\d+) of \1\)$/ })).toBeVisible();
      await expect(
        main.getByRole("row", { name: /^SLM-001 Atlantic Salmon Fillet Seafood .* -?\d+\.\d%$/ }),
      ).toBeVisible();
      await expect(main.getByText("No SKUs match the current filters.")).toHaveCount(0);
    });
  });
});
