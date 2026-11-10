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
**@otterworks/analytics**, using TDPROD / FIN_DW account `svc_analytics_dash`.
The dashboard requests trailing twelve calendar months (including the current
month) on demand and caches successful results for 15 minutes per filter pair.

`GET /api/v1/analytics/finance/rollups?region=&plan=` returns monthly billed
revenue, collected cash and active-account counts by region and plan.
Omitted filters use the configured dashboard defaults. Invalid empty/oversized
filters return 400; warehouse failures return a sanitized 503.
Set `FINANCE_WAREHOUSE_ENABLED=false` or `finance.warehouse.enabled=false`
to disable the route. It defaults on, without connecting at startup.

The DAL reads FIN_DW.CUSTOMER (CUSTOMER_ID, REGION_CODE), ACCOUNT
(ACCOUNT_ID, CUSTOMER_ID, PLAN_NAME, STATUS_CD, OPENED_DT), INVOICE
(ACCOUNT_ID, INVOICE_DT, AMOUNT_DUE, TAX_AMT) and PAYMENT
(ACCOUNT_ID, PAYMENT_DT, AMOUNT). Billed revenue excludes tax; cash is grouped by
payment month independently of invoices. Active accounts use current status A
and an opened date before the month's end; historical status changes are not
available in this model. Months with matching accounts but no activity return
zero amounts. No FX conversion is performed.

Connection defaults are fake and live alongside the DAL in
`src/main/resources/com/otterworks/analytics/finance/teradata.conf`.
The runtime driver is `com.teradata.jdbc.TeraDriver`.

```sh
sbt compile test
sbt "contract:test"
```

The separate contract configuration is excluded from `test`. Its default
`WAREHOUSE_CONTRACT_TARGET=teradata-emulator` replays the synthetic recorded
result in `contract/recorded/teradata/finance-rollups.json` and checks non-zero
row count and aggregates against `contract/expected/finance-rollups.json`.
Setting TD_EMULATOR_URL selects an explicit stub raising
"emulator endpoint not configured" until the endpoint protocol is available.
The adapter receives the DAL's SQL constant and dashboard filters.

For `WAREHOUSE_CONTRACT_TARGET=snowflake`, the placeholder reads
SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and
SNOWFLAKE_PRIVATE_KEY. Missing values cancel the spec; a configured adapter
currently raises an explicit unsupported-operation error pending implementation.
Its target is SFX_D1110_AFTER.COMPAT, with session QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"analytics-service"}`.

Without local sbt, run each command through Docker (Java 17), for example:
```sh
docker run --rm -v "$PWD":/w -v "$HOME/.ivy2":/root/.ivy2 \
  -v "$HOME/.sbt":/root/.sbt -v "$HOME/.cache/coursier":/root/.cache/coursier \
  -w /w sbtscala/scala-sbt:eclipse-temurin-17.0.21_9_1.13.1_3.3.9 sbt compile test
```
