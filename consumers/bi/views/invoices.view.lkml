view: invoices {
  sql_table_name: FIN_DW.INVOICE ;;
  dimension: invoice_id { primary_key: yes type: number sql: ${TABLE}.INVOICE_ID ;; }
  dimension: account_id { type: number sql: ${TABLE}.ACCOUNT_ID ;; }
  dimension: invoice_no { sql: ${TABLE}.INVOICE_NO ;; }
  dimension: month_label { sql: (${TABLE}.INVOICE_DT (FORMAT 'YYYY-MM') (CHAR(7))) ;; }
  dimension: overdue_30 { type: yesno sql: ${TABLE}.DUE_DT < CURRENT_DATE - 30 ;; }
  dimension: in_reporting_window { type: yesno sql: ${TABLE}.INVOICE_DT >= 1200101 ;; }
  measure: billed { type: sum sql: ZEROIFNULL(${TABLE}.AMOUNT_DUE) ;; }
  measure: tax { type: sum sql: ZEROIFNULL(${TABLE}.TAX_AMT) ;; }
}
