import { expect, test } from "@playwright/test";

const CARD_OK = "4242 4242 4242 4242";

test("guest browses, bags an item and checks out", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("hero")).toBeVisible();

  await page.getByTestId("dept-women").click();
  await expect(page.getByTestId("plp-title")).toHaveText("Women");

  // First product that isn't sold out.
  const card = page.getByTestId("product-card").filter({ hasNot: page.getByText("Sold out", { exact: true }) }).first();
  await card.click();
  await expect(page.getByTestId("pdp-name")).toBeVisible();

  // Pick the first in-stock size of any colour.
  const swatches = page.locator('[data-testid^="swatch-"]');
  const n = await swatches.count();
  let picked = false;
  for (let i = 0; i < n && !picked; i++) {
    await swatches.nth(i).click();
    const size = page.locator('[data-testid^="size-"][data-available="true"]').first();
    if (await size.count()) {
      await size.click();
      picked = true;
    }
  }
  expect(picked).toBe(true);

  await page.getByTestId("add-to-bag").click();
  await expect(page.getByTestId("mini-bag")).toBeVisible();
  await expect(page.getByTestId("bag-count")).toHaveText("1");
  await page.getByTestId("view-bag").click();

  await expect(page.getByTestId("bag-line")).toHaveCount(1);
  await page.getByTestId("checkout-button").click();

  await page.getByTestId("email").fill("playwright@example.com");
  await page.getByTestId("ship-name").fill("Pat Wright");
  await page.getByTestId("ship-line1").fill("1 Market St");
  await page.getByTestId("ship-city").fill("San Francisco");
  await page.getByTestId("ship-state").selectOption("CA");
  await page.getByTestId("ship-zip").fill("94105");
  await page.getByTestId("card-name").fill("Pat Wright");
  await page.getByTestId("card-number").fill(CARD_OK);
  await page.getByTestId("card-exp").fill("12/30");
  await page.getByTestId("card-cvc").fill("123");
  await expect(page.getByTestId("quote")).toBeVisible();
  await page.getByTestId("place-order").click();

  await expect(page.getByTestId("order-number")).toHaveText(/^OS-1\d{5}$/, { timeout: 15_000 });
  await expect(page.getByTestId("bag-count")).toHaveText("0");
});
