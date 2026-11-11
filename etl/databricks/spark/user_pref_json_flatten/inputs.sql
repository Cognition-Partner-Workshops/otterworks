/* run=dbx-d1111 act=spark step=inputs consumer=user_pref_json_flatten */
/* run_token=dbx-d1111 expires=2026-11-24
   Landing USER_PREF: USER_PREF_ID, USER_ID, PREF_JSON.
   Live SFX_USERS.USER_PREF (warehouse/teradata/ddl/users/00_tables.sql) is empty;
   stg_user_pref has 200 rows of normalized name/value pairs (pref_id, user_id, pref_name,
   pref_value, updated_dt) with pref_name in (editor_theme, notification_digest,
   review_reminders). There is no PREF_JSON document, and none of the keys the job extracts
   (theme, notifications, locale) exists. Building JSON from pref_name/pref_value would be
   derived data with no basis in etl/ or warehouse/ DDL, so no adapter is defined.
     USER_PREF_ID <- pref_id, USER_ID <- user_id, PREF_JSON <- (none)
   Gap check (first failing result): */
SELECT 'user_pref' AS live_table,
  (SELECT count(*) FROM cpw.dbx_d1111_before.users__user_pref) AS live_rows,
  (SELECT count(*) FROM cpw.dbx_d1111_before.users__stg_user_pref) AS stg_rows,
  (SELECT count(*) FROM cpw.information_schema.columns
    WHERE table_catalog='cpw' AND table_schema='dbx_d1111_before'
      AND table_name IN ('users__user_pref','users__stg_user_pref')
      AND lower(column_name) IN ('pref_json')) AS required_cols_found
