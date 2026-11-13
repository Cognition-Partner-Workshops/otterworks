# Warehouse parity

Requires Python 3.12. Install with `pip install -e '.[dev,oracle,snowflake]'`.
Run `python -m parity run --config example.yaml --left duckdb --right duckdb --out reports/run`.
Run tests with `pytest` and lint with `ruff check .`.

The YAML `objects` list names `left_table`, `right_table`, `keys`, `compare` and
`sample_size`. Columns are selected in key-then-compare order. Use the source's
identifier case, including uppercase Oracle column names. Empty key lists support
feeds that repeat rows. Hashes preserve duplicate multiplicity and distinguish
NULL from empty strings. Numbers retain significant decimal digits; insignificant
trailing zeros compare equally. Times compare to seconds, with aware timestamps
normalized to UTC. Samples use sorted SHA-256 scores, independent of row order.

Reports include every column profile, keyed-row hash and sampled values in JSON,
plus an object summary in Markdown. A mismatch is amber only when the object has
both `open_question` and `owner`; execution errors stay red. Exit status is 1 for
red objects and 0 otherwise. Reports contain data values and need the same access
controls as source data. The implementation reads each object into memory.

Connection settings live under `connections.left` and `connections.right`.
DuckDB uses `path`. Oracle uses environment variables `ORACLE_DSN`, `ORACLE_USER`
and `ORACLE_PASSWORD`; settings `dsn_env`, `user_env`, `password_env` can select
alternate environment variable names. Oracle runs in thin mode.
Snowflake uses `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
`SNOWFLAKE_PRIVATE_KEY_PATH`, optional `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE` and
`SNOWFLAKE_WAREHOUSE`; settings supply `database` and `schema`.
Snowflake authentication uses key-pair JWT.

The existing `migration/CONTRACTS.md` governs the separate Db2 selective-migration
demo. This standalone harness leaves its interfaces unchanged and uses full-scale
numeric strings. The demo retains its fixed eight-decimal wire format.
