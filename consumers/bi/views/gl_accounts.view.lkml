view: gl_accounts {
  sql_table_name: FIN_DW.GL_ACCOUNT ;;
  dimension: gl_account_cd { primary_key: yes sql: ${TABLE}.GL_ACCOUNT_CD ;; }
  dimension: gl_account_name { sql: ${TABLE}.GL_ACCOUNT_NAME ;; }
  dimension: account_class { sql: ${TABLE}.ACCOUNT_CLASS ;; }
}
