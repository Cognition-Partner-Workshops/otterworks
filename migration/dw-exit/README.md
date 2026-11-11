# Act 1: Assess

Offline only; no connections, credentials, or changes to the source estate.
Run from the repository root with Python 3, PyYAML and pytest installed:

```sh
python migration/dw-exit/tools/check.py # fails before generation
python migration/dw-exit/tools/assess.py
python migration/dw-exit/tools/check.py
python -m pytest migration/dw-exit/tests -q
```

The generator overwrites only the assessment outputs in this directory. Inputs
are the checked-out estate, registry, DBQL CSVs, licence YAML and planted risk
registers. Generated IDs use stable SHA-256 prefixes, lists and edges are sorted,
and no wall-clock values are used. See `plan.md` for interpretation and limits.

## Live assessment control plane

Install `requirements.txt` in a virtual environment outside the repository.
Bind SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE,
SNOWFLAKE_PRIVATE_KEY and SNOWFLAKE_RUN_TOKEN from the credential store per
invocation. The PEM key is parsed only in memory, never written or printed.
Only SFX_D1110_AFTER is accepted; the warehouse is fixed to SFX_D1110_OPS_WH.
Every connection starts with the compact assess/preflight QUERY_TAG, then sets
the phase tag before executing work. Every command suspends the warehouse in
its cleanup path, including a failed verification.

```sh
python migration/dw-exit/tools/control.py verify # expected missing-schema failure before first load
python migration/dw-exit/tools/control.py load
python migration/dw-exit/tools/control.py verify
python migration/dw-exit/tools/control.py report
python migration/dw-exit/tools/control.py history
```

`load` creates six tables and four views with the run/expiry comment. DML replaces
all input datasets in one transaction, preserving table definitions. It resets
statuses: do not rerun after later-act progress without intending that reset.
MANIFEST has mutable STATUS, UPDATED_AT and UPDATED_BY_ACT fields. Later acts
must explicitly update the latter two alongside status (no automatic trigger).
The licence view counts objects still present until status becomes done/retired;
planning a retirement alone does not reduce the counter. Spark is measured zero.

The hidden-consumer SQL anti-joins SELECT principals against repository scan
hits, excluding identities also observed as ETL/UTILITY/BATCH. Thus batch accounts
missing from repository text do not become hidden end-user consumers. The dead
view independently anti-joins TablesV against all DBQL usage in the 90-day window.
`query_history.sql` is the exact proof query over the last day, up to 10,000
queries, grouped by phase and execution status. No renders are committed.
