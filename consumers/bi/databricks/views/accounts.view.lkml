view: accounts {
  sql_table_name: cpw.dbx_d1111_after.billing__customer_account ;;
  dimension: account_id { primary_key: yes type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: customer_id { type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: account_no { sql: ${TABLE}.ACCOUNT_NUMBER ;; }
  dimension: currency_cd { sql: ${TABLE}.CURRENCY_CD ;; }
}
