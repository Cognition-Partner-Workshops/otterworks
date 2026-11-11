/* run=dbx-d1111 act=spark step=inputs consumer=users_risk_score */
-- run_token=dbx-d1111 expires=2026-11-24
-- ACTION_COUNT intentionally unresolved: DOCUMENT_COUNT is not an equivalent.
SELECT activity_id AS USER_ACTIVITY_ID, user_id AS USER_ID,
       activity_dt AS ACTIVITY_DATE, login_count AS LOGIN_COUNT,
       action_count AS ACTION_COUNT
FROM cpw.dbx_d1111_before.users__user_activity_daily;
