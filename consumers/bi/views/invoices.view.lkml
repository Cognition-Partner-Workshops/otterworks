view: invoices {
  sql_table_name: SFX_BILLING.INVOICE_HDR ;;
  dimension: invoice_id { primary_key: yes type: number sql: ${TABLE}.INVOICE_ID ;; }
  dimension: account_id { type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: invoice_no { sql: ${TABLE}.INVOICE_NUMBER ;; }
  dimension: month_label { sql: CAST(CAST(${TABLE}.INVOICE_DT AS FORMAT 'YYYY-MM') AS CHAR(7)) ;; }
  dimension: overdue_30 { type: yesno sql: (${TABLE}.INVOICE_DT + 30) < CURRENT_DATE - 30 ;; }
  dimension: in_reporting_window { type: yesno sql: ${TABLE}.INVOICE_DT >= 1200101 ;; }
  measure: billed { type: sum sql: ZEROIFNULL(${TABLE}.TOTAL_AMOUNT) ;; }
  measure: tax { type: sum sql: ZEROIFNULL(${TABLE}.TAX_AMOUNT) ;; }
}
