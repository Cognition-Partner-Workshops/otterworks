view: overdue_accounts {
  derived_table: {
    datagroup_trigger: finance_four_hours
    sql:
      WITH balances AS (
        SELECT i.CUSTOMER_ID, i.TOTAL_AMOUNT - coalesce(p.PAID, 0) AS OPEN_BALANCE
        FROM cpw.dbx_d1111_after.billing__invoice_hdr i
        LEFT JOIN (SELECT INVOICE_ID, SUM(AMOUNT) AS PAID FROM cpw.dbx_d1111_after.billing__payment GROUP BY INVOICE_ID) p
          ON p.INVOICE_ID = i.INVOICE_ID
        WHERE i.INVOICE_DT >= DATE'2020-01-01' AND date_add(i.INVOICE_DT, 30) < date_sub(current_date(), 30)
      ), accounts AS (
        SELECT a.ACCOUNT_NUMBER AS ACCOUNT_NO, SUM(b.OPEN_BALANCE) AS OVERDUE_BALANCE
        FROM balances b JOIN cpw.dbx_d1111_after.billing__customer_account a ON a.CUSTOMER_ID = b.CUSTOMER_ID
        WHERE b.OPEN_BALANCE > 0
        GROUP BY a.ACCOUNT_NUMBER
      )
      SELECT ACCOUNT_NO, OVERDUE_BALANCE FROM accounts
      QUALIFY ROW_NUMBER() OVER (ORDER BY OVERDUE_BALANCE DESC, ACCOUNT_NO) <= 100
      ORDER BY OVERDUE_BALANCE DESC, ACCOUNT_NO
      LIMIT 100 ;;
  }
  dimension: account_no { primary_key: yes sql: ${TABLE}.ACCOUNT_NO ;; }
  measure: overdue_balance { type: sum sql: coalesce(${TABLE}.OVERDUE_BALANCE, 0) ;; }
}
