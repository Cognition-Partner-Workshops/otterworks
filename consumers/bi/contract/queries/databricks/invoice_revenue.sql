SELECT invoice_revenue.INVOICE_PERIOD AS LABEL,
  SUM(coalesce(invoice_revenue.TOTAL_AMOUNT, 0)) AS AMOUNT
FROM cpw.dbx_d1111_after.billing__v_invoice_revenue AS invoice_revenue
GROUP BY 1
ORDER BY 1
