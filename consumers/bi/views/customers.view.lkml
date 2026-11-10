view: customers {
  sql_table_name: FIN_DW.CUSTOMER ;;
  dimension: customer_id { primary_key: yes type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: customer_name { sql: ${TABLE}.CUSTOMER_NAME ;; }
  dimension: region_code { sql: ${TABLE}.REGION_CODE ;; }
}
