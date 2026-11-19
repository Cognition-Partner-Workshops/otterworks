# Audit conversion

**Owner decision applied:** PowerCenter daily summary IDs are assigned starting
at 50001 by ROW_NUMBER ordered by SUMMARY_DT, CUSTOMER_ID NULLS FIRST. dbt rebuilds
the same stable numbering. Proofs compare against legacy groups renumbered by
that explicit contract, retaining the raw legacy ID comparison. This intentionally
replaces first-seen/sequence assignment. Storage reconciliation continues to read
deduped documents core data, not raw staging duplicates.

The dbt summary is rebuilt rather than preserving previously assigned IDs, so
late-arriving groups cannot make IDs depend on load order. The committed DAG's
summary task is recompiled from the model with `pc_dag_audit.py --refresh-summary`;
this is offline SQL generation, not evidence of a live dbt/Snowflake run.

No retire object is converted. The archive landing feed remains untouched for Spark.
Spark models live under `warehouse/dbt/models/spark/<job>/`. Nothing here authorizes retirement, migration-state
promotion, or live Snowflake execution.

## Execution paths

Batch: create AUDIT schema, execute `00_tables.sql`, upload the headerless audit PSVs
to the internal stage declared by `05_landing.sql`, then execute its nine COPYs.
Run `10_load.sql`, define `20_routines.sql`, run `35_reports.sql`, `30_views.sql`,
`40_reconciliation.sql`, and `45_finish.sql` in that order. Substitute the validated
business date and render run placeholders using `warehouse/run_config.py`.
USERS and DOCUMENTS are external inputs; BILLING must already have completed its
own conversion. Reconciliation runs after billing/storage and includes the generic
`warehouse/teradata/jobs/reconcile` write (21000000001) before the BTEQ count rows.
`M_RECON_TOTALS` returns the final business-date resultset.

PowerCenter: define `50_powercenter.sql`, `52_sessions.sql`, and `55_workflow.sql`,
then call `AUDIT_PC.WF_SFX_AUDIT_DAILY()`. It consumes the same landed staging feeds,
but has separate targets: it must not be substituted for the batch chain. The
disabled archive session is deliberately absent. Fresh local proof starts with
empty targets and sequence current value 50001. Persistent sequence/rerun semantics
and Snowflake VARCHAR/collation enforcement need live verification. Unknown
security severity routes are rejected (excluded from the relational target).

## Local evidence

`make -o sfx-teradata-up sfx-manifest-board RUN_TOKEN=sfx1119` regenerates the manifest
and board. `parity/local_audit.py` executes the shipped batch SQL and procedure
bodies in DuckDB. It reads the actual headerless PSVs and records SHA-256 hashes.
USERS/DOCUMENTS inputs are copied explicitly from the source snapshot, while the
existing converted BILLING relations are used unchanged. This proves audit logic,
not migration of those external subject areas.

`parity/powercenter_audit.py` executes the original XML mappings using the repo's
runner in a fresh rollback-only PostgreSQL schema, with separate sequence storage.
It executes the shipped converted workflow in DuckDB against the same landing
files. Mapping/session rows reference these isolated outputs, not batch outputs.
Counts, profiles, keyed multiset hashes and samples use the shared ladder. Source
rejections/logs are retained in board evidence; rejected source data is not silently
removed from the conversion to force green.

## Spark evidence

The five audit Spark jobs materialize dbt tables in MART_SPARK. The actor join
preserves the source's explicit skew-key expressions and inner joins. Archive
resort and compaction preserve row multiplicity; their physical two-partition
layout is not a Snowflake relational requirement. Compaction uses
`ref('audit_daily_summary')`, not a copy of the source result.

`parity/spark_audit.py` compares real legacy Parquet with the shipped models fed
the same headered Spark landing PSVs (different schemas from batch audit feeds).
The daily summary and compliance jobs also compare their actual JDBC outputs
from the separate Spark PostgreSQL service, as independently declared board
relations. `output_artifacts` records real lake and JDBC names in the generated
manifest. Input hashes and freshness checks are retained in board evidence.

Run the six billing jobs and five audit jobs after `make sfx-spark-up`, with
`RUN_TOKEN=sfx1119 NS=sfx-1119-before ROWS_PER_TABLE=200`. Run
`audit_daily_summary` before `lake_compaction_audit`; then regenerate the board
with the documented Make target. No registry migration status is promoted.

Local proof is not live Snowflake parity, cutover approval, complete incremental
proof, or verification of mapping reject-file delivery on Snowflake.

## Unresolved source ordering side effect (leave red)

`m_SFX_AUDIT_DAILY_SUMMARY`, its session, and `wf_SFX_AUDIT_DAILY` remain red.
The source XML specifies an unsorted, non-deterministic source qualifier
(`m_SFX_AUDIT_DAILY_SUMMARY.XML:23–38`), an unsorted aggregate (`:51–63`),
and a sequence current value of 50001 (`:65–75`), but no association between a
particular summary group and a particular generated ID. The local runner reads
without ORDER BY (`etl/informatica/runner/engine.py:400–432`), emits groups in
first-encounter dictionary order (`:622–660`), and assigns sequence values while
writing target rows (`:829–835`, `:734–761`). This path actually ran: the retained
session log records the unordered SELECT and 60 groups produced.

DuckDB executes the shipped GROUP BY and sequence without emulating the runner's
first-seen ordering. Counts and all column profiles match (60 summary rows), but
the SUMMARY_ID-to-group assignment differs, so keyed hashes correctly fail.
`audit_powercenter_evidence.summary_non_identity_multiset_matches` separately
checks the full multiset excluding SUMMARY_ID; it does not relax board parity.

Disproof check: reran the original mapping with the same 200 events inserted in
ascending then descending EVENT_ID order, with fresh identical sequence state in
rollback-only PostgreSQL isolation. Both runs wrote 60 rows; excluding SUMMARY_ID,
the multisets were identical. ID 50001 changed from `(2026-11-09, 1, 4, 0)` to
`(2026-11-08, 20, 4, 0)`. The source assignment is therefore not a stable business
key policy. No source-order emulation, ID remapping, or weakened parity gate is
applied. A stable surrogate-key policy requires owner clarification; live
Informatica ordering has not been verified.
