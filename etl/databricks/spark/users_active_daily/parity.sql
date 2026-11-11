/* run=dbx-d1111 act=spark step=parity consumer=users_active_daily */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for users_active_daily: Spark before-result (cpw.dbx_d1111_parity.users__spark_users_active_daily__spark_before) vs migrated target (cpw.dbx_d1111_after.users__spark_users_active_daily).
-- Each rung is introduced by "-- rung: <name>"; every statement is sent with the prefix
-- /* run=dbx-d1111 act=spark step=parity consumer=users_active_daily */ (step=idempotence after the second run).
-- Canonical columns: ACTIVITY_DATE, ACTIVE_USERS, LOGINS, ACTIONS; canonical formatting coalesce(cast(col AS STRING),'~').

-- rung: count
SELECT (SELECT count(*) FROM cpw.dbx_d1111_parity.users__spark_users_active_daily__spark_before) AS before_rows, (SELECT count(*) FROM cpw.dbx_d1111_after.users__spark_users_active_daily) AS after_rows;

/* run=dbx-d1111 act=spark step=parity consumer=users_active_daily */
-- rung: hash
SELECT (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(ACTIVITY_DATE AS STRING),'~'), coalesce(cast(ACTIVE_USERS AS STRING),'~'), coalesce(cast(LOGINS AS STRING),'~'), coalesce(cast(ACTIONS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_parity.users__spark_users_active_daily__spark_before) AS before_hash, (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(ACTIVITY_DATE AS STRING),'~'), coalesce(cast(ACTIVE_USERS AS STRING),'~'), coalesce(cast(LOGINS AS STRING),'~'), coalesce(cast(ACTIONS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_after.users__spark_users_active_daily) AS after_hash;

/* run=dbx-d1111 act=spark step=parity consumer=users_active_daily */
-- rung: before_except_after
SELECT * FROM (SELECT ACTIVITY_DATE, ACTIVE_USERS, LOGINS, ACTIONS FROM cpw.dbx_d1111_parity.users__spark_users_active_daily__spark_before EXCEPT ALL SELECT ACTIVITY_DATE, ACTIVE_USERS, LOGINS, ACTIONS FROM cpw.dbx_d1111_after.users__spark_users_active_daily) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=users_active_daily */
-- rung: after_except_before
SELECT * FROM (SELECT ACTIVITY_DATE, ACTIVE_USERS, LOGINS, ACTIONS FROM cpw.dbx_d1111_after.users__spark_users_active_daily EXCEPT ALL SELECT ACTIVITY_DATE, ACTIVE_USERS, LOGINS, ACTIONS FROM cpw.dbx_d1111_parity.users__spark_users_active_daily__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=users_active_daily */
-- rung: history
DESCRIBE HISTORY cpw.dbx_d1111_after.users__spark_users_active_daily LIMIT 2;
