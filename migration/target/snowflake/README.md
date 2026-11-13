# Warehouse target project

Use Python 3.12 and `pip install -r requirements.txt`, then run:

```sh
dbt build --profiles-dir . --target duckdb
pytest scripts
python scripts/generate_sources.py --manifest /path/to/frozen/manifest.json --schema main
```

The example seed and model are independent of any source estate. Generated sources
preserve loader table and column names. Supply `--database` for the token database
and `--schema PUBLIC` for Snowflake, or the DuckDB database alias and `main` schema.

The default profile selects DuckDB, and Snowflake uses key-pair authentication from
`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, optional
`SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE`,
`SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_SCHEMA`. Tests and CI never connect to Snowflake.

`warehouse_hash` distinguishes NULL and empty strings using typed length prefixes.
Callers must supply explicit numeric and date formatting when cross-engine textual
representations differ. `safe_numeric` dispatches to each adapter's safe decimal
conversion and preserves the requested scale. `empty_string` requires a visible
policy: `preserve` keeps empty strings and `nullify` converts empty strings to NULL.
The default policy is preserve. The example spells out the policy in its model.

The warehouse CI job runs available parity and loader packages plus the DuckDB dbt
build. Each source PR can land independently; the combined job covers all packages
after they are merged. The existing Db2 demo and its binding contract stay unchanged.
