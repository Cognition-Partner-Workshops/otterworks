# Content workflow conversion

`workflow.sql` ships `__RUN_DATABASE__.OPS.WF_SFX_CONTENT_DAILY()` as Snowflake
Scripting. Generate it with `warehouse/.venv/bin/python migration/dw-exit/content/convert.py`.
The workflow calls the area-owned session targets in `users/52_sessions.sql` and
`documents/52_sessions.sql`. The compiler renders their existing owned dbt SELECTs
and macros without rewriting mapping expressions. The regression test requires
all three generated files to match those sources. Deploy the two session files
before the workflow or task DAG. The five users dbt session aliases also retain
the approved manifest target names, including standalone TEAM_MEMBER.

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

## Local proof and pending decision

`parity/local_content.py` saves all eight typed pre-workflow tables, loads the same
landing files into typed `PC_SRC`, executes the actual PowerCenter workflow on the
local PostgreSQL Teradata emulator, and snapshots its eight outputs. It executes
the **shipped procedure body**, not independently reconstructed writes, in DuckDB.
DuckDB's ignored `VARCHAR(n)` cast lengths are lowered to explicit substrings to
match Snowflake casts. This is target cast semantics, not a source-port adapter.
The board records counts, profiles, duplicate-preserving keyed hashes and samples
for every differing key. Landing SHA-256s, pre-workflow hashes and execution paths
are recorded separately as `content_evidence`.

**Pending owner decision:** PowerCenter source/SQ precision 60 truncates
`DISPLAY_NAME` before TRIM, whereas the existing staging model retains up to 200
characters. The model is intentionally unchanged and no input adapter is applied.
The local workflow row remains red; APP_USER's own target cast to VARCHAR(60)
can mask this staging difference downstream on the current fixture.

The compatibility task DAG under `warehouse/snowflake/pc_dag/content.yml` validates
already-built `PC_CONTENT` outputs; it is not this procedure's execution engine.
Neither local evidence nor that DAG establishes live Snowflake parity, incremental
dbt semantics, or cutover approval. Snowflake stays **red**: the recorded role
`SFX_D1110_ROLE` has no access to `SFX_1119` (002003), so live capture/prove were not run.
