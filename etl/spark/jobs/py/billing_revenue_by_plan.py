from common.runtime import landing, save, session

spark = session("billing_revenue_by_plan")
landing(spark, "INVOICE_LINE").createOrReplaceTempView("INVOICE_LINE")
landing(spark, "PLAN_CATALOG").createOrReplaceTempView("PLAN_CATALOG")
result = spark.sql("""
SELECT p.PLAN_ID, p.PLAN_NAME, SUM(l.AMOUNT) REVENUE
FROM INVOICE_LINE l JOIN PLAN_CATALOG p ON l.PLAN_ID = p.PLAN_ID
GROUP BY p.PLAN_ID, p.PLAN_NAME
""")
save(result, "billing", "billing_revenue_by_plan")
spark.stop()
