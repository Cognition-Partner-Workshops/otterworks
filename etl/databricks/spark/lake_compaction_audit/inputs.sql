/* run=dbx-d1111 act=spark step=inputs consumer=lake_compaction_audit */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT EVENT_DATE, EVENT_TYPE, EVENT_COUNT, ACTORS
FROM cpw.dbx_d1111_after.audit__spark_audit_daily_summary;
