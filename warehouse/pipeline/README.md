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

The intentionally positional loader replaces only its own `_SRC_FILE` rows,
then forces COPY so dates can be replayed. Source markers are
`pipeline/YYYY-MM-DD.csv`, independent of stage URL formatting. Existing seed
rows are untouched. Each invocation builds `stg_billing__usage_daily+` with
the existing dbt tests; no quality tests have been added to dbt.

The vendor change inserts DISCOUNT_CODE after a currency-formatted AMOUNT.
Blank discounts become null currency codes, currency codes fail timestamp
conversion, and formatted amounts fail numeric conversion. Six long discount
codes exceed the landing currency column width and are skipped by COPY.
Thus 42 of 48 records load with null amounts/currencies/timestamps while the
existing dbt tests stay green. This is the deliberate BEFORE state, not a fix.

Reset deletes only November 10's source rows, removes its staged and generated
local file, and rebuilds dbt. November 9 remains loaded. Observation joins back
to source markers so the 200k legacy seed rows with null USAGE_DATE do not
distort daily metrics. Query-history filtering normalizes JSON whitespace
because the existing dbt tag macro merges workload/phase/run_token keys.
