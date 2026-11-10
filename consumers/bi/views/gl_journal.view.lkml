view: gl_journal {
  sql_table_name: FIN_DW.GL_JOURNAL ;;
  dimension: journal_id { primary_key: yes type: number sql: ${TABLE}.JOURNAL_ID ;; }
  dimension: gl_account_cd { sql: ${TABLE}.GL_ACCOUNT_CD ;; }
  dimension: period_id { type: number sql: ${TABLE}.PERIOD_ID ;; }
  measure: movement { type: sum sql: ZEROIFNULL(${TABLE}.DEBIT_AMT) - ZEROIFNULL(${TABLE}.CREDIT_AMT) ;; }
}
