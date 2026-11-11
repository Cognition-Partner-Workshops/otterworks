from common.runtime import register, save, session

spark = session("billing_invoice_summary_daily")
register(spark, "INVOICE_HDR", "INVOICE_LINE")
result = spark.sql("""
SELECT h.CUSTOMER_ID, h.INVOICE_DATE, COUNT(*) LINE_COUNT, SUM(l.AMOUNT) AMOUNT
FROM INVOICE_HDR h JOIN INVOICE_LINE l ON h.INVOICE_ID = l.INVOICE_ID
GROUP BY h.CUSTOMER_ID, h.INVOICE_DATE
""")
save(result, "billing", "billing_invoice_summary_daily", "sfx_billing.SPARK_INVOICE_SUMMARY")
spark.stop()
