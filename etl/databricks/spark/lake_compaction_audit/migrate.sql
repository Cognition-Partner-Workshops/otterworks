/* run=dbx-d1111 act=spark step=run1 consumer=lake_compaction_audit */
-- run_token=dbx-d1111 expires=2026-11-24
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.audit__spark_lake_compaction_audit
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS WITH AUDIT_DAILY_SUMMARY AS (SELECT EVENT_DATE, EVENT_TYPE, EVENT_COUNT, ACTORS
FROM cpw.dbx_d1111_after.audit__spark_audit_daily_summary)
SELECT * FROM AUDIT_DAILY_SUMMARY;
