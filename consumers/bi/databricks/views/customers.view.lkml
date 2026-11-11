view: customers {
  sql_table_name: cpw.dbx_d1111_after.billing__customer_account ;;
  dimension: customer_id { primary_key: yes type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: customer_name { sql: ${TABLE}.ACCOUNT_NAME ;; }
  dimension: region_code { sql: ${TABLE}.REGION_CD ;; }
}
