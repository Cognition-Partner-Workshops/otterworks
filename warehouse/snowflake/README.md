# Snowflake scaffold

Use Python 3.10. Supply SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE,
SNOWFLAKE_DATABASE, SNOWFLAKE_PRIVATE_KEY (unencrypted PEM text), and
SNOWFLAKE_RUN_TOKEN through environment injection. Never put credentials in files.
The database is SFX_D1110_AFTER; workloads.yml selects the warehouse.

```sh
make sfx-snowflake-test
SFX_EXECUTED_BY=devin make sfx-snowflake-deploy
SFX_EXECUTED_BY=devin make sfx-snowflake-load
warehouse/.venv/bin/python warehouse/snowflake/sfx_conn.py
```

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
warehouse/.venv/bin/python warehouse/snowflake/fixtures/make_fixture.py --rows 20 --seed 1110
warehouse/.venv/bin/python warehouse/snowflake/tools/render_raw.py
warehouse/.venv/bin/python warehouse/snowflake/load.py --area billing --date 20261101
warehouse/.venv/bin/python warehouse/snowflake/load.py --area all --landing-dir warehouse/snowflake/fixtures/landing
```

Landing paths are warehouse/landing/<area>/<TABLE>/<yyyymmdd>.psv, with a
pipe-delimited header in landing_columns.yml order. If warehouse/landing does
not exist, load.py uses the committed fixture. PUT preserves filenames and COPY
history skips already loaded files; use new date filenames for new batches.
A date limits COPY to that file; without a date all staged files are considered.
Metadata columns record source filename and scan timestamp. The fixture uses
matching integer IDs across related entities. GL postings summarize the invoice
run and settled receipts separately by currency. SOURCE_BATCH_NUMBER identifies
the fixture batch; each currency has invoice and receipt journals. Reconcile them
to invoice subtotal/tax/total and payment amounts in the same currency, rather
than joining a summary ledger line to an individual customer or invoice.
Reconcile the column contract
when warehouse/seed/generate.py arrives. No legacy transformations run here.

## Compatibility reads

COMPAT views expose CUSTOMER (account columns plus owner name/email), ACCOUNT
(CUSTOMER_ACCOUNT), INVOICE (INVOICE_HDR), INVOICE_LINE, PAYMENT, GL_JOURNAL_LINE
and DAILY_USAGE (customer/date/currency quantity and amount sums). Columns mirror
landing_columns.yml, excluding load metadata. No Teradata builder branch was
available at implementation time. Reconcile COMPAT names and shapes with the
SFX_BILLING Teradata DDL when it lands; these are projections, not an emulation
of Teradata semantics.

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
Cleanup suspends before dropping; token-matched schemas/databases are dropped
with CASCADE, including their contents. It also removes token-matched
non-provisioned roles, users, warehouses and resource monitors. Discovery is
limited to objects visible to the current role; explicit permission failures are
reported and cause a nonzero exit. Remaining non-exempt objects also cause a
nonzero exit, including in dry-run mode. No real teardown is needed for normal
pause/resume use.

## Governance after replacement

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

Install the SnowConvert AI CLI (`scai`) from Snowflake's distribution; it is not
available on PyPI. Run `make sfx-snowflake-snowconvert`. The wrapper looks for SQL,
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

The wrapper runs `scai init <project> -l Teradata`, `scai code add -i <input>` for
each input root, then `scai code convert`. XML is detected by the CLI. Original
stdout/stderr, the tool project/output and a short `summary.json` remain under
`warehouse/snowconvert/raw/<UTC timestamp>/`, which is gitignored. Nothing is
deployed, edited into the target scaffold, or committed. Output containing private
key material is refused rather than redacted and persisted.

Offline CI runs `make sfx-snowflake-test SFX_PYTHON=python` on Python 3.10 and 3.11,
with dummy dbt credentials and no network connection to Snowflake.
