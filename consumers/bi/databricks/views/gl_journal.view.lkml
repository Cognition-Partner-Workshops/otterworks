view: gl_journal {
  sql_table_name: cpw.dbx_d1111_after.billing__gl_journal_line ;;
  dimension: journal_id { primary_key: yes type: number sql: ${TABLE}.JOURNAL_LINE_ID ;; }
  dimension: gl_account_cd { sql: ${TABLE}.GL_ACCOUNT_ID ;; }
  dimension: period_id { type: number sql: EXTRACT(YEAR FROM ${TABLE}.POSTING_DT) * 100 + EXTRACT(MONTH FROM ${TABLE}.POSTING_DT) ;; }
  measure: movement { type: sum sql: coalesce(${TABLE}.DEBIT_AMOUNT, 0) - coalesce(${TABLE}.CREDIT_AMOUNT, 0) ;; }
}
