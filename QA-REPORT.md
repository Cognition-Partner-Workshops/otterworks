# OtterShops QA report

Branch under test: `devin/1793667895-ottershops-features`. QA branch: `devin/1793670698-ottershops-qa` (adds tests and this report only; no production code changed).

Mode: find-only. Issues are reported, not fixed. Tests that fail on the current code are kept but marked `@Disabled("KNOWN FAILING QA-xx …")` (JUnit) or `test.fail(…)` (Playwright), so every suite is green on the code as found.

## Test pyramid

| Layer | Before | After | Notes |
|---|---|---|---|
| Backend unit (JUnit, order-service) | 36 run, 36 pass | 55 run, 53 pass, 2 known-failing (skipped) | New: `PricingQaTest` (8), `FeeCalculatorQaTest` (5), `ReturnServiceQaTest` (2, 1 skipped QA-05), `MockPaymentProviderQaTest` (4, 1 skipped QA-06) |
| Frontend unit (Vitest, new runner) | 0 (no runner) | 10 run, 10 pass | `vitest@3.2.4`, `npm test`; covers `format.ts`, `client.ts`, `states.ts` |
| Integration, real Postgres (Testcontainers) | 0 | 7 run, 6 pass, 1 known-failing (skipped) | `it/OrderServiceIntegrationTest`: Flyway V1-V4 on empty DB, checkout + stock decrement, decline/bad-Luhn leave stock alone, last-unit race (1×201, 3×409, stock 0), return + duplicate return 409, guest bag merge + whole-dollar rewards, unknown state (QA-01, skipped) |
| API contract (`scripts/ottershops/smoke.sh`) | 82 checks pass | 82 checks pass | unchanged |
| Data: loader + `dbt build` against Snowflake | 51/52 (unique `fct_orders.order_number` failed on shared RAW, QA-09) | 52/52 after truncating RAW.* and LOAD_STATE | Reconciliation: Postgres 9 orders / 45,290¢ total / 38,416¢ lines / 11 units = `FCT_ORDERS` 9 / 45,290¢ and `FCT_ORDER_LINES` + `SALES_DAILY` 38,416¢ / 11 units |
| Browser E2E (Playwright, Chromium) | 10 run, 10 pass | 15 run, 14 pass, 1 expected-fail (QA-02) | New `e2e/qa-edge.spec.ts`: empty bag, unknown + below-minimum promo, refresh persistence, invalid Luhn, mini-bag Escape, sold-out-in-bag (QA-02) |
| Exploratory browser + API probes | n/a | F1-F19 walked | Real Chrome over CDP and scripted API probes; screenshots for top issues |

Lint (`next lint`) and `tsc --noEmit` are clean. Backend total: 62 run, 0 failures, 3 skipped (QA-01, QA-05, QA-06).

Running the integration tests locally: Testcontainers 1.21 defaults to Docker API 1.32 and Docker 29 needs 1.40+, so set `api.version=1.44` in `~/.docker-java.properties`. Behind the Docker Hub rate limit use `TESTCONTAINERS_POSTGRES_IMAGE=mirror.gcr.io/library/postgres:16-alpine TESTCONTAINERS_RYUK_DISABLED=true`. Without Docker the class is skipped (`disabledWithoutDocker`).

## Flow coverage (docs/OTTERSHOPS-FLOWS.md)

| Flow | Covered by | Result |
|---|---|---|
| F1 Browse | smoke, Playwright checkout spec, exploratory | pass |
| F2 Guest purchase | Playwright, integration, smoke, exploratory | pass, but QA-01, QA-02 |
| F3 Declined payment | integration, unit, Playwright (bad Luhn), smoke | pass, QA-06 minor |
| F4 Signed-in pickup and rewards | integration (merge + points), API probes | pass, QA-03 |
| F5 Snowflake data | loader + dbt + reconciliation | totals reconcile; QA-07, QA-09, QA-10 |
| F6 Search with typeahead | Playwright features spec | pass |
| F7 Quick add and guest favorites | Playwright features spec, exploratory | pass |
| F8 Size guide, fit, outfit ideas | Playwright features spec | pass |
| F9 Store stock check | Playwright features spec, smoke | pass, QA-11 latent |
| F10 Back-in-stock alert | Playwright features spec | pass |
| F11 Reviews | Playwright features spec, API probes (duplicate vote, bad rating) | pass |
| F12 Bag progress and save for later | Playwright features spec, smoke | pass, QA-02 |
| F13 Favorites carry over at sign-in | exploratory (guest → member) | pass |
| F14 Address book | Playwright features spec | pass |
| F15 Order tracking | Playwright features spec, smoke | pass |
| F16 Start a return | Playwright, integration, smoke, API probes | pass, QA-05 |
| F17 Gift card balance | Playwright features spec, API probes | pass |
| F18 Help and policy pages | smoke, exploratory | pass |
| F19 Phone menu and keyboard use | Playwright mobile spec, mini-bag Escape | pass |

Edge cases checked: invalid Luhn, unknown and below-minimum promo, `PROMO_ENABLED=false` (list prices, `BLACKFRIDAY` → `PROMO_INVALID`), pickup-disabled store, five-way oversell race, sold-out sizes, empty states, mobile viewport, keyboard/Escape, refresh persistence, guest → member merge of bag and favorites.

## Issues

Line numbers are on `devin/1793667895-ottershops-features`.

| ID | Sev | Flow | Exact repro | Root cause | Suggested fix |
|---|---|---|---|---|---|
| QA-01 | Medium | F2 checkout / tax | `POST /api/checkout` with a ship-to address `state: "XX", zip: "00000"` and a valid card → **201**, order `shipTo.state = "XX"`, `taxRate = 5` (default). Order page shows "Nowhere, XX 00000". | `CheckoutService.java:166-170` (`validAddress`) only checks `[A-Z]{2}` (line 168); `FeeCalculator.taxRate` falls back to `DEFAULT_TAX_RATE` for unknown states. The real list (`AddressService.java:15`, used at :43) isn't used by checkout. | Validate `state` against `AddressService.STATES` in `validAddress` and return `STATE_INVALID` 400. Un-skip `OrderServiceIntegrationTest.checkoutRejectsUnknownState`. |
| QA-02 | High | F2 / F12 inventory | Bag A holds the last 2 units of a size; another shopper buys them. Open `/bag` in A: line shows **"Only 0 left"**, quantity stays 2, **Checkout** is enabled. Place order → "Some items in your bag sold out. Update your bag and try again." and the bag/summary still show the item; nothing tells the shopper which line or offers to fix it. | `frontend/client-app/src/app/bag/page.tsx:83` renders `Only {l.stock} left` for any `stock <= 5` incl. 0 and never compares `stock` to `quantity`; `:132` checkout link is unconditional. `checkout/page.tsx:80-83` shows the 409 message but doesn't refresh the bag. The 409 itself is correct (`CheckoutService.java:110`). | Flag lines with `stock < quantity` ("Sold out" / "Only N left, reduce quantity"), disable Checkout while any line is short, and call `refresh()` on a 409 in checkout. Remove `test.fail` from `qa-edge.spec.ts`. |
| QA-03 | Low | F4 pickup | `POST /api/checkout/quote` `{fulfillment: "PICKUP", storeId: "S005"}` (Mission Valley, pickup disabled) → **200** with a pickup quote; `POST /api/checkout` with the same store → 400 `PICKUP_UNAVAILABLE`. | `CheckoutService.java:66` (`quote`) loads the store without the `pickupEnabled()` check that `place` does at :95-97. | Apply the same check in `quote` (or have both call one helper). |
| QA-04 | Low | bag API | `POST /api/bags/{id}/items {"sku": …, "quantity": -5}` → 200 and the line has quantity 1. | `BagController.java:62-63` `Math.max(1, qty)` silently coerces. | Reject `quantity < 1` with 400 `QUANTITY_INVALID`. |
| QA-05 | Low | F16 returns | Order OS-100014: one line, qty 3, `lineTotalCents` 8413 (BLACKFRIDAY split leaves a remainder), CA 7.25%. Return 1 unit three times → 3 × 3007 = **9021¢**; the line was 8413 + 610 tax = 9023¢. Lines with remainder 2 over-refund instead (unit test: 1001¢ / 3 → 1002¢). | `ReturnService.java:42-46` rounds each partial refund `HALF_UP` independently; nothing tracks what has already been refunded for the line. | Refund the last remaining unit as `line total − already refunded`, or allocate with largest-remainder. Un-skip `ReturnServiceQaTest.partialReturnsNeverRefundMoreThanTheLineTotal`. |
| QA-06 | Low | F3 payment | `MockPaymentProvider.authorize` with `"4242abcd42424242"` → APPROVED (the letters are dropped, leaving a 12-digit number that passes Luhn). | `MockPaymentProvider.java:27, 50-52` strips every non-digit instead of only spaces/dashes. | Strip `[\s-]` only and reject anything else. Un-skip `MockPaymentProviderQaTest.numbersContainingLettersAreInvalid`. |
| QA-07 | Medium | F5 data | Place orders after 4 pm Pacific (00:00 UTC). Postgres `created_at` 2026-11-03 01:53 UTC = Nov 2 6:53 pm PT. `MARTS.FCT_ORDERS.order_date` = **2026-11-03**; `SALES_DAILY` books all 9 of tonight's orders on Nov 3. On Black Friday every order from 4 pm PT (7 pm ET) onward lands on Saturday. | `dbt/models/marts/fct_orders.sql:15` and `fct_order_lines.sql:8` use `to_date(o.created_at)` on a `timestamp_tz` that the loader writes in UTC; `sales_daily.sql:3,10` groups by that date. | `to_date(convert_timezone('America/Los_Angeles', o.created_at))` (or a `business_timezone` var) in both marts; same for `fct_returns.sql:9`. Add a dbt test with a late-evening fixture. |
| QA-08 | Medium | alerts | `curl :8080/actuator/prometheus` → 404. No ServiceMonitor is rendered and no alert rule references order-service, so a checkout outage (5xx, payment declines, 409 spike) pages nobody. | `services/order-service/src/main/resources/application.yml:34` exposes `health,info` only; no `micrometer-registry-prometheus` in `pom.xml`; `infrastructure/helm/order-service/values.yaml:36-38` `monitoring.enabled: false` ("exposes no Prometheus endpoint yet"). | Add `micrometer-registry-prometheus`, expose `prometheus`, set `monitoring.enabled: true` for the retail tenant, add a PrometheusRule (checkout 5xx rate, 409 rate, p95 latency). |
| QA-09 | Medium (ops) | F5 loader | With RAW already holding rows from another environment that also starts at OS-100001, `loader` + `dbt build` → `FAIL unique_fct_orders_order_number`, PASS=51 ERROR=1. Truncating RAW.* and RAW.LOAD_STATE and re-running → 52/52. | `loader/loader.py` appends to RAW with no source/environment column; order numbers are per-database sequences, so two stacks sharing `OTTERSHOPS.RAW` collide. Staging dedupes on `id`, not on source. | One Snowflake database (or schema) per environment, or add a `source_env` column to RAW and key staging on it. Document the truncate-and-reload recovery in `docs/OTTERSHOPS.md`. |
| QA-10 | Low (code review, not reproduced) | F5 loader | Two transactions: T1 writes `updated_at = t1`, T2 writes `t2 > t1` and commits first; a load between the commits moves `orders_wm` to `t2` and T1 is never loaded. | `loader.py:133-143` (same pattern at :59-64, :145-150): `updated_at > watermark` and watermark = last row's `updated_at`. | Re-read a small overlap window (`updated_at > wm - interval '5 minutes'`) and rely on staging dedupe. |
| QA-11 | Low (latent data) | F9 stores | `S019` Scottsdale, AZ has `41.6949, -105.9847` (Wyoming); `S005` San Diego has `46.3894, -82.7588` (Ontario). Nothing in the storefront reads lat/long today, but they ship to Snowflake `STORES`. | `db/migration/V2__catalog_seed.sql:6787, 6801` seed coordinates don't match the addresses. | Regenerate store coordinates from the ZIP centroids in a new migration (V5). |

## Top 5 planted-bug candidates

Ranked by how visible the issue is to a store or support person, how cleanly it reproduces, and how directly logs, code and data lead to the cause. One per area.

| Rank | ID | Area | Category | Why it makes a good ticket |
|---|---|---|---|---|
| 1 | QA-02 | Inventory | How-to or is-this-a-bug | Every shopper on Black Friday can hit it; screenshot-reproducible in two minutes; 409 is in the API log; cause is two lines in one component. |
| 2 | QA-07 | Data / Snowflake | Data fix | Merchandising notices the day's sales split across two dates; reproducible from the mart with one query; fix is a dbt change plus a backfill. |
| 3 | QA-01 | Checkout / pricing | How-to or is-this-a-bug | Tax and fulfilment teams see orders with state "XX" taxed at 5%; one curl reproduces it; the correct list already exists next door. |
| 4 | QA-08 | Alerts | Monitoring alert | After any checkout incident someone asks "why didn't we get paged"; the gap is visible in config (values, actuator, pom) and fixed by a small, reviewable change. |
| 5 | QA-05 | Account / returns | Data fix | Customer care sees refunds that don't add up to the receipt; reproducible with three returns; cause is one rounding function. |

Screenshots: `QA-02-bag-only-0-left.png`, `QA-02-checkout-409.png`, `QA-01-order-state-XX.png` (attached to the hand-off message, not committed).

### Ticket 1 (QA-02)

- **Short description:** Bag says "Only 0 left" and checkout fails with "Some items in your bag sold out"
- **Description (reporter):** Several customers on chat this morning. They had a top in their bag from last night, came back, and the bag page says "Only 0 left" under it but still lets them press Checkout. They fill in everything and get "Some items in your bag sold out. Update your bag and try again." The bag looks the same afterwards, so they don't know what to update, and a few tried three or four times. One customer sent a screenshot (attached). Is this a bug or are we supposed to tell them to remove the item?
- **Category:** How-to or is-this-a-bug
- **Impact:** 2 - Medium (lost orders for anyone whose bag contains a size that sold out; heavier on promo days)
- **Urgency:** 2 - Medium
- **Priority:** P3 - Moderate
- **CI / business service:** OtterShops Storefront (web) / Online Ordering
- **Assignment group:** OtterShops Digital Commerce - Web
- **Answer key:**
  - Root cause: the bag page only shows a low-stock hint (`stock <= 5`, including 0) and never compares stock with the quantity in the bag; Checkout is always enabled. When checkout gets the 409 `OUT_OF_STOCK` it shows the message but doesn't reload the bag.
  - Files: `frontend/client-app/src/app/bag/page.tsx:83, :132`; `frontend/client-app/src/app/checkout/page.tsx:80-83`. Server side is correct: `CheckoutService.java:110`, `BagService.java:71`.
  - Fix: mark lines where `stock < quantity` (sold out / reduce to N), disable Checkout while any line is short, refresh the bag after a 409.
  - Verification: remove `test.fail` from `e2e/qa-edge.spec.ts` "a line that sold out while in the bag is flagged before checkout" and run `npx playwright test e2e/qa-edge.spec.ts`; manually buy the last units from a second bag and reload the first.

### Ticket 2 (QA-07)

- **Short description:** Daily sales report puts last night's orders on today's date
- **Description (reporter):** The online sales by day numbers in Snowflake (SALES_DAILY) don't match what we saw on the site. Yesterday evening looks almost empty and today already shows sales from before most of us were awake. On Black Friday the Friday total came in low and Saturday high by about the same amount, which threw off the recap we sent to the regional managers. Can someone check whether the report date is right and correct the history?
- **Category:** Data fix
- **Impact:** 2 - Medium (daily and promo reporting wrong; finance and merchandising decisions use it)
- **Urgency:** 3 - Low
- **Priority:** P4 - Low (P3 in Black Friday week)
- **CI / business service:** OtterShops Data Platform (Snowflake OTTERSHOPS, dbt) / Sales Reporting
- **Assignment group:** Data Engineering - Retail Analytics
- **Answer key:**
  - Root cause: `order_date` is `to_date(created_at)` on a UTC `timestamp_tz`, so anything after 00:00 UTC (4 pm PT / 7 pm ET) is bucketed into the next calendar day.
  - Files: `data-platform/ottershops/dbt/models/marts/fct_orders.sql:15`, `fct_order_lines.sql:8`, `fct_returns.sql:9`; `sales_daily.sql:3,10` inherits it.
  - Fix: convert to the business time zone before `to_date` (e.g. `to_date(convert_timezone('America/Los_Angeles', o.created_at))`, ideally via a project var); `dbt build --full-refresh` the marts to restate history.
  - Verification: `select order_number, created_at, order_date from MARTS.FCT_ORDERS` for an order placed after 4 pm PT shows the Pacific date; `SALES_DAILY` totals per day match Postgres grouped by `(created_at at time zone 'America/Los_Angeles')::date`; all 52 dbt tests still pass.

### Ticket 3 (QA-01)

- **Short description:** Orders going through with state "XX" and odd tax
- **Description (reporter):** The fulfilment team flagged an order (OS-100016) shipping to "Nowhere, XX 00000". It was paid and is in Processing. Tax on it is 5%, which isn't a rate we charge anywhere, so I think there may be more. The address book on My Account won't let me save "XX", so I'm not sure how it got through checkout. Is this a bug, and what do we do with orders like this?
- **Category:** How-to or is-this-a-bug
- **Impact:** 3 - Low (few orders, but tax mis-collected and undeliverable shipments)
- **Urgency:** 2 - Medium
- **Priority:** P4 - Low
- **CI / business service:** OtterShops Order Service (order-service API) / Online Ordering
- **Assignment group:** OtterShops Digital Commerce - Order Services
- **Answer key:**
  - Root cause: checkout's address validation accepts any two letters; unknown states fall back to the 5% default tax rate. The address book validates against the real state list, checkout doesn't.
  - Files: `services/order-service/src/main/java/com/otterworks/ottershops/checkout/CheckoutService.java:166-170`; `account/AddressService.java:15, :43`; `pricing/FeeCalculator.java` (`taxRate` default).
  - Fix: reuse `AddressService.STATES` in `validAddress` and return 400 `STATE_INVALID`; find existing bad orders with `select order_number from orders where ship_state not in (…)`.
  - Verification: remove `@Disabled` from `OrderServiceIntegrationTest.checkoutRejectsUnknownState` and run `mvn test`; `curl` checkout with `"state":"XX"` returns 400.

### Ticket 4 (QA-08)

- **Short description:** No alert fired during the checkout errors; order service missing from monitoring
- **Description (reporter):** Stores called in between about 11:10 and 11:35 because customers said online checkout kept failing. Nobody was paged and the on-call dashboard has no panels or data for the OtterShops order service at all, only the other services. We need an alert that tells us when checkout is failing before the stores do.
- **Category:** Monitoring alert
- **Impact:** 2 - Medium (outages are detected by customers, not by us)
- **Urgency:** 2 - Medium
- **Priority:** P3 - Moderate
- **CI / business service:** OtterShops Order Service (order-service, tenant t-retail) / Monitoring and Alerting
- **Assignment group:** Platform SRE / Observability
- **Answer key:**
  - Root cause: order-service never exports metrics. Actuator exposes only `health,info`, there is no Prometheus registry dependency, and the Helm chart ships `monitoring.enabled: false`, so no ServiceMonitor scrapes it and no rule can fire.
  - Files: `services/order-service/src/main/resources/application.yml:34`; `services/order-service/pom.xml` (no `micrometer-registry-prometheus`); `infrastructure/helm/order-service/values.yaml:36-38`; `infrastructure/helm/order-service/templates/servicemonitor.yaml`.
  - Fix: add `io.micrometer:micrometer-registry-prometheus`, expose `health,info,prometheus`, enable monitoring in the retail tenant values, add a PrometheusRule for checkout 5xx rate, 409/402 rate and p95 latency on `/api/checkout`.
  - Verification: `curl :8080/actuator/prometheus` returns `http_server_requests_seconds_count{uri="/api/checkout"…}`; the scrape job shows UP in Prometheus; forcing 5xx (stop Postgres) fires the alert in Alertmanager.

### Ticket 5 (QA-05)

- **Short description:** Customer refunds for returned items don't add up to what they paid
- **Description (reporter):** A customer bought three of the same cardigan in one order and sent them back one at a time on separate returns. Each refund was $30.07, so $90.21 in total, but the receipt shows $84.13 for the three plus $6.10 tax, which is $90.23. She is asking for the 2 cents, and while checking I found another order where the refunds came out a cent more than was paid. Can someone look at how partial refunds are worked out and tell us how to correct these?
- **Category:** Data fix
- **Impact:** 3 - Low (cents per return, but refund and finance reconciliations don't tie out)
- **Urgency:** 3 - Low
- **Priority:** P4 - Low
- **CI / business service:** OtterShops Order Service (returns) / Returns and Refunds
- **Assignment group:** OtterShops Digital Commerce - Order Services
- **Answer key:**
  - Root cause: each partial return computes `lineTotal × qty / quantity` and its tax with `HALF_UP` independently, so the parts of a line whose total isn't divisible by its quantity round up or down every time and never sum to the line.
  - Files: `services/order-service/src/main/java/com/otterworks/ottershops/order/ReturnService.java:42-46` (`refund`); allocation that produces uneven line totals is `pricing/PricingService.java` (`applyCode`).
  - Fix: track cents already refunded per line and make the final unit's refund `line total + line tax − already refunded`, or allocate cents up front with largest-remainder; correct affected returns with a data fix on `returns.refund_cents`.
  - Verification: remove `@Disabled` from `ReturnServiceQaTest.partialReturnsNeverRefundMoreThanTheLineTotal`; reproduce with a 3-unit line under BLACKFRIDAY and three single-unit returns, the refunds sum to line + tax exactly.

## Not tested / limits

- Real-world brand/logo review and photo swaps: dropped by the scope change.
- Before/after clips and the stitched video: dropped by the scope change.
- The deployed t-retail tenant was not exercised (read-only reference, older code).
- QA-10 is from code review only; it wasn't reproduced because it needs two overlapping transactions timed around a loader run.
- Snowflake RAW.* and RAW.LOAD_STATE were truncated once to get a clean dbt run (allowed for this demo database).
