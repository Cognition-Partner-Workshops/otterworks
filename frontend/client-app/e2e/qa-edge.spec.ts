import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

// QA edge cases. Bags are seeded through the same /api proxy the storefront uses.
async function skuWithStock(api: APIRequestContext, min: number, exact?: number) {
  const list = await (await api.get("/api/products?pageSize=500")).json();
  for (const p of list.items) {
    const d = await (await api.get(`/api/products/${p.id}`)).json();
    const s = d.skus.find((s: { stock: number }) => (exact === undefined ? s.stock >= min : s.stock === exact));
    if (s) return s.sku as string;
  }
  throw new Error("no matching sku");
}

async function seedBag(page: Page, api: APIRequestContext, sku: string, quantity = 1) {
  const bag = await (await api.post("/api/bags")).json();
  expect((await api.post(`/api/bags/${bag.id}/items`, { data: { sku, quantity } })).ok()).toBeTruthy();
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.evaluate((id) => localStorage.setItem("os_bag", id), bag.id);
  return bag.id as string;
}

async function fillCheckout(page: Page, card = "4242 4242 4242 4242") {
  await page.getByTestId("email").fill("qa@example.com");
  for (const [k, v] of Object.entries({ name: "Q A", line1: "1 Market St", city: "San Francisco", zip: "94105" })) await page.getByTestId(`ship-${k}`).fill(v);
  await page.getByTestId("card-name").fill("Q A");
  await page.getByTestId("card-number").fill(card);
  await page.getByTestId("card-exp").fill("12/30");
  await page.getByTestId("card-cvc").fill("123");
}

test("empty bag state offers a way back to shopping", async ({ page }) => {
  await page.goto("/bag");
  await expect(page.getByRole("heading", { name: "Your bag is empty" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Shop new arrivals" })).toBeVisible();
});

test("unknown and below-minimum promo codes explain themselves; bag survives a refresh", async ({ page, request }) => {
  await seedBag(page, request, await skuWithStock(request, 3));
  await page.goto("/bag");
  await page.getByTestId("promo-input").fill("NOPE");
  await page.getByTestId("promo-apply").click();
  await expect(page.getByText("We don't recognize the code NOPE")).toBeVisible();
  await page.getByTestId("promo-input").fill("OTTERWELCOME");
  await page.getByTestId("promo-apply").click();
  await expect(page.getByText(/Add \$[\d.]+ more to use OTTERWELCOME/)).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("bag-line")).toHaveCount(1);
});

test("invalid Luhn card is rejected without placing an order", async ({ page, request }) => {
  await seedBag(page, request, await skuWithStock(request, 3));
  await page.goto("/checkout");
  await fillCheckout(page, "4242 4242 4242 4241");
  await page.getByTestId("place-order").click();
  await expect(page.getByTestId("checkout-error")).toContainText("Check your card number");
  await expect(page).toHaveURL(/\/checkout/);
});

test("mini bag closes with Escape", async ({ page, request }) => {
  const sku = await skuWithStock(request, 3);
  await seedBag(page, request, sku);
  const pid = sku.split("-")[0];
  await page.goto(`/p/${pid}`);
  await page.locator('[data-available="true"]').first().click();
  await page.getByRole("button", { name: /add to bag/i }).click();
  await expect(page.getByTestId("mini-bag")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("mini-bag")).toBeHidden();
});

test("a line that sold out while in the bag is flagged before checkout", async ({ page, request }) => {
  test.fail(true, "KNOWN FAILING QA-02: bag shows 'Only 0 left' and still offers checkout");
  const sku = await skuWithStock(request, 0, 2);
  await seedBag(page, request, sku, 2);
  const rival = await (await request.post("/api/bags")).json();
  await request.post(`/api/bags/${rival.id}/items`, { data: { sku, quantity: 2 } });
  const r = await request.post("/api/checkout", { data: { bagId: rival.id, email: "rival@example.com", fulfillment: "SHIP", shippingMethod: "STANDARD",
    address: { name: "R V", line1: "1 Main St", city: "Austin", state: "TX", zip: "73301" }, card: { number: "4242424242424242", expMonth: 12, expYear: 2030, cvc: "123", name: "R V" } } });
  expect(r.status()).toBe(201);
  await page.goto("/bag");
  await expect(page.getByText("Only 0 left")).toHaveCount(0);
  await expect(page.getByTestId("checkout-button")).toBeDisabled();
});
