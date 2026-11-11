/* run=dbx-d1111 act=spark step=inputs consumer=audit_actor_activity_join */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT event_id AS AUDIT_EVENT_ID, actor_user_id AS ACTOR_USER_ID,
 document_id AS DOCUMENT_ID, event_type AS EVENT_TYPE, event_ts AS EVENT_AT, details AS DETAILS
FROM cpw.dbx_d1111_before.audit__audit_event;

/* run=dbx-d1111 act=spark step=inputs consumer=audit_actor_activity_join */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT activity_id AS USER_ACTIVITY_ID, user_id AS USER_ID, activity_dt AS ACTIVITY_DATE,
 CAST(login_count AS BIGINT) AS LOGIN_COUNT
FROM cpw.dbx_d1111_before.users__user_activity_daily;

/* run=dbx-d1111 act=spark step=inputs consumer=audit_actor_activity_join */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT login_id AS LOGIN_EVENT_ID, user_id AS USER_ID, login_ts AS EVENT_AT
FROM cpw.dbx_d1111_before.users__login_event;
-- BLOCKED: ACTION_COUNT has no equivalent: DOCUMENT_COUNT is not action count. LOGIN_EVENT USER_AGENT, RAW_LINE and IP_ADDRESS have no equivalents; CLIENT_TYPE is not a user agent.
