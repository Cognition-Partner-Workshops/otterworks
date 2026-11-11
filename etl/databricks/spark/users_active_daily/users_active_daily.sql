/* run=dbx-d1111 act=spark step=run consumer=users_active_daily */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/users_active_daily.py. ACTION_COUNT has no live source (see inputs.sql): ACTIONS is NULL, job stays RED.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.users__spark_users_active_daily
COMMENT 'Migrated Spark job users_active_daily. run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS SELECT activity_dt AS ACTIVITY_DATE, COUNT(DISTINCT user_id) AS ACTIVE_USERS,
       SUM(CAST(login_count AS BIGINT)) AS LOGINS, CAST(NULL AS BIGINT) AS ACTIONS
FROM cpw.dbx_d1111_before.users__user_activity_daily
GROUP BY activity_dt
