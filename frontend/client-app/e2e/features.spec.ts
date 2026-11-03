import { expect, type APIRequestContext, type Page, test } from "@playwright/test";

type Sku = { sku: string; size: string; color: string; stock: number };
type Detail = { id: string; name: string; skus: Sku[] };

async function products(api: APIRequestContext, query = "pageSize=500"): Promise<{ id: string; stockState: string; collections: string[] }[]> {
  return (await (await api.get(`/api/products?${query}`)).json()).items;
}

async function detail(api: APIRequestContext, id: string): Promise<Detail> {
  return (await api.get(`/api/products/${id}`)).json();
}

async function inStockProduct(api: APIRequestContext): Promise<Detail> {
  const p = (await products(api, "department=women&category=dresses&pageSize=50")).find((x) => x.stockState === "IN_STOCK" && !x.collections.includes("maternity"))!;
  return detail(api, p.id);
}

async function guestOrder(api: APIRequestContext, email: string): Promise<string> {
  const p = await inStockProduct(api);
  const sku = p.skus.find((s) => s.stock >= 2)!.sku;
  const bag = (await (await api.post("/api/bags")).json()).id;
  await api.post(`/api/bags/${bag}/items`, { data: { sku, quantity: 1 } });
  const res = await api.post("/api/checkout", { data: {
    bagId: bag, email, fulfillment: "SHIP", shippingMethod: "STANDARD",
    address: { name: "Pat Wright", line1: "1 Market St", city: "San Francisco", state: "CA", zip: "94105" },
    card: { number: "4242424242424242", expMonth: 12, expYear: 2030, cvc: "123", name: "Pat Wright" },
  } });
  expect(res.status()).toBe(201);
  return (await res.json()).orderNumber;
}

async function signIn(page: Page) {
  await page.goto("/account/sign-in");
  await page.getByTestId("auth-email").fill("maya@ottershops.test");
  await page.getByTestId("auth-password").fill("otters-2026");
  await page.getByTestId("auth-submit").click();
  await expect(page).toHaveURL(/\/account$/);
}

test("typeahead search, results page and the no-results state", async ({ page }) => {
  await page.goto("/");
  const box = page.getByTestId("search-input").first();
  await box.fill("denim");
  await expect(page.getByTestId("search-suggestions")).toBeVisible();
  await expect(page.getByTestId("suggest-product").first()).toBeVisible();
  await box.press("ArrowDown");
  await expect(box).toHaveAttribute("aria-activedescendant", /.+/);
  await page.getByTestId("suggest-all").click();
  await expect(page).toHaveURL(/\/search\?q=denim/);
  await expect(page.getByTestId("product-card").first()).toBeVisible();

  await page.goto("/search?q=zzqxv");
  await expect(page.getByTestId("no-results")).toBeVisible();
});

test("PDP: size guide, store availability, complete the look and recently viewed", async ({ page, request }) => {
  const p = await inStockProduct(request);
  await page.goto(`/p/${p.id}`);
  await page.getByTestId("size-guide-link").click();
  await expect(page.getByTestId("size-guide")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("size-guide")).toHaveCount(0);

  await page.locator('[data-testid^="size-"][data-available="true"]').first().click();
  await page.getByTestId("check-stores").click();
  await expect(page.getByTestId("store-availability")).toBeVisible();
  await expect(page.getByTestId("avail-store").first()).toBeVisible();
  await page.keyboard.press("Escape");

  await expect(page.getByTestId("complete-the-look")).toBeVisible();
  await expect(page.getByTestId("recommended")).toBeVisible();
  await page.getByTestId("recommended").getByTestId("product-card").first().click();
  await expect(page.getByTestId("pdp-name")).toBeVisible();
  await expect(page.getByTestId("recently-viewed")).toContainText(p.name);
});

test("reviews: filter by stars, write a review, vote helpful", async ({ page, request }) => {
  const p = await inStockProduct(request);
  await page.goto(`/p/${p.id}#reviews`);
  const reviews = page.getByTestId("reviews");
  await expect(reviews.getByTestId("histogram")).toBeVisible();
  await expect(reviews.getByTestId("fit-summary")).toBeVisible();
  await reviews.getByTestId("review-sort").selectOption("recent");

  await reviews.getByTestId("write-review").click();
  await reviews.getByTestId("rate-5").click();
  await reviews.getByTestId("review-title").fill("Lovely weight");
  await reviews.getByTestId("review-body").fill("Soft fabric and it kept its shape after washing.");
  await reviews.getByTestId("review-fit").selectOption("True to size");
  await reviews.getByTestId("review-author").fill("Playwright");
  await reviews.getByTestId("review-submit").click();
  const mine = reviews.getByTestId("review").filter({ hasText: "Lovely weight" }).first();
  await expect(mine).toBeVisible();

  await reviews.getByTestId("histogram-5").click();
  await expect(reviews.getByTestId("review-count")).toContainText("5-star");
  const vote = reviews.getByTestId("review").filter({ hasText: "Lovely weight" }).first().getByTestId("helpful");
  await vote.click();
  await expect(vote).toBeDisabled();
});

test("back-in-stock alert for a sold-out size", async ({ page, request }) => {
  let target: { id: string; size: string; color: string } | null = null;
  for (const p of (await products(request)).filter((x) => x.stockState !== "SOLD_OUT").slice(0, 80)) {
    const d = await detail(request, p.id);
    const gone = d.skus.find((s) => s.stock === 0);
    if (gone) { target = { id: d.id, size: gone.size, color: gone.color }; break; }
  }
  test.skip(!target, "no sold-out size in the catalog");
  await page.goto(`/p/${target!.id}`);
  await page.getByTestId(`swatch-${target!.color}`).click();
  await page.getByTestId(`size-${target!.size}`).click();
  await expect(page.getByTestId("add-to-bag")).toHaveCount(0);
  await page.getByTestId("notify-email").fill("alerts@example.com");
  await page.getByTestId("notify-submit").click();
  await expect(page.getByTestId("notify-done")).toContainText("alerts@example.com");
});

test("guest favorites, PLP quick add, free-shipping bar and save for later", async ({ page }) => {
  await page.goto("/c/women");
  const card = page.getByTestId("product-card").filter({ hasNot: page.getByText("Sold out", { exact: true }) }).first();
  await card.getByTestId("favorite-button").click();
  await expect(page.getByTestId("favorites-count")).toHaveText("1");

  await card.hover();
  await card.getByTestId("quick-add").click();
  await page.getByTestId("quick-add-panel").getByTestId("quick-add-size").first().click();
  await expect(page.getByTestId("bag-count")).toHaveText("1");

  await page.goto("/favorites");
  await expect(page.getByTestId("favorites-grid").getByTestId("product-card")).toHaveCount(1);

  await page.goto("/bag");
  await expect(page.getByTestId("free-shipping")).toBeVisible();
  await page.getByTestId("save-for-later").click();
  await expect(page.getByTestId("saved-line")).toHaveCount(1);
  await expect(page.getByTestId("bag-count")).toHaveText("0");
  await page.getByTestId("move-to-bag").click();
  await expect(page.getByTestId("bag-line")).toHaveCount(1);
  await expect(page.getByTestId("saved-line")).toHaveCount(0);
});

test("order tracking timeline and starting a return", async ({ page }) => {
  const number = await guestOrder(page.request, "returns@example.com");
  await page.goto(`/order/${number}?email=returns@example.com`);
  await expect(page.getByTestId("order-timeline")).toBeVisible();
  await expect(page.getByTestId("step-PLACED")).toBeVisible();
  await page.getByTestId("start-return").click();
  await page.getByTestId("return-line-1").check();
  await page.getByTestId("return-reason-1").selectOption("Too small");
  await page.getByTestId("return-submit").click();
  await expect(page.getByTestId("return-number")).toHaveText(/^R/);
  await expect(page.getByTestId("return-refund")).toContainText("$");
});

test("gift card balance check", async ({ page }) => {
  await page.goto("/gift-cards");
  await page.getByTestId("gc-number").fill("6006 4912 3456 7890");
  await page.getByTestId("gc-pin").fill("1234");
  await page.getByTestId("gc-submit").click();
  await expect(page.getByTestId("gc-balance")).toHaveText("$50.00");
  await page.getByTestId("gc-pin").fill("9999");
  await page.getByTestId("gc-submit").click();
  await expect(page.getByTestId("gc-error")).toBeVisible();
});

test("member address book", async ({ page }) => {
  await signIn(page);
  const book = page.getByTestId("address-book");
  await book.getByTestId("add-address").click();
  await book.getByTestId("addr-label").fill("Studio");
  await book.getByTestId("addr-name").fill("Maya Otter");
  await book.getByTestId("addr-line1").fill("200 Larimer St");
  await book.getByTestId("addr-city").fill("Denver");
  await book.getByTestId("addr-state").fill("CO");
  await book.getByTestId("addr-zip").fill("80202");
  await book.getByTestId("save-address").click();
  const card = book.getByTestId("address-card").filter({ hasText: "200 Larimer St" });
  await expect(card).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await card.getByRole("button", { name: /delete|remove/i }).click();
  await expect(card).toHaveCount(0);
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("menu drawer, skip link and keyboard close", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    await page.getByTestId("mobile-menu-button").click();
    const nav = page.getByTestId("mobile-nav");
    await expect(nav).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(nav).toHaveCount(0);
    await expect(page.getByTestId("mobile-menu-button")).toBeFocused();
    await page.getByTestId("mobile-menu-button").click();
    await nav.getByTestId("mobile-dept-men").click();
    await nav.getByRole("link", { name: /^Shop all/ }).first().click();
    await expect(page.getByTestId("plp-title")).toHaveText("Men");
  });
});
