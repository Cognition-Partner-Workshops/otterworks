# Audit conversion — sfg1120

Ported selectively from `a11fc255f` onto
[devin/sfg1120-audit](https://github.com/Cognition-Partner-Workshops/otterworks/tree/devin/sfg1120-audit).
Only audit conversions and their shared measurement helpers are enabled.
No other area's conversion module is imported. Other areas retain the base
board execution path and licence counters; migration status is still not_started.

## Reproduce this run

```sh
export RUN_TOKEN=sfx-sfg1120-audit
eval "$(warehouse/.venv/bin/python warehouse/run_config.py env)"
export NS="$RUN_BEFORE_NAMESPACE"  # sfx-sfg1120-audit-before
# Stacks already seeded at ROWS_PER_TABLE=200.
make sfx-informatica-run INFA_DB=teradata MAPPINGS=all INFA_WORKFLOWS=SFX_AUDIT:wf_SFX_AUDIT_DAILY
make sfx-teradata-run ROWS_PER_TABLE=200
for job in audit_actor_activity_join audit_archive_resort audit_daily_summary compliance_flag_rules lake_compaction_audit; do
  make sfx-spark-run JOB="$job" ROWS_PER_TABLE=200 || exit
done
make -o sfx-teradata-up sfx-manifest-board BOARD_ROWS=200 PARITY_TARGET=duckdb
warehouse/.venv/bin/python migration/dw-exit/tools/audit_parity.py
```

The fresh PC workflow succeeded (4/4 enabled sessions); archive was disabled.
All five audit Spark jobs succeeded. The batch chain was rerun after PC so its
snapshot is not contaminated by the PC summary's append behavior.
Namespace after-side is `sfx-sfg1120-audit-after`; no Snowflake connection,
preflight, capture, deployment, or prove was performed.

Result: **48 green, 3 approved_deviation, 6 retired, 0 red** locally.
All 57 Snowflake legs are red with exactly:
**Snowflake login down for run sfg1120; no live capture/prove**.
See [all measured rows](PARITY.md) and
[source / conversion / metric line links](../board/README.md#audit-parity-provenance).

## Execution and measurement

Batch executes the shipped `00_tables.sql`, nine headerless PSV COPY contracts
from `05_landing.sql`, then `10_load.sql`, `35_reports.sql`,
`30_views.sql`, `40_reconciliation.sql`, `45_finish.sql`.
The small supported Snowflake Scripting grammar in `local_audit.py` lowers calls
from `20_routines.sql`, `50_powercenter.sql`, `52_sessions.sql`,
`55_workflow.sql`; unknown constructs fail closed.
Macro resultsets are compared independently.

PowerCenter proof executes the original XML mappings on the same landing files
in a fresh rollback-only PostgreSQL schema, with fresh sequence state, then the
converted workflow in a separate DuckDB. Retained source logs and rejection
counts are in `audit_powercenter_evidence`; batch targets are never substituted
for mapping/session outputs. The converted workflow lives in AUDIT; the dbt
workflow deployment scaffold uses PC_AUDIT and deliberately omits archive.

Spark compares actual lake parquet and both JDBC outputs (daily summary and
compliance rules) to shipped dbt SQL on the same headered Spark PSVs.
These schemas differ from batch audit feeds. Input SHA-256 hashes and freshness
checks are retained; compaction reads the converted summary, not source output.

Counts, per-column null/min/max/distinct profiles, keyed full-row multiset hashes
and sampled differences come from `parity/ladder.py`. Trailing spaces are
ignored only for source CHAR columns derived from Teradata DDL. Duplicate
multiplicity remains part of parity. Every audit row links source, converted SQL,
and the current metric implementation on this branch. Retire rows link DBQL
files and keep both pinned BEFORE and current-checkout query records.

## Owner-approved summary IDs

`decisions.json` records approval of stable IDs starting 50001 in
`ORDER BY SUMMARY_DT, CUSTOMER_ID NULLS FIRST` order. The converted Scripting,
dbt model and offline-compiled workflow DAG all use this order. Rebuilds avoid
arrival-order-dependent retained IDs.

The legacy mapping uses unsorted source/aggregator encounter order plus a
sequence. Fresh legacy and converted results contain 60 groups; raw keyed hash
Δ is **84**, while the non-identity multiset matches. Under the explicit approved
numbering contract the hash Δ is zero. The mapping, session and workflow are
**approved_deviation**, not unqualified green. Raw counts, profiles, keyed hashes
and samples remain in each affected board row and the PC evidence section.
Without owner approval or with non-identity differences, these rows stay red.
No additional undocumented behavior change was needed.

## Owner-approved retirement and DBQL

All six archive candidates in `decisions.json` are retired locally; no physical
deletion, licence promotion, or Spark archive feed removal occurs.

Assessment reads pinned BEFORE commit
`a48ea0e29c31ca5a5445e22074a99a0549d7d6b3`:
`warehouse/teradata/dbql/{qrylog,objectusage,tablesv}.csv`.
Window: 2026-08-12 through 2026-11-09 inclusive.

- AUDIT_EVENT_ARCHIVE and M_ARCHIVE_OVERVIEW: zero usage records.
- STG_AUDIT_EVENT_ARCHIVE: one READ, no writes. Pinned query 111000000068,
  2026-08-12 06:06:11, svc_report_recon, BTEQ, finance-recon-01:
  `SELECT COUNT(*) AS ROW_COUNT FROM SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE;`.
- Current checkout has the equivalent setup read as query 111000000069,
  2026-08-12 06:06:58. These are distinct fixture versions, not two reads
  in the same window.
- Mapping/session/TPT retirement is dependency-derived, not direct DBQL evidence.
  The mapping writes archive from AUDIT_EVENT; the macro reads archive.
  The workflow references the archive session but ISENABLED=NO.
  The TPT loads archive staging, which is counted by the reconciliation reader.

Each retire row carries this evidence, its owner approval, and caller caveats.
`query_history.sql` is a Snowflake prove-history query, not DBQL retirement
evidence, and was not executed.

## Cross-area inputs and shared writers

Audit reads but does not convert the following external tables. Each listed base
table and its STG_ counterpart is read by reconciliation:

- BILLING: CUSTOMER_ACCOUNT, PLAN_CATALOG, TAX_RATE, SUBSCRIPTION, INVOICE_HDR,
  INVOICE_LINE, PAYMENT, CREDIT_NOTE, BILLING_ADJ, USAGE_DAILY.
- DOCUMENTS: FOLDER, DOCUMENT, DOC_VERSION, DOC_SHARE, DOC_TAG, DOC_COMMENT,
  FILE_OBJECT, COLLAB_SESSION, STORAGE_USAGE_DAILY.
- USERS: APP_USER, USER_PROFILE, TEAM, TEAM_MEMBER, ROLE_GRANT, SSO_IDENTITY,
  USER_STATUS_HIST, LOGIN_EVENT, USER_ACTIVITY_DAILY.

V_EVENT_ACTORS also joins USERS.APP_USER. Spark actor activity reads the separate
Spark USERS.USER_ACTIVITY_DAILY and USERS.LOGIN_EVENT fixture inputs.
The local proof explicitly copies read-only source snapshots for cross-area batch
inputs; this is not evidence of their target conversion or live integration.

No non-audit manifest object declares an audit output. However the shared
`warehouse/teradata/jobs/reconcile` writes AUDIT_RECON row 21000000001 from
documents storage counts. It is outside the manifest's normal kind extraction
and is represented in audit's reconciliation SQL. No non-audit PC folder or
consumer service SQL reference to SFX_AUDIT was found in the searched tree.

## Readers and ownership review

`consumers/registry.yaml` declares no SFX_AUDIT table. DBQL nevertheless records:

- svc_report_recon: 59 AUDIT_RECON reads, one V_CUSTOMER_RECON read, one staging
  archive setup count; maps to @otterworks/finance-reporting.
- nb_dsci_pkhan: 16 AUDIT_EVENT and 16 V_EVENT_ACTORS reads; unregistered notebook
  reader, not found in warehouse/ETL code by the assessment.
- svc_etl_audit: 90-day reads/writes for active staging/core audit tables,
  90 M_RECON_TOTALS, P_DAILY_SUMMARY and P_RECON_COUNTS executions each.
  This ETL account is not registered as an owner.

Manifest ownership was not silently changed. Six rows have
@otterworks/finance-reporting with owner_source DBQL readership via
consumers/registry.yaml: 03_load_reviews, 11_reconciliation, AUDIT_RECON,
STG_AUDIT_EVENT_ARCHIVE, audit_audit_event_archive, V_CUSTOMER_RECON.
The other 51 rows use @otterworks/data-platform, owner_source proposed.
In particular AUDIT_EVENT, V_EVENT_ACTORS and their producers still have proposed
owners despite observed nb_dsci_pkhan readership. These need owner validation;
the archive staging finance attribution is only a setup-day read, not proof
of ongoing business ownership.

## Checks

Using warehouse/.venv/bin/python with RUN_TOKEN=sfx-sfg1120-audit:

```text
test_audit.py + test_audit_spark.py + test_object_board.py:
50 passed in 3.53s
make sfx-manifest-board-test:
111 passed, 23 skipped in 9.29s
test_dag_audit.py + test_summary_reconciliation.py:
8 passed in 0.17s
```

The warehouse venv initially lacked Jinja2; installed Jinja2 3.1.6 locally for
offline DAG/model compilation, without installing or invoking Snowflake.
Generated-board validation also checked all 596 audit source/conversion/metric
URLs and line ranges, all 57 Snowflake reasons, and retirement setup-read evidence.
All 195 non-audit board rows are byte-for-value identical to the base board.

## Limits

Local proof is not live Snowflake parity, production Informatica ordering,
incremental/replay verification of every persistent target state, Snowflake
collation/VARCHAR enforcement, reject-file delivery, or cutover approval.
No visual UI verification was requested or performed.
