/* run=dbx-d1111 act=spark step=run1 consumer=audit_actor_activity_join */
-- run_token=dbx-d1111 expires=2026-11-24
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join
USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS WITH AUDIT_EVENT AS (SELECT event_id AS AUDIT_EVENT_ID, actor_user_id AS ACTOR_USER_ID,
 document_id AS DOCUMENT_ID, event_type AS EVENT_TYPE, event_ts AS EVENT_AT, details AS DETAILS
FROM cpw.dbx_d1111_before.audit__audit_event),
USER_ACTIVITY_DAILY AS (SELECT activity_id AS USER_ACTIVITY_ID, user_id AS USER_ID, activity_dt AS ACTIVITY_DATE,
 CAST(login_count AS BIGINT) AS LOGIN_COUNT
FROM cpw.dbx_d1111_before.users__user_activity_daily),
LOGIN_EVENT AS (SELECT login_id AS LOGIN_EVENT_ID, user_id AS USER_ID, login_ts AS EVENT_AT
FROM cpw.dbx_d1111_before.users__login_event),
activity AS (
 SELECT CASE WHEN LOGIN_COUNT > 12 THEN 0 ELSE USER_ID END USER_KEY,
        ACTIVITY_DATE, SUM(LOGIN_COUNT) LOGIN_COUNT, SUM(ACTION_COUNT) ACTION_COUNT
 FROM USER_ACTIVITY_DAILY
 GROUP BY CASE WHEN LOGIN_COUNT > 12 THEN 0 ELSE USER_ID END, ACTIVITY_DATE
), logins AS (
 SELECT CASE WHEN hour(EVENT_AT) < 8 THEN 0 ELSE USER_ID END USER_KEY,
        MAX(USER_AGENT) USER_AGENT, concat_ws('\n', collect_list(RAW_LINE)) LOGIN_TEXT
 FROM LOGIN_EVENT GROUP BY CASE WHEN hour(EVENT_AT) < 8 THEN 0 ELSE USER_ID END
)
SELECT coalesce(a.ACTOR_USER_ID, 0) USER_KEY, a.AUDIT_EVENT_ID, a.EVENT_AT,
       d.ACTIVITY_DATE, d.ACTION_COUNT, l.USER_AGENT, octet_length(l.LOGIN_TEXT) LOGIN_TEXT_BYTES
FROM AUDIT_EVENT a
JOIN activity d ON coalesce(a.ACTOR_USER_ID, 0) = d.USER_KEY
JOIN logins l ON coalesce(a.ACTOR_USER_ID, 0) = l.USER_KEY;
