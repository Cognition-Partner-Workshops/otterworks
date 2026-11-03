# OtterShops retail demo

OtterShops is a fictional family apparel store built on the `demo-retail` branch. It is the base site for the Devin on-call demo. ServiceNow, New Relic and seeded tickets come later. All brands, products, stores and people are invented. Product photos are from Unsplash and credited in `frontend/client-app/IMAGE_CREDITS.md`.

## What runs

| Component | Path | Role |
|---|---|---|
| Storefront | `frontend/client-app` | Next.js App Router site on port 3000. Browser calls go to its own `/api/*`, which proxies to the order service (`ORDER_SERVICE_URL`). |
| Order service | `services/order-service` | Spring Boot 3.5 / Java 21. Catalog, search suggestions, bags and saved-for-later, promotions, pricing, fees, mock payments, checkout, orders with tracking and returns, accounts and address books, stores and store stock, reviews, favorites, back-in-stock alerts, gift card balances. Flyway migrations seed the catalog. |
| Postgres | compose `postgres` | Transactional store. Checkout locks SKU rows, decrements stock and rejects oversells with 409. |
| Loader | `data-platform/ottershops` | Every 5 minutes copies new and changed rows from Postgres to Snowflake `RAW`, then runs `dbt build`. |
| Snowflake | `OTTERSHOPS` database | `RAW` → `STAGING` (views) → `MARTS` (tables). Warehouse `OTTERSHOPS_WH` (X-Small, 60 s auto-suspend) under resource monitor `OTTERSHOPS_RM` (10 credits a month). |

## Run it locally

```bash
docker compose -f docker-compose.ottershops.yml up --build
open http://localhost:3000
```

If Maven Central rate-limits the build, set `MAVEN_MIRROR_URL=https://maven-central.storage-download.googleapis.com/maven2/`.
If Docker Hub rate-limits base image pulls, set `OTTERSHOPS_REGISTRY=mirror.gcr.io/library/`.

The loader stays idle unless `OTTERSHOPS_SNOWFLAKE_KEY_FILE` points at the private key of the `OTTERSHOPS_SVC` Snowflake user. Keys are never committed. To create the Snowflake objects and that user, generate an RSA key pair and run `data-platform/ottershops/snowflake/bootstrap.py <public-key>` with an admin PAT (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_ADMIN_USER`, `SNOWFLAKE_PAT`).

Set `PROMO_ENABLED=false` on the order service to switch Black Friday off without a rebuild. The banner, hero, countdown, strikethrough prices and codes all disappear on the next page load.

## Demo data

- 192 products and 3,413 color/size SKUs across Women, Men, Kids, Baby, Maternity, Denim and Activewear. Some SKUs are low stock (5 or fewer) and some are sold out.
- 22 stores. A few have pickup turned off.
- Demo shopper: `maya@ottershops.test` / `otters-2026`.
- Promo codes: `BLACKFRIDAY` (extra 15% off sale-eligible styles) and `OTTERWELCOME` (10% off orders of $75 or more).
- Gift cards: `6006 4912 3456 7890` PIN `1234` ($50.00), `6006 4955 5544 4433` PIN `4321` ($125.75), `6006 4900 0000 0000` PIN `0000` ($0).
- Test cards: `4242 4242 4242 4242` approves, `4000 0000 0000 0002` is declined (HTTP 402). Cards that fail the Luhn check are rejected (HTTP 400). Any future expiry and 3-digit CVC.

Regenerate the catalog with `python3 tools/catalog/generate.py`. It is deterministic and rewrites `V2__catalog_seed.sql`.

## Pricing rules

- Black Friday takes 40% off list price, except the excluded collections (`maternity`, `gift-cards`, `essentials-forever`), which stay at full price. A product's markdown price wins when it is lower.
- Codes apply after the sale and are spread across eligible lines.
- Standard shipping is $7.99 and free from $50 after discounts. Express is $19.99. Pickup is free.
- Colorado deliveries add the $0.29 retail delivery fee. California pickups add a $0.10 bag fee.
- Tax applies to merchandise plus shipping, at the destination state's rate or the store's state for pickup (5% where no rate is listed).
- Members earn 1 rewards point per whole dollar of merchandise after discounts (shipping, fees, tax and gift cards don't earn). Every balance change is written to `rewards_ledger`.

## Snowflake marts

| Mart | Grain |
|---|---|
| `fct_orders` | one row per order, with totals in dollars and cents |
| `fct_order_lines` | one row per order line, with department and savings |
| `dim_products` | one row per product, with current stock, sold-out and low-stock SKU counts |
| `dim_customers` | one row per member, with order count and lifetime value (no password data) |
| `inventory_daily` | one row per SKU per day: closing stock and units sold |
| `sales_daily` | one row per day per department: orders, units, list and net sales |
| `fct_returns` | one row per returned order line, with reason, method, refund and days after the order |
| `product_engagement` | one row per product: written reviews, fit votes, helpful votes, favorites, pending back-in-stock alerts, units sold and returned, top return reason |

The loader also copies reviews (no text or names), returns and their lines, favorites and back-in-stock requests (no email addresses). `dbt build` runs 52 models and tests, including key uniqueness, relationships, order totals that balance, no negative stock, and returns that never exceed the quantity or amount bought.

## Deploy (t-retail)

The `demo-retail` branch is the store's tenant: pushing it runs `.github/workflows/cd-tenant.yml`, which builds the services the push changed (`order-service`, `web-app`), tags them `tenant-retail`, and has the ops dashboard run `scripts/deploy-tenant.sh retail` from the branch.

- `infrastructure/helm/tenant-values/retail/services` lists what the tenant runs: `web-app` and `order-service` only. Any other OtterWorks release left in the namespace is uninstalled on deploy. Redis and MeiliSearch still come up with every tenant.
- `infrastructure/helm/tenant-values/retail/web-app.yaml` points the storefront at `http://order-service:8080`. Add an `order-service.yaml` next to it for per-tenant settings, for example `config: { PROMO_ENABLED: "true" }`.
- order-service uses the tenant database `otterworks_retail` through PgBouncer. Flyway runs on the session port and records its versions in `order_service_schema_history`.
- `order-service` exists only on this branch, so it has no `:main` image. A tenant without a `tenant-retail` build of it fails the deploy. To rebuild everything, run the workflow on `demo-retail` with `rebuild_all`.
- Redeploy after changes: commit on top of the branch and push `demo-retail`. Then check with `demo-platform/scripts/tenant.sh status retail` and run `scripts/ottershops/smoke.sh https://t-retail.demo.otterworks.app`.
- The Snowflake loader does not run in the cluster. Run it locally (see above).

## Checks

```bash
(cd services/order-service && mvn test)                          # unit tests
(cd frontend/client-app && npm run lint && npm run typecheck && npm run build)
scripts/ottershops/smoke.sh http://localhost:3000                # 82 API checks through the storefront proxy
(cd frontend/client-app && npx playwright test)                  # 10 browser specs: checkout plus every phase-2 flow
```

## Store features

Phase 2 added typeahead search with a no-results page, quick add and favorites on the product grid, a size guide and fit summary, complete-the-look and recommendation rows, recently viewed, a store stock check, back-in-stock alerts, reviews with a star histogram, sort, filters, writing and helpful votes, a free-shipping bar and save for later in the bag, an address book, order tracking, self-service returns, a gift card balance check, help and policy pages, a phone menu and keyboard support. `docs/OTTERSHOPS-RESEARCH.md` lists the retail patterns behind each feature.

Store stock and tracking milestones are demo data. Each store's count for a size is derived from the SKU and store id, so it stays the same between visits, and tracking steps advance with the age of the order.

## User flows

`docs/OTTERSHOPS-FLOWS.md` maps every flow (F1 to F19) with a diagram, steps and expected results.
