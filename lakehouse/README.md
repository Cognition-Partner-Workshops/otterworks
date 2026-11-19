# Local lakehouse foundation

Java 17 and Python 3.10–3.12 are required. No services, credentials or Docker
are needed. Run from the repository root:

```sh
make sfx-lakehouse-up NS=sfx-d1110-after ROWS_PER_TABLE=2000
make sfx-lakehouse-run NS=sfx-d1110-after
make sfx-lakehouse-test NS=sfx-d1110-after
make sfx-lakehouse-down NS=sfx-d1110-after
```

`NS` is mandatory. Defaults match the legacy fixture: `BUSINESS_DATE=20261109`,
`ROWS_PER_TABLE=200000`, seed 1110. Landing files are generated into the
namespace, not the legacy landing directory. All mutable warehouse state,
including the embedded Hive metastore, lives under `.data/<NS>/`. One writer
process per namespace is supported (Derby locks its metastore).

`runtime.session.create_session()` configures local PySpark 3.5.3, Delta 3.2.1,
UTC and ANSI casts. Delta jars download on first use; the Maven Central Google
mirror is the default additional repository (override with
`LAKEHOUSE_MAVEN_REPOSITORY`). The ordinary Maven endpoint returned HTTP 429
on the development machine. Dependencies are installed in `.venv/`.

## Layout and ingestion

Every combination of bronze/silver/gold and billing/documents/users/audit has
a Spark database `<layer>_<domain>` located at
`.data/<NS>/delta/<layer>/<domain>`. Tables use lowercase names. Layout creation
does not imply that a domain's transformations have been migrated.

```sh
NS=sfx-d1110-after SPARK_LOCAL_IP=127.0.0.1 lakehouse/.venv/bin/python \
  -m lakehouse.runtime.ingest --landing lakehouse/.data/sfx-d1110-after/landing \
  --business-date 20261109 --tables CUSTOMER_ACCOUNT PLAN_CATALOG
```

Column order and source types come directly from `warehouse.seed.columns`.
All source columns are stored as strings. Exactly empty non-character values
become null; empty character values remain empty, and whitespace is preserved,
matching `bteq/load.py`. Python CSV parsing preserves its quoted pipe/newline
semantics. Wrong field counts and missing files fail explicitly. An empty file
clears that date's partition. Delta `replaceWhere` replaces only the requested
date, without deleting historical partitions. Metadata is `_business_date`
(date), `_source_file` (absolute string), `_ingested_at` (timestamp).
Atomicity is per table/date, not across the whole ingest run. The local ingest
currently buffers one file in driver memory, as a foundation rather than a
distributed file-loader implementation.

## dbt pilot and semantic assumptions

`python -m lakehouse.runtime.dbt` is the supported dbt entry point (set NS and
BUSINESS_DATE). It initializes the shared Spark session before invoking dbt's
session adapter in-process. The checked-in profile contains no secrets.
The schema macro uses the exact configured `<layer>_<domain>` schema.

* `01_load_accounts.bteq` deletes **all** customer accounts and inserts the
  current staging snapshot, without joins, deduplication or enrichment. The
  pilot is a full table materialization selecting just `BUSINESS_DATE` from
  retained bronze history. It does not union historical snapshots or use an
  incremental merge. Rebuilding an older date intentionally restores that
  date's snapshot. A missing/empty snapshot produces an empty silver table,
  consistent with empty staging.
* BIGINT and DATE are native Spark types. Spark CTAS represents CHAR/VARCHAR
  results as STRING rather than retaining SQL length/collation metadata.
  `legacy_text` explicitly reproduces lengths and fixed-width padding. The
  emulator's `Runner.translate` wraps INSERT SELECT text values in explicit
  PostgreSQL casts, so overflow is **truncated**, not rejected. This differs
  from assumptions one might make about a native Teradata load.
* The legacy NOT CASESPECIFIC collation, LATIN/UNICODE character set flags,
  compression, physical unique primary index and NOT NULL constraint are not
  native Delta equivalents here. dbt unique/not_null tests validate the key
  after materialization; they are not transactional insert constraints. Spark
  string comparisons remain case-sensitive. No pilot transformation compares
  these strings, but future models must address collation explicitly.
* Bronze null handling follows the runnable PostgreSQL loader, not a claim
  about native FastLoad/TPT defaults. Type conversion is deferred to silver.
  ANSI casts reject invalid numeric/date text, but PostgreSQL and Spark can
  accept different noncanonical date/numeric spellings; fixture inputs are
  canonical. Source staging character widths (200) are not enforced in bronze.
* The BTEQ script also loads PLAN_CATALOG, TAX_RATE, GL_ACCOUNT and
  GL_JOURNAL_LINE. They are ingested into bronze but deliberately have no
  silver models in this step. BTEQ logon/error labels and multi-statement
  partial-failure behavior are not ported.

Tests use an isolated disposable namespace, exercising layout, quoted/empty
fields, malformed and missing input, date-specific replacement, retained
history, empty snapshots, pilot types/padding/truncation and cast failures.
The Make run additionally executes real dbt model and key tests.
