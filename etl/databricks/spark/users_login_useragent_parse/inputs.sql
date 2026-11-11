/* run=dbx-d1111 act=spark step=inputs consumer=users_login_useragent_parse */
/* run_token=dbx-d1111 expires=2026-11-24
   Landing LOGIN_EVENT: LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE.
   Live SFX_USERS.LOGIN_EVENT (warehouse/teradata/ddl/users/00_tables.sql) has login_id,
   user_id, login_ts, result_cd, client_type (CHAR(12): API/DESKTOP/MOBILE/WEB). The job parses
   USER_AGENT with (Chrome|Firefox|Safari)/(\S+); client_type is a device category, not a
   user-agent string, so mapping it would only produce 'Other' and is not an equivalent.
   IP_ADDRESS and RAW_LINE have no live column either (core and stg_ tables alike).
     LOGIN_EVENT_ID <- login_id, USER_ID <- user_id, EVENT_AT <- login_ts,
     IP_ADDRESS/USER_AGENT/RAW_LINE <- (none)
   Gap check (first failing result): */
SELECT 'login_event' AS live_table,
  (SELECT count(*) FROM cpw.dbx_d1111_before.users__login_event) AS live_rows,
  (SELECT count(*) FROM cpw.dbx_d1111_before.users__stg_login_event) AS stg_rows,
  (SELECT count(*) FROM cpw.information_schema.columns
    WHERE table_catalog='cpw' AND table_schema='dbx_d1111_before'
      AND table_name IN ('users__login_event','users__stg_login_event')
      AND lower(column_name) IN ('user_agent','ip_address','raw_line')) AS required_cols_found
