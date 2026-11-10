view: accounts {
  sql_table_name: FIN_DW.ACCOUNT ;;
  dimension: account_id { primary_key: yes type: number sql: ${TABLE}.ACCOUNT_ID ;; }
  dimension: customer_id { type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: account_no { sql: ${TABLE}.ACCOUNT_NO ;; }
  dimension: plan_name { sql: ${TABLE}.PLAN_NAME ;; }
}
