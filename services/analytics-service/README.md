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

The finance rollup route reads Snowflake using JWT key-pair authentication.
Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE and
SNOWFLAKE_PRIVATE_KEY (PKCS8 PEM). Sessions use SFX_D1110_AFTER and only
SFX_D1110_PARITY_WH, with QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"analytics-service"}`.

Customer, invoice and payment reads use COMPAT views. Subscription and plan
catalog reads use CORE_BILLING staging models because COMPAT has no equivalents.
Invoice/payment customer attribution uses each invoice/payment's CUSTOMER_ID.
Native calendar truncation, month formatting and COALESCE replace Teradata
date arithmetic, FORMAT and ZEROIFNULL. Successful results remain cached for
15 minutes per filter pair. Defaults are in snowflake.conf.
Shared UPPER(RTRIM(...)) comparisons preserve Teradata NOT CASESPECIFIC CHAR
semantics for subscription filters, the plan-code join and active-account status:
case and trailing pad spaces do not affect matching.

`GET /api/v1/analytics/finance/rollups?status=&plan=` returns monthly billed
revenue, collected cash and active-account counts by region and plan name for
the trailing twelve calendar months, including the current month.
Filters select subscription STATUS_CD and PLAN_CODE. Omitted parameters use
the dashboard configuration in snowflake.conf. Empty or oversized filters
return 400; warehouse failures return a sanitized 503.
Set FINANCE_WAREHOUSE_ENABLED=false or finance.warehouse.enabled=false to
disable the route. It defaults on, without connecting at startup.

Revenue uses invoice subtotals for the selected subscriptions, excluding tax.
Cash is grouped independently by payment month, attributed through each
payment's invoice to its subscription. Both are aggregated before joining the
month/account grid. Accounts are deduplicated within each plan; active counts
use current account status ACTIVE and a creation date before the month's end.
Historical status changes are unavailable. Matching accounts with no activity
return zero amounts. No FX conversion is performed; totals assume a common
reporting currency. Seeded multi-currency aggregates are mechanical control totals.

### Checks

```sh
sbt compile test
WAREHOUSE_CONTRACT_TARGET=replay sbt "contract:test"
WAREHOUSE_CONTRACT_TARGET=snowflake sbt "contract:test"
```

Missing Snowflake credentials cancel the live test. It executes the production
repository SQL and prints query IDs. The live contract compares columns, month
labels and plan names to replay. Counts and monetary totals intentionally are
not compared: the live seed has 200,000 rows per table versus 800 in replay.

The legacy reference query is contract-only. Emulator runs always use
TD_USER=svc_exit_parity. Supply TD_PG_PORT and CONTRACT_KIT_PYTHON as described
in ../../consumers/contract-kit/README.md. Targets teradata-emulator and
snowflake-semantics remain available. Replay needs neither Python nor a DB.
The separate case-comparison spec always probes snowflake-semantics: without
a local emulator it cancels; in CI it bootstraps an isolated 800-row emulator
via contract/start-emulator.sh. Its namespace defaults to
sfx-d1110-analytics-ci (override ANALYTICS_CONTRACT_NS).
The fixture was captured with ROWS_PER_TABLE=800 and BUSINESS_DATE=20261109.
CONTRACT_RECORD=true records live emulator output under
contract/recorded/teradata/ while still checking expected row counts and sums:

```sh
WAREHOUSE_CONTRACT_TARGET=teradata-emulator CONTRACT_RECORD=true sbt "contract:test"
```

Review expected files after any intentional data or query change.
