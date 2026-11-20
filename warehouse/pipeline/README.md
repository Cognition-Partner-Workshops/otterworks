# __RUN_TOKEN__ daily billing feed

## Local DuckDB replay

From the repository root (no Snowflake credentials needed):

```sh
eval "$(python3 warehouse/run_config.py env)"
uv run --with duckdb==1.4.2 --with tomlkit --with PyYAML python warehouse/pipeline/load_daily.py --target duckdb --no-build --date 2026-11-09
uv run --with tomlkit --with PyYAML python warehouse/pipeline/schema_drift.py --column CUSTOMER_ID
uv run --with duckdb==1.4.2 --with tomlkit --with PyYAML python warehouse/pipeline/load_daily.py --target duckdb --no-build --date 2026-11-10
```

The ignored database defaults to `migration/dw-exit/.runs/nightly.duckdb`;
override with `--db-path`. DuckDB requires `--no-build`: no dbt or downstream
checks are simulated. Operational load events still go to `pipeline.jsonl`.
The drift generator can alternatively use `--column USAGE_DATE` to emit US-style
dates. It overwrites only the generated November 10 file, never the good day.
Both variants add DISCOUNT_CODE and currency formatting using the existing vendor
generator. DuckDB uses header names, TRY_CAST, and the source-file replacement
transaction. Both targets accept only the anchored `CUST-[0-9]+` customer prefix
in addition to numeric IDs. After loading, before commit, each required field is
checked for nonempty raw values whose conversion produced NULL; failures report
column/count/sample and roll back the day's replacement. Empty input values retain
the existing nullable behavior. DuckDB does not enforce CHAR/VARCHAR length limits, and its
date parsing is not Snowflake's automatic date parser.

Replay/backfill uses the same atomic source-file replacement:

```sh
uv run --with duckdb==1.4.2 --with tomlkit --with PyYAML python warehouse/pipeline/load_daily.py --target duckdb --no-build --date 2026-11-10 --step backfill
uv run --with duckdb==1.4.2 python warehouse/pipeline/backfill_diff.py migration/dw-exit/.runs/before-backfill.duckdb migration/dw-exit/.runs/nightly.duckdb
```

The diff compares full-row multisets per key/day, excluding only `_LOADED_AT`.
Failure telemetry includes bounded loader diagnostics with environment secrets
redacted; arbitrary driver exception text is withheld rather than risking credentials.

Use the existing named `sfx_d1110` connection in `~/.snowflake/connections.toml`
and its private-key file. Credentials never belong here. All operations use
`__RUN_DATABASE__`; load/reset use `__RUN_DATABASE___LOAD_WH`, dbt uses
`__RUN_DATABASE___TRANSFORM_WH`, and observation uses `__RUN_DATABASE___OPS_WH`.

```
make sfx-operate-load
make sfx-operate-break
warehouse/snowflake/.venv/bin/python warehouse/pipeline/observe.py
make sfx-operate-reset
warehouse/snowflake/.venv/bin/python warehouse/pipeline/observe.py --history
warehouse/snowflake/.venv/bin/python -m pytest warehouse/pipeline/test_pipeline.py -q
```

The committed November 9 file has 48 records, existing customer IDs 1–6,
fictional account names from the seed's ACCOUNT_NAME, and IDs 200001–200048
(above the inspected seed maximum of 200000). The generated November 10 file
adds 1000 to those IDs. Both USAGE_ID/USAGE_DAILY_ID and USAGE_DT/USAGE_DATE
are populated. SUBSCRIPTION_ID remains null because this feed has no subscription
key; existing relationship tests permit nulls.

The header-mapped loader validates all nine required columns before connecting,
prints and ignores extra columns, and parses currency symbols and thousands
separators in AMOUNT and UNIT_PRICE. It replaces only its own `_SRC_FILE` rows
using DELETE and COPY in one explicit transaction with ON_ERROR=ABORT_STATEMENT;
a failed COPY rolls back the delete. COPY is forced so dates can be replayed. Source markers are
`pipeline/YYYY-MM-DD.csv`, independent of stage URL formatting. Existing seed
rows are untouched. Each invocation builds `source:billing.USAGE_DAILY+`, including
pipeline-scoped source not-null tests and a COPY_HISTORY row-count test (latest
entry per file within 14 days). Legacy seed nulls are excluded.

The vendor change inserts DISCOUNT_CODE after a currency-formatted AMOUNT.
The old positional loader loaded only 42 of 48 rows with null financial fields.
The fixed loader ignores DISCOUNT_CODE and loads all 48 rows correctly.

For isolated backfills, use `--schema RAW_BILLING___RUN_DATABASE___BACKFILL`
`--warehouse __RUN_DATABASE___TRANSFORM_WH --step backfill --no-build` with `--date`.
Schemas must be RAW_BILLING or an identifier containing __RUN_DATABASE__; warehouses
must start with __RUN_DATABASE___. Defaults remain RAW_BILLING and __RUN_DATABASE___LOAD_WH.
`--no-build` skips dbt (whose sources still point at production RAW_BILLING).
Target overrides and --no-build are not supported for reset.

Reset deletes only November 10's source rows, removes its staged and generated
local file, and rebuilds dbt. November 9 remains loaded. Observation joins back
to source markers so the 200k legacy seed rows with null USAGE_DATE do not
distort daily metrics. Query-history filtering normalizes JSON whitespace
because the existing dbt tag macro merges workload/phase/run_token keys.

Notifications use `DEVIN_PIPELINE_WEBHOOK_URL` and
`DEVIN_PIPELINE_WEBHOOK_SECRET`. Configure the final HTTPS receiver URL without
embedded credentials or a fragment. The sender rejects plaintext URLs and all
redirects so its bearer credential cannot be forwarded to another endpoint.
Dry runs (no URL) still print the payload without sending a request.
