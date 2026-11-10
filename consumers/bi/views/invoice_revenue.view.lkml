view: invoice_revenue {
  derived_table: {
    sql:
      SELECT UPPER(RTRIM(i.CURRENCY_CODE)) AS CURRENCY_CD,
        TO_CHAR(i.INVOICE_DATE, 'YYYY-MM') AS INVOICE_PERIOD,
        COUNT(*) AS INVOICE_COUNT, SUM(i.TOTAL_AMOUNT) AS TOTAL_AMOUNT
      FROM SFX_D1110_AFTER.COMPAT.INVOICE i
      INNER JOIN SFX_D1110_AFTER.COMPAT.ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
      GROUP BY UPPER(RTRIM(i.CURRENCY_CODE)), TO_CHAR(i.INVOICE_DATE, 'YYYY-MM') ;;
  }
  dimension: month_label { sql: ${TABLE}.INVOICE_PERIOD ;; }
  dimension: currency_cd { sql: ${TABLE}.CURRENCY_CD ;; }
  measure: billed { type: sum sql: COALESCE(${TABLE}.TOTAL_AMOUNT, 0) ;; }
  measure: invoice_count { type: sum sql: COALESCE(${TABLE}.INVOICE_COUNT, 0) ;; }
}
