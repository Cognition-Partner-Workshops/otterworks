view: gl_accounts {
  sql_table_name: SFX_D1110_AFTER.RAW_BILLING.GL_ACCOUNT ;;
  dimension: gl_account_cd { primary_key: yes sql: ${TABLE}.GL_ACCOUNT_ID ;; }
  dimension: gl_account_name { sql: ${TABLE}.ACCOUNT_NAME ;; }
  dimension: account_class { sql: ${TABLE}.ACCOUNT_TYPE ;; }
}
