WITH invoices AS (
  SELECT h.INVOICE_NUMBER, a.ACCOUNT_NUMBER, h.INVOICE_DT, h.CURRENCY_CD,
    h.TOTAL_AMOUNT, COALESCE(h.TAX_AMOUNT, 0) AS TAX_AMOUNT,
    h.TOTAL_AMOUNT - COALESCE(p.PAID, 0) AS OPEN_BALANCE
  FROM cpw.dbx_d1111_after.billing__v_invoice_base b
  JOIN cpw.dbx_d1111_after.billing__invoice_hdr h ON h.INVOICE_ID = b.INVOICE_ID
  JOIN cpw.dbx_d1111_after.billing__customer_account a ON a.CUSTOMER_ID = h.CUSTOMER_ID
  LEFT JOIN (
    SELECT INVOICE_ID, SUM(AMOUNT) AS PAID FROM cpw.dbx_d1111_after.billing__payment GROUP BY INVOICE_ID
  ) p ON p.INVOICE_ID = h.INVOICE_ID
  WHERE h.BILL_DT = CAST(:extract_date AS DATE)
    AND h.INVOICE_DT >= DATE '2020-01-01'
    AND h.BILL_DT <= date_sub(COALESCE(CAST(:as_of_date AS DATE), current_date()), 1)
)
SELECT
  TRIM(INVOICE_NUMBER) || ',' ||
  TRIM(ACCOUNT_NUMBER) || ',' ||
  date_format(INVOICE_DT, 'yyyy-MM-dd') || ',' ||
  CAST(CAST(TOTAL_AMOUNT AS DECIMAL(15, 2)) AS STRING) || ',' ||
  CAST(CAST(TAX_AMOUNT AS DECIMAL(15, 2)) AS STRING) || ',' ||
  CAST(CAST(OPEN_BALANCE AS DECIMAL(15, 2)) AS STRING) || ',' ||
  TRIM(CURRENCY_CD) AS REPORT_ROW
FROM invoices ORDER BY INVOICE_NUMBER
