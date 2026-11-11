view: invoice_revenue {
  sql_table_name: SFX_BILLING.V_INVOICE_REVENUE ;;
  dimension: month_label { sql: ${TABLE}.INVOICE_PERIOD ;; }
  dimension: currency_cd { sql: ${TABLE}.CURRENCY_CD ;; }
  measure: billed { type: sum sql: ZEROIFNULL(${TABLE}.TOTAL_AMOUNT) ;; }
  measure: invoice_count { type: sum sql: ZEROIFNULL(${TABLE}.INVOICE_COUNT) ;; }
}
