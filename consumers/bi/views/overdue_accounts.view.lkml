view: overdue_accounts {
  derived_table: {
    datagroup_trigger: finance_four_hours
    sql:
      WITH balances AS (
        SEL i.CUSTOMER_ID, i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
        FROM SFX_BILLING.INVOICE_HDR i
        LEFT JOIN (SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM SFX_BILLING.PAYMENT GROUP BY INVOICE_ID) p
          ON p.INVOICE_ID = i.INVOICE_ID
        WHERE i.INVOICE_DT >= 1200101 AND (i.INVOICE_DT + 30) < CURRENT_DATE - 30
      ), accounts AS (
        SEL a.ACCOUNT_NUMBER AS ACCOUNT_NO, SUM(b.OPEN_BALANCE) AS OVERDUE_BALANCE
        FROM balances b JOIN SFX_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = b.CUSTOMER_ID
        WHERE b.OPEN_BALANCE > 0
        GROUP BY a.ACCOUNT_NUMBER
      )
      SEL TOP 100 ACCOUNT_NO, OVERDUE_BALANCE FROM accounts
      QUALIFY ROW_NUMBER() OVER (ORDER BY OVERDUE_BALANCE DESC, ACCOUNT_NO) <= 100
      ORDER BY OVERDUE_BALANCE DESC, ACCOUNT_NO ;;
  }
  dimension: account_no { primary_key: yes sql: ${TABLE}.ACCOUNT_NO ;; }
  measure: overdue_balance { type: sum sql: ZEROIFNULL(${TABLE}.OVERDUE_BALANCE) ;; }
}
