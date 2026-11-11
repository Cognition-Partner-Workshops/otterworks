SELECT date_format(invoices.INVOICE_DT, 'yyyy-MM') AS LABEL,
  SUM(coalesce(invoices.TOTAL_AMOUNT, 0)) AS AMOUNT
FROM cpw.dbx_d1111_after.billing__invoice_hdr AS invoices
LEFT JOIN cpw.dbx_d1111_after.billing__customer_account AS accounts ON invoices.CUSTOMER_ID = accounts.CUSTOMER_ID
LEFT JOIN cpw.dbx_d1111_after.billing__customer_account AS customers ON accounts.CUSTOMER_ID = customers.CUSTOMER_ID
GROUP BY 1
ORDER BY 1
