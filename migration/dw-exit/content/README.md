# Content workflow conversion

`workflow.sql` ships `__RUN_DATABASE__.OPS.WF_SFX_CONTENT_DAILY()` as Snowflake
Scripting. Generate it with `warehouse/.venv/bin/python migration/dw-exit/content/convert.py`.
The compiler renders the existing owned dbt model SELECTs and macros; it does not
invoke dbt materializations or rewrite their mapping expressions. The regression
test requires the checked-in SQL to match those sources.

The caller supplies typed `USERS` and `DOCUMENTS` target tables and typed landing
tables in `PC_SRC` (`APP_USER`, `ROLE_GRANT`, `LOGIN_EVENT`, `DOCUMENT`, `DOC_SHARE`).
Create `OPS` before deploying the procedure and render the run database placeholder
with `warehouse.run_config`. No live deployment is performed by the local board.

The seven enabled sessions execute sequentially in a valid topological order;
parallel execution is not necessary for the success dependencies. Staging users,
roles and staging documents truncate and insert. Users and documents merge their
data-driven insert/update outputs; login and share outputs update else insert.
The owned login SELECT combines the two routed target instances of the same table.
DOC_SHARE cannot start before both ROLE_GRANT and DOCUMENT finish successfully.
Uncaught SQL errors abort the procedure; this is not an all-workflow transaction,
and earlier successful session writes are not rolled back. Disabled TEAM_MEMBER
is never written.

## Local proof and owner decisions

`parity/local_content.py` saves all eight typed pre-workflow tables, loads the same
landing files into typed `PC_SRC`, executes the actual PowerCenter workflow on the
local PostgreSQL Teradata emulator, and snapshots its eight outputs. It executes
the **shipped procedure body**, not independently reconstructed writes, in DuckDB.
DuckDB's ignored `VARCHAR(n)` cast lengths are lowered to explicit substrings to
match Snowflake casts. This is target cast semantics, not a source-port adapter.
The board records counts, profiles, duplicate-preserving keyed hashes and samples
for every differing key. Landing SHA-256s, pre-workflow hashes and execution paths
are recorded separately as `content_evidence`.

**Approved deviation:** PowerCenter source/SQ precision 60 truncates
`DISPLAY_NAME` before TRIM, whereas the existing staging model retains up to 200
characters. The model is intentionally unchanged and no input adapter is applied.
The raw measurements stay red and the scoped owner proof is retained; APP_USER's own target cast to VARCHAR(60)
can mask this staging difference downstream on the current fixture.

**Pending decision:** the emulator stores CHAR columns with trailing blanks, while
the Snowflake models retain unpadded strings. All differing DOCUMENT, DOC_SHARE
and APP_USER keys were checked: removing only trailing spaces made each full row
equal, and the PostgreSQL catalog identifies exactly STATUS_CD (12), FILE_TYPE (8),
and ACCESS_LEVEL (12) as CHAR. This is a storage side effect, not a mapping expression.
No TRIM comparison adapter or RPAD production change was applied. See decisions.json.
The workflow therefore remains red rather than silently accepting this difference.

The compatibility task DAG under `warehouse/snowflake/pc_dag/content.yml` validates
already-built `PC_CONTENT` outputs; it is not this procedure's execution engine.
Neither local evidence nor that DAG establishes live Snowflake parity, incremental
dbt semantics, or cutover approval. Snowflake stays **red**: **Snowflake login down**.
No Snowflake connection was attempted for sfg1120.
