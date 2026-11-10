from pyspark.sql import SQLContext
from common.runtime import landing, save, session

spark = session("billing_revenue_by_plan")
sql = SQLContext(spark.sparkContext)
landing(spark, "INVOICE_LINE").registerTempTable("INVOICE_LINE")
landing(spark, "PLAN_CATALOG").registerTempTable("PLAN_CATALOG")
result = sql.sql("""
SELECT p.PLAN_ID, p.PLAN_NAME, SUM(l.AMOUNT) REVENUE
FROM INVOICE_LINE l JOIN PLAN_CATALOG p ON l.PLAN_ID = p.PLAN_ID
GROUP BY p.PLAN_ID, p.PLAN_NAME
""")
save(result, "billing", "billing_revenue_by_plan")
spark.stop()
