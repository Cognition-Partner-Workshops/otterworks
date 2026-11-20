# Local area registration

`object_board.py` discovers `migration/dw-exit/*/area.yaml`. Use
`RUN_TOKEN=sfx-g1120 make sfx-area-prove AREA=billing` to seed the emulator and
measure one area, or `make sfx-manifest-board` for all registrations. The board
always includes every manifest object; Snowflake execution is disabled.

Example registration (paths under `sql` are relative to the area directory):

```yaml
schema: CONTENT
seed: ['STG_*']
sql: ['initial/10_load.sql']
dbt:
  - model: models/pc/content/pc_content__document.sql
    target: DOCUMENT
sources:
  pc_content.document: STG_DOCUMENT
snowpark:
  - job: warehouse/snowpark/docs_tag_normalize.py
    inputs:
      STG_DOCUMENT: [LOCAL, SPARK_RAW_DOCUMENTS, DOCUMENT]
    output: [LOCAL, MART_SPARK, DOCS_TAG_NORMALIZE]
    target: DOCS_TAG_NORMALIZE
```

`SFX_CONTENT.T` in the emulator maps to `CONTENT.T`. Non-view source tables
are created empty in DuckDB; only names matching `seed` patterns are copied.
Converted SQL executes only when its references have been materialized.

dbt runs the selected models and their ancestors using dbt-duckdb against the
board's file-backed database. A disposable project/profile is used; committed
Snowflake profiles are neither read nor edited. Sources resolve within the area
schema; optional `sources` entries map `source_name.table_name` to a seeded
identifier. Selected models get the registered target aliases/schema. Models
must be DuckDB-compatible: Snowflake-only governance/comment/query-tag hooks
are no-ops, not emulations of Snowflake behavior. Unsupported model SQL remains
red with an execution error rather than being treated as measured.

Snowpark jobs are imported directly (not through the real-session runner) and
called as `run(session)` with a local-testing session. `inputs` map DuckDB table
names to local Snowpark relation names (strings or qualified-name lists). Jobs
may return a DataFrame; otherwise `output` identifies their saved result.
Local-testing unsupported operations remain red with an error. No remote
Snowflake fallback exists.
