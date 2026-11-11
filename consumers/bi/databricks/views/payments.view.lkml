view: payments {
  sql_table_name: cpw.dbx_d1111_after.billing__payment ;;
  dimension: payment_id { primary_key: yes type: number sql: ${TABLE}.PAYMENT_ID ;; }
  dimension: month_label { sql: date_format(${TABLE}.PAYMENT_DT, 'yyyy-MM') ;; }
  measure: collected { type: sum sql: coalesce(${TABLE}.AMOUNT, 0) ;; }
}
