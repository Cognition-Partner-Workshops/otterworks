from common.runtime import jdbc_read, save, session

spark = session("billing_payment_aging")
jdbc_read(spark, "sfx_billing.PAYMENT").registerTempTable("PAYMENT")
jdbc_read(spark, "sfx_billing.INVOICE_HDR").registerTempTable("INVOICE_HDR")
result = spark.sql("""
SELECT h.customer_id, h.invoice_id, datediff(p.payment_date, h.due_date) DAYS_LATE,
h.total_amount, p.amount PAID_AMOUNT
FROM INVOICE_HDR h LEFT JOIN PAYMENT p ON h.invoice_id = p.invoice_id
""")
save(result, "billing", "billing_payment_aging")
spark.stop()
