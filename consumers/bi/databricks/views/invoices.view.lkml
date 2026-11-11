view: invoices {
  sql_table_name: cpw.dbx_d1111_after.billing__invoice_hdr ;;
  dimension: invoice_id { primary_key: yes type: number sql: ${TABLE}.INVOICE_ID ;; }
  dimension: account_id { type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: invoice_no { sql: ${TABLE}.INVOICE_NUMBER ;; }
  dimension: month_label { sql: date_format(${TABLE}.INVOICE_DT, 'yyyy-MM') ;; }
  dimension: overdue_30 { type: yesno sql: date_add(${TABLE}.INVOICE_DT, 30) < date_sub(current_date(), 30) ;; }
  dimension: in_reporting_window { type: yesno sql: ${TABLE}.INVOICE_DT >= DATE'2020-01-01' ;; }
  measure: billed { type: sum sql: coalesce(${TABLE}.TOTAL_AMOUNT, 0) ;; }
  measure: tax { type: sum sql: coalesce(${TABLE}.TAX_AMOUNT, 0) ;; }
}
