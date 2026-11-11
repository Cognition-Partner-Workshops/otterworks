# UNT-9: wf_SFX_AUDIT_DAILY (dbt workflow + Snowflake Task DAG)

## What is implemented
- `parity/workflow.py`: scoped workflow command. Reads the canonical `wf_SFX_AUDIT_DAILY.XML` graph and
  runs the enabled sessions as `dbt run --select <model>`, with PowerCenter `$X.Status = SUCCEEDED` link
  semantics: a failed session leaves its downstream sessions NOTSTARTED and fails the workflow. Archive is
  DISABLED in the XML, so it is excluded from the daily selector. It stays runnable on its own via dbt.
- `dbt_project.yml`: the audit block only, `+schema: {{ var('pc_audit_schema', 'PC_AUDIT') }}`, so the default
  stays `PC_AUDIT`. Billing and content blocks are unchanged; parse resolves billing to PC_BILLING and content to PC_CONTENT.
- `snowflake/pc_dag_audit.py` → `snowflake/pc_dag/audit.yml`: Task DAG bodies generated from the SQL that dbt actually
  ran for the incremental replay (temp view + MERGE, plus CTAS for staging). It has no schedule and no archive task.
  The DAG is deployed and run with the shared, unmodified `snowflake/pc_dag.py`.
  START→{STG_AUDIT_EVENT, SECURITY_ALERT}; STG_AUDIT_EVENT→AUDIT_EVENT→AUDIT_DAILY_SUMMARY.

## Replay
```
cd warehouse
python -m parity.workflow --schema PC_FX_UNT9_AUDIT_WF --step <step> --out <dir>   # dbt workflow
python -m parity.evidence_unt9 {oracle|preflight|run1|run2|collect1|collect2|compare|dag|postflight}
python snowflake/pc_dag_audit.py --run-dir <evidence>/dbt/run2/sessions --source-schema PC_FX_UNT9_AUDIT_WF \
  --schema PC_AUDIT --output snowflake/pc_dag/audit.yml
```
The `dag` step refuses to run if any `SFX_D1110_PC_AUDIT_*` task, task history or evidence directory already exists.

## Result (isolated schema SFX_D1110_AFTER.PC_FX_UNT9_AUDIT_WF; frozen manifest business date 20261109)
- Oracle: PowerCenter run of wf_SFX_AUDIT_DAILY. All 4 enabled sessions SUCCEEDED, with 480/480/118/61 rows and 3 security-alert rejects.
  Each target is equal to the accepted UNT-2 oracle. Archive did not run.
- dbt run1 and run2: no reset or full refresh. First-load multisets equal the oracle for all 4 targets, run1 == run2,
  0 duplicate keys, and the 3 unwritten INFO alerts equal the oracle rejects. The write scope covers only the isolated schema.
  The legacy second run appends the summary (236 rows). That is not claimed: d-summary-replay certifies
  idempotent replay.
- Task DAG: exactly one execution, graph run group `b35af49a-b056-4d33-b71a-b49a63520076`, run id 1794358031749.
  START `01c8542f-030d-21f3-0035-065b001c4616`, STG `01c8542f-030d-21e5-0035-065b001bc032`,
  SECURITY_ALERT `01c8542f-030d-21e5-0035-065b001bc036`, EVENT `01c8542f-030d-21ea-0035-065b001bf04a`,
  SUMMARY `01c8542f-030d-2214-0035-065b001c565e`: all SUCCEEDED. Final SHOW TASKS shows all 5 suspended.
  Post-DAG targets equal run2, with 0 duplicates.
- Postflight: the control table (20 rows, SHA 36035640…a2fe9ab3, QID 01c85431-030d-1e5c-0035-065b001d6196), the protected
  relations (data and metadata) and the PC_SRC sources are unchanged from preflight. No control row was written.
- Failure propagation: covered by `tests/test_workflow.py` (an injected failure blocks downstream sessions and the workflow fails;
  security alert stays independent). No live DAG run was spent on a failure.

## Limits and errata
- The evidence is bounded to the frozen inputs. It inherits the per-mapping limits from UNT-3, UNT-4 and UNT-5
  (for example, a duplicate ALERT_ID fails closed).
- Collector-only fixes are separate commits after `042ebfa22`. Retained failed attempts: `failed/oracle_attempt1_headerless_rowcount`,
  `dbt/run1/post_failed_attempt*`, and `failed/dag_attempt1_prior_history_window` (it failed before deploy, so no task was created).
- The DAG run was interrupted by a session suspension after `EXECUTE TASK`. TASK_HISTORY then confirmed a single run, and the
  collector resumed and suspended all tasks. EXECUTE TASK was not repeated.
- UNT-8 erratum (carried forward): the generated tables are Unicode 13.0.0, not 14.0.0.
