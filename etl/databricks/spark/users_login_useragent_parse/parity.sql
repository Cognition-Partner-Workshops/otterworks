/* run=dbx-d1111 act=spark step=parity consumer=users_login_useragent_parse */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for users_login_useragent_parse. Not executed: the job is RED (no live input, see README); neither table exists.
-- Same canonical formatting as the green jobs: concat_ws('|', coalesce(cast(col AS STRING),'<NULL>') ...).
SELECT 'before' AS side, count(*) AS row_count,
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(LOGIN_EVENT_ID AS STRING),'<NULL>'), coalesce(cast(USER_ID AS STRING),'<NULL>'), coalesce(cast(EVENT_AT AS STRING),'<NULL>'), coalesce(cast(IP_ADDRESS AS STRING),'<NULL>'), coalesce(cast(USER_AGENT AS STRING),'<NULL>'), coalesce(cast(RAW_LINE AS STRING),'<NULL>'), coalesce(cast(BROWSER AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash
FROM cpw.dbx_d1111_parity.users__spark_users_login_useragent_parse__spark_before
UNION ALL
SELECT 'after', count(*),
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(LOGIN_EVENT_ID AS STRING),'<NULL>'), coalesce(cast(USER_ID AS STRING),'<NULL>'), coalesce(cast(EVENT_AT AS STRING),'<NULL>'), coalesce(cast(IP_ADDRESS AS STRING),'<NULL>'), coalesce(cast(USER_AGENT AS STRING),'<NULL>'), coalesce(cast(RAW_LINE AS STRING),'<NULL>'), coalesce(cast(BROWSER AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0)))
FROM cpw.dbx_d1111_after.users__spark_users_login_useragent_parse;

/* run=dbx-d1111 act=spark step=parity consumer=users_login_useragent_parse */
SELECT 'before_not_in_after' AS direction, * FROM (
  SELECT LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE, BROWSER FROM cpw.dbx_d1111_parity.users__spark_users_login_useragent_parse__spark_before
  EXCEPT ALL
  SELECT LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE, BROWSER FROM cpw.dbx_d1111_after.users__spark_users_login_useragent_parse) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=users_login_useragent_parse */
SELECT 'after_not_in_before' AS direction, * FROM (
  SELECT LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE, BROWSER FROM cpw.dbx_d1111_after.users__spark_users_login_useragent_parse
  EXCEPT ALL
  SELECT LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE, BROWSER FROM cpw.dbx_d1111_parity.users__spark_users_login_useragent_parse__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=users_login_useragent_parse */
DESCRIBE HISTORY cpw.dbx_d1111_after.users__spark_users_login_useragent_parse;
