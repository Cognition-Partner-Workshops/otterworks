# Databricks DW exit assessment

Offline assessment uses Python stdlib and PyYAML. Live operations use only the
Databricks SQL connector and the existing serverless SQL warehouse. No clusters
or warehouses are created. All new files stay in this directory.

## Rerun

```sh
python3 -m venv migration/dw-exit-dbx/.venv
migration/dw-exit-dbx/.venv/bin/pip install -r migration/dw-exit-dbx/requirements.txt
migration/dw-exit-dbx/.venv/bin/python migration/dw-exit-dbx/assess.py --spark-ref pr-2740
# Set DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID,
# DATABRICKS_CATALOG=cpw in the environment, never in tracked files.
migration/dw-exit-dbx/.venv/bin/python migration/dw-exit-dbx/load_control.py
migration/dw-exit-dbx/.venv/bin/python migration/dw-exit-dbx/check.py
migration/dw-exit-dbx/.venv/bin/python -m unittest discover -s migration/dw-exit-dbx -p 'test_*.py'
```

After the Spark parent PR merges, rebase and rerun assess.py without --spark-ref.
The flag reads only etl/spark from git; it does not merge or check out that ref.
Source paths and stable IDs are identical in either mode. Metadata records the
Spark ref and commit; working-tree mode records HEAD (uncommitted edits are not
claimed to be part of that commit). check.py reuses the recorded ref.

## Inventory and rules

Each CREATE TABLE/VIEW is an object. Macro/procedure definitions, BTEQ scripts,
FastLoad/TPT files, scheduling wrappers, PowerCenter mappings, sessions and
workflows, five cron scripts and spark_load.py each have their own entry.
Workflow XML embeds mapping copies: mappings are counted only from mapping
exports, not twice. XML LOC is measured on the named element block, not the full
repository export; all other code LOC excludes blank lines, block comments and
lines starting #, --, // or *. Inline comments do not remove the code line.
DDL LOC is partitioned at successive CREATE TABLE/VIEW boundaries.

Complexity: high if LOC >150 or at least 8 JOIN/QUALIFY/MERGE/UNION/WHILE/LOOP/
UDF/RDD/TRANSFORMATION tokens; medium if LOC >40 or at least 2 tokens; else low.
Risk defaults to complexity, with high risk for hidden consumers and compatibility
views. Each manifest entry includes a reason. Ownership prefers the first
registered consumer team for its exact object, else an area team. CODEOWNERS
matches those consumer teams. Area heuristics are reviewable, not ownership proof.

Spark inventory has one entry for each of 30 jobs in jobs.txt, with code, submit
and k8s source_paths. Common Python modules and Scala BatchSupport are separate
shared entries counted once, never multiplied across jobs. Job LOC excludes
submit/k8s manifests. Classification hints map dbt -> Lakeflow pipeline (SQL
transforms, wave 3), snowpark_python -> PySpark job, and spark_standard_template
-> PySpark job. Scala implementations require PySpark parity rewrites. The shared
runtime and existing six batch jobs also target PySpark. No Snowflake target is
retained. Control IDs are hashes of source path plus object, not source names.

Wave 1 = DBQL retirement and Delta tables; wave 2 = ingestion; wave 3 =
transformations and orchestration; wave 4 = compatibility/cutover/decommission.
Unread candidates follow the specified no READ/EXECUTE rule, even for write-active
objects: 6 dormant and 19 write-only. Retirement additionally requires no static
code reader. Objects read by code keep their migration target, high risk and a
reader-path reason. Reader checks cover SQL FROM/JOIN/CALL/EXEC, PowerCenter
Teradata SOURCE/lookup declarations, consumer SQL, and Spark SQL/register/landing/jdbc_read.
Spark landing reads conservatively retain the corresponding logical Teradata object;
this does not claim the job reads Teradata JDBC. References used only as write
targets, declarations, fixtures or schema constants are not readers. Evidence is
stored per object in the manifest and dbql.md. Do not automatically delete based
on this static assessment alone.
lineage.md has an area-level flow overview plus Spark code-derived graph/detail;
it is static source lineage, not a claim of observed execution.

## DBQL and privacy

Window: 2026-08-12 through 2026-11-10 inclusive, using StartTime and joined QueryID.
Dead candidates are SFX_* tablesv objects with no READ/EXECUTE, including macros;
LastAccessTimeStamp/AccessCount are included for cross-checking. WRITE-only objects
therefore qualify even with recent timestamps. DBC system tables are excluded.

Hidden discovery uses literal case-insensitive username OR full ClientID search
over git-tracked repository text, excluding warehouse/teradata/dbql/ and this
directory, plus warehouse/teradata/tests/test_dbql.py (the emulator test, not
consumer code). svc_etl_* are internal producer row-count checks, not consumers;
their stable IDs are retained and reclassified as internal ETL, wave 3. The one
hidden consumer is the finance analyst. It gets a wave 4 discovery entry plus
one compatibility-view cutover entry per object read, owned by finance-ops with
high risk. The registered SFTP consumer is not hidden; DBQL timing mismatch and
failed read paths are documented in dbql.md.
Person-name username suffixes are masked in all generated files. No source SQL,
customer/partner data records or raw XML descriptions are copied to output.

## Live table contract and counter

The existing cpw.dbx_d1111_control.migration_control is preserved. object_name is
manifest id; subject_area and source_system are explicit manifest fields. Loader
adds missing manifest columns using guarded ALTER, then MERGEs on object_name.
New rows have status planned, parity NULL, pr NULL; matched rows retain these
three demo-managed fields. Retirement targets remain planned until actually
retired. updated_at changes on reload. No DELETE or replacement is performed.
Changing the inventory to remove entries requires explicit operator reconciliation;
check.py rejects stale row counts rather than deleting demo-owned state.

board/README.md contains counter SQL. Spark hours come only from
etl/spark/history/baseline.json (30 applications), with per-job hours loaded as
DECIMAL(18,9). NULL on other jobs means not measured, not zero. Independently
rounded per-job values may differ from the aggregate baseline by a few billionths;
check.py permits 1e-8 for that comparison, but requires exact manifest/live sum.
No annual extrapolation is made. Every live SQL statement is tagged and all
objects created by the loader carry the run-token/expiry comment. Catalog is
restricted to cpw and all mutation targets are dbx_d1111_control only.
