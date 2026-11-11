/* run=dbx-d1111 act=spark step=parity consumer=users_risk_score */
-- run_token=dbx-d1111 expires=2026-11-24
-- Intentionally fails: no honest before result can be built without ACTION_COUNT.
SELECT activity_id, user_id, activity_dt, login_count, action_count
FROM cpw.dbx_d1111_before.users__user_activity_daily;

/* run=dbx-d1111 act=spark step=inputs consumer=users_risk_score */
DESCRIBE TABLE cpw.dbx_d1111_before.users__stg_user_activity_daily;
