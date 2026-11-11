/* run=dbx-d1111 act=spark step=parity consumer=user_pref_json_flatten */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for user_pref_json_flatten. Not executed: the job is RED (no live input, see README); neither table exists.
-- Same canonical formatting as the green jobs: concat_ws('|', coalesce(cast(col AS STRING),'<NULL>') ...).
SELECT 'before' AS side, count(*) AS row_count,
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_PREF_ID AS STRING),'<NULL>'), coalesce(cast(USER_ID AS STRING),'<NULL>'), coalesce(cast(PREF_JSON AS STRING),'<NULL>'), coalesce(cast(THEME AS STRING),'<NULL>'), coalesce(cast(NOTIFICATIONS AS STRING),'<NULL>'), coalesce(cast(LOCALE AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash
FROM cpw.dbx_d1111_parity.users__spark_user_pref_json_flatten__spark_before
UNION ALL
SELECT 'after', count(*),
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_PREF_ID AS STRING),'<NULL>'), coalesce(cast(USER_ID AS STRING),'<NULL>'), coalesce(cast(PREF_JSON AS STRING),'<NULL>'), coalesce(cast(THEME AS STRING),'<NULL>'), coalesce(cast(NOTIFICATIONS AS STRING),'<NULL>'), coalesce(cast(LOCALE AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0)))
FROM cpw.dbx_d1111_after.users__spark_user_pref_json_flatten;

/* run=dbx-d1111 act=spark step=parity consumer=user_pref_json_flatten */
SELECT 'before_not_in_after' AS direction, * FROM (
  SELECT USER_PREF_ID, USER_ID, PREF_JSON, THEME, NOTIFICATIONS, LOCALE FROM cpw.dbx_d1111_parity.users__spark_user_pref_json_flatten__spark_before
  EXCEPT ALL
  SELECT USER_PREF_ID, USER_ID, PREF_JSON, THEME, NOTIFICATIONS, LOCALE FROM cpw.dbx_d1111_after.users__spark_user_pref_json_flatten) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=user_pref_json_flatten */
SELECT 'after_not_in_before' AS direction, * FROM (
  SELECT USER_PREF_ID, USER_ID, PREF_JSON, THEME, NOTIFICATIONS, LOCALE FROM cpw.dbx_d1111_after.users__spark_user_pref_json_flatten
  EXCEPT ALL
  SELECT USER_PREF_ID, USER_ID, PREF_JSON, THEME, NOTIFICATIONS, LOCALE FROM cpw.dbx_d1111_parity.users__spark_user_pref_json_flatten__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=user_pref_json_flatten */
DESCRIBE HISTORY cpw.dbx_d1111_after.users__spark_user_pref_json_flatten;
