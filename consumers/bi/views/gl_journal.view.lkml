view: gl_journal {
  sql_table_name: SFX_D1110_AFTER.COMPAT.GL_JOURNAL_LINE ;;
  dimension: journal_id { primary_key: yes type: number sql: ${TABLE}.GL_JOURNAL_LINE_ID ;; }
  dimension: gl_account_cd { sql: ${TABLE}.GL_ACCOUNT_ID ;; }
  dimension: period_id { type: number sql: EXTRACT(YEAR FROM ${TABLE}.POSTING_DATE) * 100 + EXTRACT(MONTH FROM ${TABLE}.POSTING_DATE) ;; }
  measure: movement { type: sum sql: COALESCE(${TABLE}.DEBIT_AMOUNT, 0) - COALESCE(${TABLE}.CREDIT_AMOUNT, 0) ;; }
}
