# Snowflake scaffold

## Processed Teradata billing handoff

To land invoiced before-state outputs without implementing legacy invoice logic
in Snowflake, first run the emulator, then replace only the three billing outputs:

```sh
make sfx-teradata-run NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-snowflake-deploy
make sfx-snowflake-load-before NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-snowflake-dbt
```

The additive `load.py --source teradata-before --area billing --date 20261109`
mode exports processed SFX_BILLING.INVOICE_HDR, INVOICE_LINE and GL_JOURNAL_LINE
using the separate Teradata interpreter (`--teradata-python`). Headered,
pipe-delimited gzip files remain under ignored warehouse/landing/.teradata-before.
All exports must be nonempty and match the RAW contract before connecting to
Snowflake. This mode atomically DELETEs and COPYs exactly those three tables with
explicit date filenames and FORCE=TRUE, replacing rather than appending. Other RAW data stays
on the shared seed. Fixture and seed loading, including seed-derived journals,
are unchanged. Journal IDs and fixture column aliases are naming adapters;
invoice amounts and journal debits/credits come unchanged from the emulator.

V004 codifies the consumer views using only V001–V003 columns; governance tags
are applied after the tag exists in V006. V008 is the idempotent live upgrade:
applied V004 edits are logged as checksum drift and skipped by schemachange 4.0.1.
COMPAT.CREDIT_NOTE mirrors the Teradata credit shape plus ISSUE_DATE;
COMPAT.V_INVOICE_REVENUE mirrors its currency/month revenue view, with
COMPAT.INVOICE_REVENUE retained as an alias. Currency grouping preserves case
and trims trailing CHAR padding, matching the emulator revenue view. V009 applies
that fidelity correction to an already-applied initial V008 without rewriting
history; V008 itself also contains the final definition for fresh deployments.
Deploy governance reapply covers every COMPAT view.

Invoice due dates preserve actual DUE_DATE first, otherwise use customer
PAYMENT_TERMS_DAYS with INVOICE_DATE/INVOICE_DT, and use **net 30 only as the final
fallback** when customer terms are absent. The current processed emulator has no
due-date column and the shared seed supplies no terms, so its rows use that
approved final fallback. Credit ISSUE_DATE falls back to CREDIT_DT. The same
date rules apply in dbt staging. No invoice-run procedure is translated here.

Use Python 3.10. Snowflake targets install into warehouse/snowflake/.venv,
separate from Teradata's warehouse/.venv; SFX_VENV overrides that location.
Supply SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE,
SNOWFLAKE_DATABASE, SNOWFLAKE_PRIVATE_KEY (unencrypted PEM text), and
SNOWFLAKE_RUN_TOKEN through environment injection. Never put credentials in files.
The database is SFX_D1110_AFTER; workloads.yml selects the warehouse.

```sh
make sfx-snowflake-test
SFX_EXECUTED_BY=devin make sfx-snowflake-deploy
SFX_EXECUTED_BY=devin make sfx-snowflake-load
warehouse/snowflake/.venv/bin/python warehouse/snowflake/sfx_conn.py
```

For an existing alternate Python environment, run
make sfx-snowflake-test SFX_TEST_PYTHON=/path/to/python3.11.

Deploy uses schemachange 4's Python API with an in-memory JWT session (no key
file). Its history table is bootstrapped with a run-token comment. Versioned
migrations run once; tasks are created suspended. Do not resume tasks unless
scheduled loading is wanted. All sessions receive compact JSON query tags;
SFX_COMMIT, SFX_RUN_ID, SFX_EXECUTED_BY and SFX_BUILT_WITH override defaults.
The same query_tag() value can be passed to schemachange's --query-tag, but its
stock CLI prefixes the value; deploy.py keeps the session tag as exact JSON.
Scheduled task tags use a stable run_id of "scheduled" to avoid checksum drift
between otherwise identical deployments.

```sh
warehouse/snowflake/.venv/bin/python warehouse/snowflake/fixtures/make_fixture.py --rows 20 --seed 1110
warehouse/snowflake/.venv/bin/python warehouse/snowflake/load.py --area billing --date 20261101
warehouse/snowflake/.venv/bin/python warehouse/snowflake/load.py --area all --landing-dir warehouse/snowflake/fixtures/landing
```

The default source is the committed headered fixture, whose frozen V002 contract
is fixture_columns.yml. PUT preserves filenames and COPY
history skips already loaded files; use new date filenames for new batches.
A date limits COPY to that file; without a date all staged files are considered.
Metadata columns record source filename and scan timestamp. The fixture uses
matching integer IDs across related entities. GL postings summarize the invoice
run and settled receipts separately by currency. SOURCE_BATCH_NUMBER identifies
the fixture batch; each currency has invoice and receipt journals. Reconcile them
to invoice subtotal/tax/total and payment amounts in the same currency, rather
than joining a summary ledger line to an individual customer or invoice.
No legacy transformations run here.

## Shared seeded RAW data

```sh
python3 warehouse/seed/generate.py --rows 200000 --seed 1110
warehouse/snowflake/.venv/bin/python warehouse/snowflake/deploy.py
warehouse/snowflake/.venv/bin/python warehouse/snowflake/load.py --source seed --area all --date 20261109 --truncate
warehouse/snowflake/.venv/bin/python warehouse/snowflake/run_dbt.py build
warehouse/snowflake/.venv/bin/python warehouse/snowflake/sfx_conn.py
```

The shared generator writes headerless PSV under warehouse/landing/<area>/<TABLE>/.
The seed loader validates every input and produces headered gzip files under
ignored warehouse/landing/.snowflake before connecting. It keeps all rows and
values, including reserved-key edge cases, mixed-case codes and duplicate SET
rows; it does not emulate Teradata truncation, collation or deduplication.
APP_USER.DISPLAY_NAME is VARCHAR(256) to preserve the generator's overlength names.
Uploads use a stable area/table/date seed stage prefix and COPY selects only that
date's filename. Reruns preserve the staged file and COPY history, so they are
no-ops; use --truncate to replace a date's staged data and RAW rows.
The --truncate flag retains its name but uses transactional DELETE, never TRUNCATE.
All selected tables are replaced in one BEGIN/COMMIT; COPY exceptions, unsuccessful
statuses, reported errors or row-count mismatches trigger ROLLBACK for the whole
batch. Uploads and local validation precede BEGIN, and the transaction contains no
DDL or session changes. Replacement COPYs use FORCE=TRUE to reload existing files
despite retained COPY history. Fixture --truncate uses this same helper with explicit
date files; non-replacement fixture procedure loading is unchanged. Each committed
output row reports area, table, COPY rows and COUNT(*).
Without --truncate, existing RAW rows are not removed. --landing-dir overrides
the input directory; --source seed requires --date. No generated files are committed.

landing_columns.yml is the additive superset of both formats. V007 adds the seed
columns and only widens existing types where necessary. V001–V003 and V005–V007
remain unchanged; V004 codifies the initial COMPAT contract in place, with live
replacements supplied by V008/V009 rather than replaying the applied V004.
tools/render_seed.py renders V007/the superset; render_raw.py remains bound to the
frozen fixture/V002 contract. V012 restores RAW_BILLING.USAGE_DAILY.CURRENCY_CODE to
CHAR(3) after the nightly drift sweep found it widened to VARCHAR(10) outside the
migration history. Snowflake cannot narrow a column in place, so V012 rebuilds it
through a temporary column; the table, its COPY history and Time Travel are kept,
and CURRENCY_CODE becomes the last column (every load here maps by name). V012 is a
no-op when the column is already three characters wide and refuses to run while any
row holds a longer value: such rows come from an out-of-contract load and must be
removed or replayed first. Each DDL statement autocommits, so V012 inspects the
column layout first and a rerun resumes from wherever an interrupted run stopped. dbt exposes both column sets and tests the shared
primary/foreign keys, using legacy fixture IDs as fallbacks. Legacy-only fields
absent from shared RAW seed data remain NULL; the approved COMPAT/staging date
fallbacks above are explicit exceptions at projection time. Catalog, chart and
tax records have no customer association in the shared seed, so customer FK tests
apply only to tables whose actual seed contract includes CUSTOMER_ID.

The shared generator supplies GL_ACCOUNT but currently writes an empty
GL_JOURNAL_LINE. The seed loader supplements only that empty journal using scaled
fixture postings from the actual seeded invoices, payments and credit notes:
invoice DR AR / CR revenue / CR sales tax, payment DR cash / CR AR, credit-note
DR revenue / CR AR. It uses the seed chart IDs and invoice currencies, validates
each journal's decimal balance, and retains INVOICE_ID/CREDIT_NOTE_ID provenance.
This is fixture construction, not converted legacy accounting logic.

## Compatibility reads

COMPAT views expose CUSTOMER (account columns plus owner name/email), ACCOUNT
(CUSTOMER_ACCOUNT), INVOICE (INVOICE_HDR), INVOICE_LINE, PAYMENT, GL_JOURNAL_LINE
and DAILY_USAGE (customer/date/currency rollup). V007 adds the shared Teradata
column names while retaining the original aliases and adds GL_ACCOUNT,
CUSTOMER_ACCOUNT and INVOICE_HDR views. Quantity comes from seeded UNITS;
DAILY_USAGE.AMOUNT remains NULL when the source has no amount. These are plain
projections, joins and aggregates, not Teradata-semantics emulation.

Tag consumer SELECT sessions with JSON containing run=sfx-d1110, act=consumers,
and consumer=<service-name>. Additional run_id/executed_by/built_with fields allow
cycle attribution. Use consumer_reads.py --run sfx-d1110 --hours 24 or
make sfx-snowflake-consumers. The report merges ACCOUNT_USAGE with visible recent
history by query ID, reports observed counts and marks unlanded usage pending.
Missing consumers are reported as no reads yet, not proof of zero activity.
Objects read are best-effort COMPAT names parsed from query text. ledger.py
accepts either run_token or run tags; consumer-only tags without workload/phase
appear under unknown attribution dimensions.

## Placeholder task graph

Run make sfx-snowflake-dag or task_dag.py --run-once [--timeout 180]. The runner
sets graph config and task query tags from the cycle environment, resumes only
children, manually executes the suspended root, polls TASK_HISTORY, prints log
rows, and suspends/verifies every DAG task even on failure. The root cron is
never enabled. task_dag.yml maps the log-only steps to the billing workflow names
found on origin/devin/sfx-d1110-informatica; it does not implement their mappings.
tools/render_dag.py regenerates V005 from the map. ORCH.RUN_STEP only logs; the
decision accepts the fixed CONTINUE result from D. No converted logic runs.

## Procedure and SET-table targets

Deploy recursively discovers versioned migrations and repeatable SQL under the
Snowflake root. Put converted procedures in procedures/R__<schema>__<proc>.sql;
include the run token in each created object's COMMENT. No converted procedure
is supplied by this scaffold; the directory is intentionally empty.

Converted dbt models with a Teradata SET source can call
set_table_semantics('source_cte', 'model_key'). Supply set_table_decisions as a
dbt var mapping that model key to distinct or keep_all. Missing or invalid
decisions fail compilation. No decisions are recorded by the scaffold.

## Operational commands

```sh
make sfx-snowflake-roles-dry-run
make sfx-snowflake-ledger
make sfx-snowflake-up NS=sfx-d1110
make sfx-snowflake-run NS=sfx-d1110
make sfx-snowflake-down NS=sfx-d1110
make sfx-snowflake-teardown TEARDOWN_ARGS=--dry-run
```

up deploys; run loads, builds billing staging and reports credits; down suspends
tagged tasks and warehouses without dropping objects. For NS=sfx-d1110-before,
these three lifecycle targets are no-ops. The test target always runs.

roles/dry_run.py validates and prints the ordered SQL plan. --check-live inspects
SHOW GRANTS without applying DDL. --apply refuses unless CREATE ROLE is held.
Analysts retain database and transform-warehouse USAGE, with schema USAGE and
SELECT on current/future tables and views only in MART, MART_SPARK and COMPAT.
The role plan first revokes existing and future analyst database/schema/table/view
privileges before restoring that allowlist, so upgrades remove legacy broad grants.
Deploy V010 before applying the role plan; it provisions the Spark landing and mart
schemas. The loader writes SPARK_RAW_*; the transformer reads those sources and
retains table/view creation and table writes in MART and MART_SPARK.
After an administrator provisions the functional roles, run
`python warehouse/snowflake/roles/verify.py --apply` with the injected credentials.
It applies only V010 and the scoped grants as SFX_D1110_ROLE, disables secondary
roles, then tests analyst reads/denials and transformer writes using tagged scratch
objects. It prints query IDs and drops its scratch objects. Omit `--apply` to check
the already-deployed plan. Snowflake permits session-local temporary tables with
USAGE alone; this plan prevents persistent DDL and writes to published data, not
session-local scratch creation.
Validation rejects analyst write grants, inherited functional roles, and access
to RAW_*, LANDING or SCHEMACHANGE.

ledger.py --token sfx-d1110 --days 14 [--json] allocates warehouse-hour compute
credits using tagged execution time divided by all queries' execution time in
that hour. Query cloud-services credits are added directly. Missing metering or
recent activity absent from ACCOUNT_USAGE marks cells pending; it does not imply
zero credits. Recent history is limited to 3h and 10000 visible queries, and
ACCOUNT_USAGE can lag up to about 3h. This is attribution, not a billing invoice.

**sfx-snowflake-teardown performs real cleanup by default.** Use
TEARDOWN_ARGS=--dry-run to preview. It preserves the provisioned role, user,
database, warehouses and resource monitor unless --include-provisioned is
explicitly passed. That flag can remove the active service identity and database.
Cleanup suspends before dropping. Database and account-level object names must
start with SFX_D1110_ (or the scoped token prefix); comment-only matches remain
in the inventory and affect the exit code but are never modified. Schema-local
comment matches may be removed only inside a name-scoped database. Eligible
schemas/databases are dropped with CASCADE, including their contents. Discovery is
limited to objects visible to the current role; explicit permission failures are
reported and cause a nonzero exit. Remaining non-exempt objects also cause a
nonzero exit, including in dry-run mode. No real teardown is needed for normal
pause/resume use.

## Governance after replacement

V010 provisions `SPARK_RAW_BILLING`, `SPARK_RAW_DOCUMENTS`, `SPARK_RAW_USERS`,
`SPARK_RAW_AUDIT` and `MART_SPARK` before any Spark landing or migrated job runs.
V011 creates database roles `SFX_D1110_AFTER.SFX_D1110_TRANSFORMER` and
`SFX_D1110_AFTER.SFX_D1110_ANALYST`, and grants them to `SFX_D1110_ROLE`.
The database owner can apply both migrations without account-level role admin.
V010 creates the five Spark schemas WITH MANAGED ACCESS so their owner can grant
future privileges without the account-level MANAGE GRANTS privilege. Creating
them managed initially avoids ALTER SCHEMA ENABLE MANAGED ACCESS, which itself
requires account-level MANAGE GRANTS. Existing standard schemas require a
requester-managed conversion or a backed-up managed schema clone before V011.
Table owners leave grant decisions to the schema owner.
The transformer database role reads only the four Spark raw schemas, creates
tables, views and functions only in `MART_SPARK`, and applies only
`GOVERNANCE.SFX_RUN`. The analyst database role has only `MART_SPARK` schema
USAGE and SELECT on existing/future output tables and views.

For the separate account-role deployment, requester action is required: have a
role administrator apply `roles/01_roles.sql` through `roles/06_spark_grants.sql`
using `roles/dry_run.py --apply`. This additionally sets up the account-level
loader, parity and Snowpark roles and their warehouse access. The database-role
deployment inherits warehouse access from `SFX_D1110_ROLE`; database roles cannot
hold warehouse privileges or be activated with USE ROLE.

The loader only creates
and refreshes tables in the provisioned landing schemas; it needs no database
CREATE SCHEMA privilege. Transformer and Snowpark roles read the landing tables
and create tables, views and Python functions in `MART_SPARK`. Parity and analyst
roles receive read access on existing and future output tables and views.

`GOVERNANCE.SFX_RUN` always stores the fixed run identifier `sfx-d1110`, matching
V006's allowed value. A scoped `SNOWFLAKE_RUN_TOKEN` remains in query attribution
and object comments. Both the dbt hook and the Snowpark runner restore this tag
after publishing; their roles receive APPLY on this single tag. Snowpark table
replacements must use `copy_grants=True` to preserve explicit consumer grants.
Spark dbt tables likewise have `+copy_grants: true` so full refreshes retain
explicit grants as well as the schema's future grants.

Deploy V006 before running dbt. `deploy.py` restores `GOVERNANCE.SFX_RUN='sfx-d1110'`
and token comments on the V003/V005 tasks and procedures after every deployment,
including no-op deployments. The dbt `on-run-end` hook calls `reapply_governance`
for successful model/seed/snapshot relations; ephemeral, failed and skipped nodes
are excluded. To restore metadata independently, use `dbt run-operation
reapply_governance --project-dir warehouse/dbt --profiles-dir warehouse/dbt`
with the same secret-safe profile environment as `run_dbt.py`.

`governance_policies` defaults to `{}`. Optional entries are keyed by dbt model
name, with `masking: [{column: EMAIL, policy: DB.GOVERNANCE.EMAIL_MASK}]`,
`row_access: {policy: DB.GOVERNANCE.TENANT_FILTER, columns: [CUSTOMER_ID]}` and
`column_tags: {EMAIL: {DB.GOVERNANCE.SFX_RUN: sfx-d1110}}`. Policy and tag names
must be fully qualified; these objects must already exist. No policies are
created. Masking associations are restored with FORCE. An identical row-access
association is retained; a different existing policy fails rather than silently
removing its protection. Missing relations are skipped by the independent
operation. Session QUERY_TAG format is unchanged.

Connections use TIMEZONE=UTC; ledger timestamps and comparisons are UTC, including
Pacific-offset ACCOUNT_USAGE values returned by a cursor. Credits remain pending
until query and metering freshness have caught up with recent tagged activity.

Teardown also inventories tags, integrations, applications, compute pools and
account-wide services, matching names or comments. Privilege failures are reported
as `not visible to role`, not as an empty account. Compute pools are suspended
before dropping. After dropping a token user, a second sweep removes its renamed
`DROPPED_USER$<original_username>_<timestamp>` database. Unattributed dropped-user
databases are listed but never removed without a token or an established link to
a dropped token user. The GOVERNANCE schema is included in cleanup.

## SnowConvert CLI

Install the SnowConvert AI CLI (`scai`) using the same public installer as the
PowerCenter builder (PR #2654); it is not available on PyPI:

```sh
curl -fsSL https://snowconvert.snowflake.com/storage/linux/prod/cli/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
scai --version
make sfx-snowflake-snowconvert
```

The user-local installer verifies its archive checksum and bundles the runtime;
no license, login, Java change or separate runtime installation was needed for
stable CLI 2.52.5 on this VM. The wrapper looks for SQL,
BTEQ and BTQ files under `warehouse/teradata/`, and PowerCenter XML under
`etl/informatica/` (the path on `origin/devin/sfx-d1110-informatica`). It does not
fetch or check out sibling builders automatically. With no input it reports the
searched locations. A missing CLI fails with installation guidance before any
credential files are written.

At runtime only, when the CLI and inputs exist, the wrapper merges a connection
named `sfx_d1110` into `~/.snowflake/connections.toml` using the SNOWFLAKE_*
environment bindings. It preserves other connections, writes the injected PEM to
`~/.snowflake/sfx_d1110.p8`, and uses JWT key-pair authentication exclusively. The
directory is mode 700 and both files are mode 600, created under a restrictive
umask; symlink destinations are refused. These credential files are outside the
repository. `scai` receives `SNOWFLAKE_CONNECTION=sfx_d1110`, not the credential
bindings. Key-pair rejection stops the run; no password fallback is attempted.

The wrapper creates separate Teradata and Informatica projects with
`scai init <project> -l Teradata -c sfx_d1110`, adds staged inputs, and runs
`scai code convert --show-ewis` in each project. Teradata DDL, macros, procedures
and `dbql/schema.sql` (the DBC schema used by `dbql/consumer_reads.bteq`)
are split into individual statements using the builder's parser, then added with
`--code-already-split`; BTEQ/BTQ scripts are copied unchanged. PostgreSQL emulator
bootstrap SQL is excluded. Informatica uses the self-contained `wf_*.XML` exports
when present, as the PowerCenter builder does, avoiding duplicate standalone
mapping imports; XML is added without the split flag. No source files are edited.
`inputs.json` lists the original inputs and `summary.json` records commands,
working directories and exit codes. Original
stdout/stderr, the tool project/output and a short `summary.json` remain under
`warehouse/snowconvert/raw/<UTC timestamp>/`, which is gitignored. Nothing is
deployed, edited into the target scaffold, or committed. Output containing private
key material is refused rather than redacted and persisted.

Offline CI runs `make sfx-snowflake-test SFX_PYTHON=python` on Python 3.10 and 3.11,
with dummy dbt credentials and no network connection to Snowflake.
