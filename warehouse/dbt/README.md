# Billing staging

Use the shared warehouse/.venv and injected SNOWFLAKE_* environment variables.

```sh
make sfx-snowflake-test
SFX_EXECUTED_BY=devin make sfx-snowflake-dbt
warehouse/.venv/bin/python warehouse/snowflake/sfx_conn.py
```

run_dbt.py uses sfx_conn.query_tag for connection-level attribution and the
set_query_tag/unset_query_tag macros preserve that shape for materializations.
Override SFX_COMMIT, SFX_RUN_ID, SFX_EXECUTED_BY and SFX_BUILT_WITH as needed;
pass --phase to run_dbt.py to change the phase (default dbt).
The wrapper aliases SNOWFLAKE_PRIVATE_KEY in memory to
DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY so dbt scrubs the PEM and excludes it from
persisted environment-variable artifacts. No key file is used. Run via the
wrapper rather than the bare dbt CLI.

Offline parse supplies dummy profile values and never connects to Snowflake.
No external dbt packages are required. The empty marts directory intentionally
produces an unused-configuration warning until a MART model is added.
Views persist their token-bearing descriptions as Snowflake comments.

After changing landing_columns.yml, regenerate source declarations and billing
views/tests:

```sh
warehouse/.venv/bin/python warehouse/dbt/tools/render_sources.py
warehouse/.venv/bin/python warehouse/dbt/tools/render_billing.py
```
