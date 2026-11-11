/* run=dbx-d1111 act=spark step=run consumer=users_team_rollup */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/users_team_rollup.py. LEFT JOINs; COUNT(m.USER_ID) ignores NULL member user ids as in the source.
-- The source also overwrote JDBC table sfx_users.SPARK_TEAM_ROLLUP; this Delta table is its replacement.
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.users__spark_users_team_rollup
COMMENT 'Migrated Spark job users_team_rollup. run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS SELECT t.team_id AS TEAM_ID, t.team_name AS TEAM_NAME, COUNT(m.user_id) AS MEMBERS
FROM cpw.dbx_d1111_before.users__team t
LEFT JOIN cpw.dbx_d1111_before.users__team_member m ON t.team_id = m.team_id
LEFT JOIN cpw.dbx_d1111_before.users__app_user u ON m.user_id = u.user_id
GROUP BY t.team_id, t.team_name
