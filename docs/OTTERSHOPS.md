# OtterShops retail demo

OtterShops is a fictional family apparel store built on the `demo-retail` branch. It is the base site for the Devin on-call demo. ServiceNow, New Relic and seeded tickets come later. All brands, products, stores and people are invented. Product photos are from Unsplash and credited in `frontend/client-app/IMAGE_CREDITS.md`.

## What runs

| Component | Path | Role |
|---|---|---|
| Storefront | `frontend/client-app` | Next.js App Router site on port 3000. Browser calls go to its own `/api/*`, which proxies to the order service (`ORDER_SERVICE_URL`). |
| Order service | `services/order-service` | Spring Boot 3.5 / Java 21. Catalog, bags, promotions, pricing, fees, mock payments, checkout, orders, accounts, stores. Flyway migrations seed the catalog. |
| Postgres | compose `postgres` | Transactional store. Checkout locks SKU rows, decrements stock and rejects oversells with 409. |
| Loader | `data-platform/ottershops` | Every 5 minutes copies new and changed rows from Postgres to Snowflake `RAW`, then runs `dbt build`. |
| Snowflake | `OTTERSHOPS` database | `RAW` → `STAGING` (views) → `MARTS` (tables). Warehouse `OTTERSHOPS_WH` (X-Small, 60 s auto-suspend) under resource monitor `OTTERSHOPS_RM` (10 credits a month). |

## Run it locally

```bash
docker compose -f docker-compose.ottershops.yml up --build
open http://localhost:3000
```

If Maven Central rate-limits the build, set `MAVEN_MIRROR_URL=https://maven-central.storage-download.googleapis.com/maven2/`.

The loader stays idle unless `OTTERSHOPS_SNOWFLAKE_KEY_FILE` points at the private key of the `OTTERSHOPS_SVC` Snowflake user. Keys are never committed. To create the Snowflake objects and that user, generate an RSA key pair and run `data-platform/ottershops/snowflake/bootstrap.py <public-key>` with an admin PAT (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_ADMIN_USER`, `SNOWFLAKE_PAT`).

Set `PROMO_ENABLED=false` on the order service to switch Black Friday off without a rebuild. The banner, hero, countdown, strikethrough prices and codes all disappear on the next page load.

## Demo data

- 192 products and 3,413 color/size SKUs across Women, Men, Kids, Baby, Maternity, Denim and Activewear. Some SKUs are low stock (5 or fewer) and some are sold out.
- 22 stores. A few have pickup turned off.
- Demo shopper: `maya@ottershops.test` / `otters-2026`.
- Promo codes: `BLACKFRIDAY` (extra 15% off sale-eligible styles) and `OTTERWELCOME` (10% off orders of $75 or more).
- Test cards: `4242 4242 4242 4242` approves, `4000 0000 0000 0002` is declined (HTTP 402). Cards that fail the Luhn check are rejected (HTTP 400). Any future expiry and 3-digit CVC.

Regenerate the catalog with `python3 tools/catalog/generate.py`. It is deterministic and rewrites `V2__catalog_seed.sql`.

## Pricing rules

- Black Friday takes 40% off list price, except the excluded collections (`maternity`, `gift-cards`, `essentials-forever`), which stay at full price. A product's markdown price wins when it is lower.
- Codes apply after the sale and are spread across eligible lines.
- Standard shipping is $7.99 and free from $50 after discounts. Express is $19.99. Pickup is free.
- Colorado deliveries add the $0.29 retail delivery fee. California pickups add a $0.10 bag fee.
- Tax applies to merchandise plus shipping, at the destination state's rate or the store's state for pickup (5% where no rate is listed).
- Members earn 1 rewards point per whole dollar of the order total.

## Snowflake marts

| Mart | Grain |
|---|---|
| `fct_orders` | one row per order, with totals in dollars and cents |
| `fct_order_lines` | one row per order line, with department and savings |
| `dim_products` | one row per product, with current stock, sold-out and low-stock SKU counts |
| `dim_customers` | one row per member, with order count and lifetime value (no password data) |
| `inventory_daily` | one row per SKU per day: closing stock and units sold |
| `sales_daily` | one row per day per department: orders, units, list and net sales |

`dbt build` runs 35 models and tests, including key uniqueness, relationships, order totals that balance, and no negative stock.

## Checks

```bash
(cd services/order-service && mvn test)                          # unit tests
(cd frontend/client-app && npm run lint && npm run typecheck && npm run build)
scripts/ottershops/smoke.sh http://localhost:3000                # 38 API checks through the storefront proxy
(cd frontend/client-app && npx playwright test)                  # guest checkout in a browser
```

## User flows

1. Browse: home with the Black Friday hero and countdown → Women menu → filter by size and color, sort → product page.
2. Guest purchase: pick color and size → Add to Bag → mini-bag → bag → apply `BLACKFRIDAY` → ship to California with the 4242 card → confirmation `OS-1xxxxx` → order lookup.
3. Declined payment: the 0002 card shows a clear decline. No order is created and stock is unchanged.
4. Member pickup: sign in as the demo shopper → the guest bag merges → pick up at a store → the order and points show on the account.
5. Data: orders from flows 2 and 4 reach the Snowflake marts within 10 minutes.
