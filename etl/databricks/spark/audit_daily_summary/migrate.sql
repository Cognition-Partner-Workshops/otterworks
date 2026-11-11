/* run=dbx-d1111 act=spark step=run1 consumer=audit_daily_summary */
-- run_token=dbx-d1111 expires=2026-11-24
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.audit__spark_audit_daily_summary
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS WITH AUDIT_EVENT AS (SELECT event_id AS AUDIT_EVENT_ID, actor_user_id AS ACTOR_USER_ID,
 document_id AS DOCUMENT_ID, event_type AS EVENT_TYPE, event_ts AS EVENT_AT, details AS DETAILS
FROM cpw.dbx_d1111_before.audit__audit_event)
SELECT to_date(EVENT_AT) EVENT_DATE, EVENT_TYPE, COUNT(*) EVENT_COUNT,
       COUNT(DISTINCT ACTOR_USER_ID) ACTORS
FROM AUDIT_EVENT GROUP BY to_date(EVENT_AT), EVENT_TYPE;
