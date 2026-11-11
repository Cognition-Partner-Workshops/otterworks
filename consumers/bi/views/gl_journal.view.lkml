view: gl_journal {
  sql_table_name: SFX_BILLING.GL_JOURNAL_LINE ;;
  dimension: journal_id { primary_key: yes type: number sql: ${TABLE}.JOURNAL_LINE_ID ;; }
  dimension: gl_account_cd { sql: ${TABLE}.GL_ACCOUNT_ID ;; }
  dimension: period_id { type: number sql: EXTRACT(YEAR FROM ${TABLE}.POSTING_DT) * 100 + EXTRACT(MONTH FROM ${TABLE}.POSTING_DT) ;; }
  measure: movement { type: sum sql: ZEROIFNULL(${TABLE}.DEBIT_AMOUNT) - ZEROIFNULL(${TABLE}.CREDIT_AMOUNT) ;; }
}
