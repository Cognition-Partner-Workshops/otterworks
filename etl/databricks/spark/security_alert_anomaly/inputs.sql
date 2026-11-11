/* run=dbx-d1111 act=spark step=inputs consumer=security_alert_anomaly */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT alert_id AS SECURITY_ALERT_ID, actor_user_id AS USER_ID, alert_ts AS EVENT_AT
FROM cpw.dbx_d1111_before.audit__security_alert;
-- BLOCKED: SCORE and ALERT_TYPE have no equivalent. SEVERITY_CD is categorical, not a numeric anomaly score.
