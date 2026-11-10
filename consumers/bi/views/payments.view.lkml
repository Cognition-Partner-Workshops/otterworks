view: payments {
  sql_table_name: FIN_DW.PAYMENT ;;
  dimension: payment_id { primary_key: yes type: number sql: ${TABLE}.PAYMENT_ID ;; }
  dimension: month_label { sql: (${TABLE}.PAYMENT_DT (FORMAT 'YYYY-MM') (CHAR(7))) ;; }
  measure: collected { type: sum sql: ZEROIFNULL(${TABLE}.AMOUNT) ;; }
}
