view: payments {
  sql_table_name: SFX_BILLING.PAYMENT ;;
  dimension: payment_id { primary_key: yes type: number sql: ${TABLE}.PAYMENT_ID ;; }
  dimension: month_label { sql: CAST(CAST(${TABLE}.PAYMENT_DT AS FORMAT 'YYYY-MM') AS CHAR(7)) ;; }
  measure: collected { type: sum sql: ZEROIFNULL(${TABLE}.AMOUNT) ;; }
}
