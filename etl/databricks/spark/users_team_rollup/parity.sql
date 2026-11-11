/* run=dbx-d1111 act=spark step=parity consumer=users_team_rollup */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for users_team_rollup: Spark before-result (cpw.dbx_d1111_parity.users__spark_users_team_rollup__spark_before) vs migrated target (cpw.dbx_d1111_after.users__spark_users_team_rollup).
-- Each rung is introduced by "-- rung: <name>"; every statement is sent with the prefix
-- /* run=dbx-d1111 act=spark step=parity consumer=users_team_rollup */ (step=idempotence after the second run).
-- Canonical columns: TEAM_ID, TEAM_NAME, MEMBERS; canonical formatting coalesce(cast(col AS STRING),'~').

-- rung: count
SELECT (SELECT count(*) FROM cpw.dbx_d1111_parity.users__spark_users_team_rollup__spark_before) AS before_rows, (SELECT count(*) FROM cpw.dbx_d1111_after.users__spark_users_team_rollup) AS after_rows;

/* run=dbx-d1111 act=spark step=parity consumer=users_team_rollup */
-- rung: hash
SELECT (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(TEAM_ID AS STRING),'~'), coalesce(cast(TEAM_NAME AS STRING),'~'), coalesce(cast(MEMBERS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_parity.users__spark_users_team_rollup__spark_before) AS before_hash, (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(TEAM_ID AS STRING),'~'), coalesce(cast(TEAM_NAME AS STRING),'~'), coalesce(cast(MEMBERS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_after.users__spark_users_team_rollup) AS after_hash;

/* run=dbx-d1111 act=spark step=parity consumer=users_team_rollup */
-- rung: before_except_after
SELECT * FROM (SELECT TEAM_ID, TEAM_NAME, MEMBERS FROM cpw.dbx_d1111_parity.users__spark_users_team_rollup__spark_before EXCEPT ALL SELECT TEAM_ID, TEAM_NAME, MEMBERS FROM cpw.dbx_d1111_after.users__spark_users_team_rollup) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=users_team_rollup */
-- rung: after_except_before
SELECT * FROM (SELECT TEAM_ID, TEAM_NAME, MEMBERS FROM cpw.dbx_d1111_after.users__spark_users_team_rollup EXCEPT ALL SELECT TEAM_ID, TEAM_NAME, MEMBERS FROM cpw.dbx_d1111_parity.users__spark_users_team_rollup__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=users_team_rollup */
-- rung: history
DESCRIBE HISTORY cpw.dbx_d1111_after.users__spark_users_team_rollup LIMIT 2;
