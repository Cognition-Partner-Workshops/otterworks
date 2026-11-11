view: invoices {
  sql_table_name: SFX_D1110_AFTER.COMPAT.INVOICE ;;
  dimension: invoice_id { primary_key: yes type: number sql: ${TABLE}.INVOICE_HDR_ID ;; }
  dimension: account_id { type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: invoice_no { sql: ${TABLE}.INVOICE_NUMBER ;; }
  dimension: month_label { sql: TO_CHAR(${TABLE}.INVOICE_DATE, 'YYYY-MM') ;; }
  dimension: overdue_30 { type: yesno sql: DATEADD(day, 30, ${TABLE}.INVOICE_DATE) < DATEADD(day, -30, CURRENT_DATE) ;; }
  dimension: in_reporting_window { type: yesno sql: ${TABLE}.INVOICE_DATE >= DATE '2020-01-01' ;; }
  measure: billed { type: sum sql: COALESCE(${TABLE}.TOTAL_AMOUNT, 0) ;; }
  measure: tax { type: sum sql: COALESCE(${TABLE}.TAX_AMOUNT, 0) ;; }
}
