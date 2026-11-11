# Analytics Service

Scala 3 / Akka HTTP service that ingests platform events (via the REST API and
an SQS consumer) and serves aggregated analytics: dashboard summaries, per-user
activity, document stats, top content, active users, storage usage, and report
exports.

## Metrics store

Events and a daily aggregate rollup are persisted to a **durable PostgreSQL
store via Slick** — the golden-app default. The schema is applied with Flyway
from `src/main/resources/db/migration` (the same convention the JVM services in
this repo use):

- `analytics_events` — the raw event log (source of truth). The event instant is
  stored as epoch-nanoseconds (UTC) so it round-trips exactly regardless of DB
  timestamp precision or server time zone.
- `analytics_daily_metrics` — a materialized daily rollup (`event_date`,
  `event_type` → `event_count`) maintained transactionally on every write.

Query responses are derived from the durable event log via the pure,
storage-agnostic `MetricsAggregator`, which is shared with the in-memory backend
so both produce **byte-for-byte identical** results for the same event set.

### Backends

Selected by `analytics.repository.backend` (env `ANALYTICS_REPOSITORY_BACKEND`):

| value        | use                                                        |
|--------------|------------------------------------------------------------|
| `postgres`   | durable store (default; golden app)                        |
| `in-memory`  | ephemeral, process-local — for local runs and unit tests   |

The connection is assembled from `POSTGRES_*` (compose) unless `DATABASE_URL`
is provided explicitly (`scripts/deploy-dev.sh` wiring); `DATABASE_*` always
takes precedence. If the durable store cannot be initialised at startup, the
service logs a warning and falls back to the in-memory store so it still boots.

## Market data & margins (OTD-15)

The service also owns supply-chain market data and per-SKU margin analytics in a
dedicated **`analytics` schema** (its own Flyway history table
`flyway_schema_history_analytics`): `market_series`, `market_prices`, `products`,
`product_margin_daily`, `sync_runs`.

At startup an idempotent seeder loads the deterministic synthetic baseline
bundled from `testdata/market-series` (see the README there for the CSV
contract) and extends every series to "today" with a seeded random walk.

Endpoints (all behind the API-gateway JWT — no extra auth):

- `GET /api/v1/analytics/margins` — KPIs + per-SKU margin rows
- `GET /api/v1/analytics/margins/series?sku=|category=&from=&to=`
- `GET /api/v1/analytics/margins/export?format=csv`
- `GET /api/v1/analytics/market/series` / `market/prices?series_code=&from=&to=` / `market/status`
- `POST /api/v1/analytics/market/observations` — manual Trading Economics pulls:

```json
{
  "observations": [
    { "series_code": "SALMON_NOK_KG", "price_date": "2026-07-24", "value": 103.10 },
    { "series_code": "USD_NOK", "price_date": "2026-07-24", "value": 10.62 }
  ],
  "source_note": "tradingeconomics.com manual pull"
}
```

Each observation is validated (known series, ISO date not in the future,
positive value); valid ones upsert as `manual_pull` (winning over synthetic),
affected margins are recomputed synchronously and a `sync_runs` row is recorded.
Response reports `accepted`, itemized `rejected`, `recomputed_skus` and
`run_id`; an all-invalid request returns 400. There is **no** Trading Economics
API integration and no TE credentials — pulls are manual by design.

## Lakehouse migration — "before" state

This durable PostgreSQL store is the **"before"** state for a
REFACTOR / RE-ARCHITECT exercise that moves the analytics store to an
**S3 + Apache Iceberg lakehouse**. It is intentionally shaped so that migration
is a self-contained, verifiable step; the "after" is **not** built here.

### Target ("after") — outline only

- **Storage:** raw events land in S3 (partitioned by `event_date` /
  `event_type`) as an **Apache Iceberg** table; the daily rollup becomes an
  Iceberg aggregate table.
- **Catalog + query:** **AWS Glue Data Catalog** for table metadata and
  schema evolution; **Amazon Athena** (and/or Spark) for SQL over Iceberg.
- **Ingestion:** the existing SQS consumer writes to Iceberg (directly or via a
  streaming/compaction job) instead of `INSERT`-ing into PostgreSQL.
- **Serving:** the HTTP API and `DashboardSummary` semantics stay **identical**;
  only the repository implementation behind `MetricsRepository` changes.

### Continuous validation (reconciliation)

The migration is de-risked by a reconciliation check that asserts the
**old (PostgreSQL) and new (Iceberg) stores agree** for the same event set:

1. Seed / replay a fixed event set into both stores.
2. Compare every analytics response (`DashboardSummary`, `getUserActivity`,
   `getDocumentStats`, `getTopContent`, `getActiveUsers`, `getStorageUsage`,
   `getExportData`, event counts) field-for-field.
3. Cross-check the persisted daily rollup against counts derived from the raw
   event log.

The baseline for (2)–(3) already exists as
`src/test/scala/com/otterworks/analytics/repository/PostgresMetricsRepositorySpec.scala`,
which proves the durable PostgreSQL store reconciles exactly with the in-memory
store. The lakehouse "after" is expected to pass the **same** reconciliation
against this PostgreSQL "before", turning a one-off migration into a
continuously-validated cutover.

## Build & test

```bash
sbt compile        # compile
sbt test           # unit tests + durable-store reconciliation (Testcontainers)
sbt assembly       # fat jar (used by the Docker image / deploy)
```

The reconciliation suite uses Testcontainers and requires Docker; when Docker is
unavailable it is cancelled (not failed), so Docker-less runners stay green.

## Finance warehouse consumer

This consumer is operated as a separate repository owned by
**@otterworks/analytics**, using TDPROD / SFX_BILLING account `svc_analytics_dash`.
It requests trailing twelve calendar months, including the current month, on
demand and caches successful results for 15 minutes per filter pair.

`GET /api/v1/analytics/finance/rollups?status=&plan=` returns monthly billed
revenue, collected cash and active-account counts by region and plan name.
Filters select subscription STATUS_CD and PLAN_CODE. Omitted parameters use
the dashboard configuration in teradata.conf. Invalid empty/oversized filters
return 400; warehouse failures return a sanitized 503.
Set FINANCE_WAREHOUSE_ENABLED=false or finance.warehouse.enabled=false to
disable the route. It defaults on, without connecting at startup.

Tables and columns in SFX_BILLING:
- CUSTOMER_ACCOUNT: CUSTOMER_ID, REGION_CD, STATUS_CD, CREATED_DT.
- SUBSCRIPTION: SUBSCRIPTION_ID, CUSTOMER_ID, STATUS_CD, PLAN_CODE.
- PLAN_CATALOG: PLAN_CODE, PLAN_NAME.
- INVOICE_HDR: INVOICE_ID, SUBSCRIPTION_ID, CUSTOMER_ID, INVOICE_DT, SUBTOTAL_AMOUNT.
- PAYMENT: INVOICE_ID, CUSTOMER_ID, PAYMENT_DT, AMOUNT.

Revenue uses invoice subtotals for the selected subscriptions, excluding tax.
Cash is grouped independently by payment month, attributed through each
payment's invoice to its subscription. Both are aggregated before joining the
month/account grid. Accounts are deduplicated within each plan; active counts
use current account status ACTIVE and a creation date before the month's end.
Historical status changes are unavailable. Matching accounts with no activity
return zero amounts. No FX conversion is performed; totals assume a common
reporting currency. Seeded multi-currency aggregates are mechanical control totals.
The account's DBQL inventory also reads invoice revenue from this billing estate.

SQL retains SEL, TOP 12, ZEROIFNULL, ADD_MONTHS, CURRENT_DATE integer date
arithmetic, EXTRACT and FORMAT casts. The runtime driver is
com.teradata.jdbc.TeraDriver. Fake connection defaults live beside the DAL in
`src/main/resources/com/otterworks/analytics/finance/teradata.conf`.

### Checks
From this directory with Java 17 and sbt:
```sh
sbt compile test
WAREHOUSE_CONTRACT_TARGET=replay sbt "contract:test"
```
The separate contract configuration is excluded from test. CI additionally runs
the replay contract without credentials or a warehouse.

For live execution, seed the emulator and install the shared Python bridge
dependencies as documented in ../../consumers/contract-kit/README.md:
```sh
export TD_PG_PORT=54902
export CONTRACT_KIT_PYTHON=/path/to/contract-venv/bin/python
sbt "contract:test"
CONTRACT_RECORD=true sbt "contract:test"
```
The default target teradata-emulator executes the actual DAL SQL through the
shared bridge. Its runtime defaults to this repository's warehouse/teradata;
TD_EMULATOR_HOME overrides the repository root for a separate worktree.
CONTRACT_KIT_BRIDGE optionally overrides the bridge script path.
The contract client substitutes escaped SQL string literals for the two
parameters before invoking the bridge; production continues to use JDBC binds.
CONTRACT_RECORD=true saves live output under contract/recorded/teradata/ while
still checking expected row counts and sums. Review expected files after any
intentional data or query change. The fixture was captured from the emulator
seeded with ROWS_PER_TABLE=800 and BUSINESS_DATE=20261109.

WAREHOUSE_CONTRACT_TARGET accepts teradata-emulator, replay,
snowflake-semantics and snowflake. Replay reads recorded JSON locally without
Python or a database. The Snowflake placeholder requires SNOWFLAKE_ACCOUNT,
USER, ROLE, WAREHOUSE and PRIVATE_KEY; missing values cancel the spec, while a
configured placeholder raises an explicit unsupported-operation error.
Destination: SFX_D1110_AFTER.COMPAT; session QUERY_TAG:
`{"run":"sfx-d1110","act":"consumers","consumer":"analytics-service"}`.

Without local sbt, unit/replay commands can use:
```sh
docker run --rm -v "$PWD":/w -v "$HOME/.ivy2":/root/.ivy2 \
  -v "$HOME/.sbt":/root/.sbt -v "$HOME/.cache/coursier":/root/.cache/coursier \
  -w /w sbtscala/scala-sbt:eclipse-temurin-17.0.21_9_1.13.1_3.3.9 sbt compile test
```
Live container runs additionally need Python with the bridge dependencies,
the whole repository mounted at a stable path, and access to the emulator port.

### Databricks cutover (run dbx-d1111)

`DatabricksFinanceRollupRepository` (in `DatabricksReadPath.scala`) is a native
Databricks SQL rewrite of the Teradata query, read from `cpw.dbx_d1111_after`
(`billing__customer_account`, `billing__subscription`, `billing__plan_catalog`,
`billing__invoice_hdr`, `billing__payment`). `FINANCE_WAREHOUSE_TARGET=databricks`
selects it at startup (default stays Teradata). Teradata behaviour preserved:
- NOT CASESPECIFIC CHAR/VARCHAR equality (`STATUS_CD = ?`, `PLAN_CODE = ?`, the
  plan-catalog join and `STATUS_CD = 'ACTIVE'`) becomes `upper(rtrim(a)) = upper(rtrim(b))`;
  Databricks compares strings exactly and keeps CHAR pads (`'ACTIVE      '`, `'TEAM  '`, `'team'`).
- CURRENT_DATE month arithmetic becomes `trunc(as_of, 'MM')` with a bound as-of date
  (production: today in UTC); `TOP 12` months become `explode(sequence(0, 11))`;
  `ZEROIFNULL` becomes `coalesce(..., 0)`; `FORMAT 'YYYY-MM'` becomes `date_format`.
No compatibility view is used: the fix depends on this consumer's bound filters,
and the base tables are shared with other readers.

Live contract (secrets only in the environment; skipped with a clear cancel when absent):
```sh
make -C ../.. sfx-teradata-up NS=dbx-d1111-consumers-analytics-service ROWS_PER_TABLE=800
export TD_PG_PORT=55326 CONTRACT_KIT_PYTHON=../../warehouse/.venv/bin/python
python scripts/emulator_baseline.py seed   # emulator inputs := cpw.dbx_d1111_before, then count+hash check
WAREHOUSE_CONTRACT_TARGET=databricks CONTRACT_OLDPATH=emulator CONTRACT_STEP=contract-fixed sbt "contract:test"
```
The Databricks target runs the repository read logic with the dashboard filters,
pins the as-of date to `CONTRACT_AS_OF` (default 2026-11-09 = BUSINESS_DATE) on both
paths, checks `row_count` from `contract/expected` and requires row-for-row equality
with the Teradata read path on the same data: live through the emulator
(`CONTRACT_OLDPATH=emulator`) or `contract/recorded/dbx-d1111-baseline/finance-rollups.json`
(recorded from the baseline-seeded emulator). The expected sums describe the
800-row emulator seed, not the live baseline, so they are checked only by the
emulator and replay targets.
