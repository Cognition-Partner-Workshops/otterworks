# Local lakehouse foundation

## Coverage and assumptions

```sh
make sfx-lakehouse-coverage NS=sfx-d1110-after
lakehouse/.venv/bin/python -m lakehouse.coverage check --strict
lakehouse/.venv/bin/python -m lakehouse.assumptions check
```

The non-strict coverage target validates both logs and renders
`evidence/COVERAGE.md` and `evidence/ASSUMPTIONS.md`. Pending work is expected;
strict mode fails until every pending object is resolved. Both validators also
run before pytest in `sfx-lakehouse-test`. No Spark or legacy connection is
needed for coverage validation: converted data objects require the latest saved
PASS evidence with a matching spec hash and a spec covering that object. Evidence
is scoped to the namespace/date recorded inside it, not refreshed by this target.
Non-data orchestration/configuration objects may instead cite
`verification: test:path/to/test_file.py::test_function` (or a class test node).
A path without an existing named test does not qualify.

`coverage/inventory.py` discovers logical objects from source, without running
legacy code. SQL names are uppercased; Informatica names are folder-qualified,
with workflow/worklet qualification for non-reusable nested tasks; Spark job-list,
Python/Scala implementation and deployment sources are merged under job names.
Repeated Informatica exports contribute source links, not duplicate objects.
Thus the repository's 40 mapping definitions represent 20 logical mappings, and
`jobs.txt` contains 30 jobs: 24 Python and 6 Scala (not 24 total). Disabled cron
entries, including `docs_folder_legacy_report`, are retained. Cron IDs use a
command hash rather than a source line number; daily-chain stages use stage names.

Beyond the requested minimum, discovery includes DBQL tables/views; reusable
Informatica source/target definitions, worklets, tasks and schedulers; shared Spark
libraries, submit wrappers and execution configuration; batch runners; partner
shell scripts; and ETL runtime configuration. Informatica parameter expressions,
XML execution CONFIG elements and connection default-database/code-page settings
carry behavior and are included; pure endpoint-only connection records are not.
Fixture generators, emulator implementation internals, tests, READMEs, build
metadata and generated landing/export data are not separate legacy business
processing objects. Their semantics are cited by assumptions where relevant.

When source objects are added, inventory changes automatically and the checker
fails until `coverage/coverage.yaml` receives an explicit entry. Only the account
output is converted; the surrounding BTEQ, staging schemas, Informatica mappings
and cron/orchestration remain pending. FastLoad/TPT controls are platform-replaced
by bronze ingestion, not certified against native vendor runtimes. Assumptions
cite legacy sources and distinguish accepted choices from open/unverified gaps.

## Runtime and pilot

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

## Legacy parity

The harness is read-only against legacy PostgreSQL; it does not invoke the BTEQ
runner or modify its metadata. Start legacy once, then use **its exact landing
files**, without regenerating feeds between the two loads:

```sh
make sfx-teradata-up NS=sfx-d1110-before ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109
make sfx-lakehouse-run NS=sfx-d1110-after SFX_LH_LANDING=warehouse/landing BUSINESS_DATE=20261109
make sfx-lakehouse-parity NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-lakehouse-test NS=sfx-d1110-after
```

`sfx-lakehouse-parity` compares already-built outputs; it deliberately does not
start, reseed or reload either side. `sfx-lakehouse-run` bootstraps the venv if
needed, so a separate lakehouse-up is unnecessary for this shared-input flow.
Legacy-up uses seed 1110 and writes `warehouse/landing/`; the lakehouse reads
that same directory directly. Keep the emulator running for subsequent tickets.
`LEGACY_NS` defaults to `sfx-d1110-before` and selects its deterministic local
port, independently of lakehouse NS. Explicit TD_PG_PORT or TD_PG_DSN overrides
that derivation. The reader uses the TD_PG_DSN/HOST/PORT/DB/USER/PASSWORD
precedence documented in `warehouse/README.md`. No credentials enter specs.

Direct invocation (export TD_PG_* connection settings as appropriate):

```sh
NS=sfx-d1110-after lakehouse/.venv/bin/python -m lakehouse.parity run \
  --spec billing.customer_account --business-date 20261109 --samples 10
```

Use `--all` instead of `--spec ID ...` for every spec. Failures, including read
errors, exit nonzero. Each selected spec overwrites its small report under
`evidence/parity/<id>.json`. `evidence/PARITY.md` rolls up all saved reports;
reports not selected in a run remain saved with their own namespace/date/time.
JSON records the raw spec SHA-256, code git SHA and dirty flag, namespaces,
business date, UTC timestamp, counts, diagnostics, samples and fingerprints.
These small artifacts are committed intentionally; never use sensitive data.

### Adding an object spec

Place one YAML file at `parity/specs/<domain>/<object>.yaml`. Required fields:
`id` (unique lowercase filename-safe ID), `legacy_objects` (stable coverage IDs,
e.g. `teradata_table:SFX_BILLING.CUSTOMER_ACCOUNT`), `legacy`, `lakehouse`, `keys`.
Keys/column names are lowercase; reader column names are matched case-insensitively.
Each side supports:

* `kind: postgres_sql`, `sql: SELECT ...` — PostgreSQL, read-only transaction.
* `kind: spark_sql`, `sql: SELECT ...` — namespace's configured Spark session.
* `kind: delta_table`, `table: silver_billing.customer_account`, or `path: ...`.
* `kind: file`, `path: ...`, `delimiter: '|'`, `header: false`,
  `columns: [id, amount]` — headerless PSV/CSV requires columns; headered files
  may infer names. Explicit names must match the header. Empty fields remain
  empty until normalization. An empty headerless file retains its schema.
* `kind: parquet`, `path: ...` — Spark Parquet file/directory reader.

Relative paths are repository-relative, independent of cwd. Paths substitute
`{business_date}` and `{NS}`; SQL substitutes `{business_date}`. Specs are trusted
repository code, not arbitrary user-supplied queries. Use side SQL for complex
source filters/column aliases.

Optional comparison fields:

```yaml
columns: [id, status, amount, day]  # omitted => every common column
normalize:
  '*': {trim: true}               # defaults; per-column settings override
  status: {rstrip: true, trim: false, case_fold: true, empty_as_null: true}
  amount: {numeric_scale: 2}      # Decimal, ROUND_HALF_UP
  day: {date_format: '%d/%m/%Y'}  # input strings => ISO date; native dates accepted
tolerance:
  amount: '0.01'                  # inclusive absolute numeric difference
filters:
  status: [active, pending]      # equality/IN on normalized values, both sides
```

`trim` strips surrounding whitespace; `rstrip` strips trailing ASCII spaces
only (CHAR padding). Trim takes precedence if both are true. Native dates and
numbers normalize to ISO strings and finite Decimal values; files needing
numeric semantics should specify numeric_scale. Normalization precedes filters,
key grouping, comparison and fingerprints. Keys must be included in columns.
Null keys and duplicate keys on either side fail; duplicate groups are reported
but not arbitrarily paired for cell comparisons. Missing/extra key counts and
per-column cell mismatch counts are exact, with deterministically ordered samples
capped by --samples. Pass requires equal filtered counts, no duplicate/null keys,
no missing/extra keys and no out-of-tolerance cells.

Per-column fingerprints include count, null count, numeric sum (when nonempty
values are numeric), and a SHA-256 of sorted, length-prefixed, type-tagged values.
They are order-independent diagnostics, not pass gates: tolerated numeric
differences can legitimately produce different sums/hashes. All comparisons and
hash sorting happen in driver Python memory; this is intended for demo sizes,
not production-scale parity. Full source rows, not just samples, are collected.

### Embedded Hive replacement compatibility

Delta 3.2.1 replacement previously caused Hive 2.3 to reject a metastore column
type update (`customer_id`), then Spark retried successfully in its own metadata
format. The session now sets
`spark.hadoop.hive.metastore.disallow.incompatible.col.type.changes=false` for
the per-namespace embedded metastore. Delta schema checks remain authoritative;
this removes the Hive-only compatibility rejection, not Delta data validation.
