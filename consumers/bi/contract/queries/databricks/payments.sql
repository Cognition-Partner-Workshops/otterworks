SELECT date_format(payments.PAYMENT_DT, 'yyyy-MM') AS LABEL,
  SUM(coalesce(payments.AMOUNT, 0)) AS AMOUNT
FROM cpw.dbx_d1111_after.billing__payment AS payments
GROUP BY 1
ORDER BY 1
