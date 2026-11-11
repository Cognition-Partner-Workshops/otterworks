view: payments {
  sql_table_name: SFX_D1110_AFTER.COMPAT.PAYMENT ;;
  dimension: payment_id { primary_key: yes type: number sql: ${TABLE}.PAYMENT_ID ;; }
  dimension: month_label { sql: TO_CHAR(${TABLE}.PAYMENT_DATE, 'YYYY-MM') ;; }
  measure: collected { type: sum sql: COALESCE(${TABLE}.AMOUNT, 0) ;; }
}
