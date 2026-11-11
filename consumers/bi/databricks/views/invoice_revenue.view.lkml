view: invoice_revenue {
  sql_table_name: cpw.dbx_d1111_after.billing__v_invoice_revenue ;;
  dimension: month_label { sql: ${TABLE}.INVOICE_PERIOD ;; }
  dimension: currency_cd { sql: ${TABLE}.CURRENCY_CD ;; }
  measure: billed { type: sum sql: coalesce(${TABLE}.TOTAL_AMOUNT, 0) ;; }
  measure: invoice_count { type: sum sql: coalesce(${TABLE}.INVOICE_COUNT, 0) ;; }
}
