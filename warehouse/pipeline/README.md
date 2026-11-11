# sfx-d1110 daily billing feed

Use the existing named `sfx_d1110` connection in `~/.snowflake/connections.toml`
and its private-key file. Credentials never belong here. All operations use
`SFX_D1110_AFTER`; load/reset use `SFX_D1110_LOAD_WH`, dbt uses
`SFX_D1110_TRANSFORM_WH`, and observation uses `SFX_D1110_OPS_WH`.

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

For isolated backfills, use `--schema RAW_BILLING_SFX_D1110_BACKFILL`
`--warehouse SFX_D1110_TRANSFORM_WH --step backfill --no-build` with `--date`.
Schemas must be RAW_BILLING or an identifier containing SFX_D1110; warehouses
must start with SFX_D1110_. Defaults remain RAW_BILLING and SFX_D1110_LOAD_WH.
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
