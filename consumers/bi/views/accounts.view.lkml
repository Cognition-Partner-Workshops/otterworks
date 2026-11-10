view: accounts {
  sql_table_name: SFX_D1110_AFTER.COMPAT.ACCOUNT ;;
  dimension: account_id { primary_key: yes type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: customer_id { type: number sql: ${TABLE}.CUSTOMER_ID ;; }
  dimension: account_no { sql: ${TABLE}.ACCOUNT_NUMBER ;; }
  dimension: currency_cd { sql: ${TABLE}.CURRENCY_CODE ;; }
}
