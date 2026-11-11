from common.runtime import register, save, session

spark = session("billing_usage_append_daily")
register(spark, "USAGE_DAILY")
result = spark.sql("""
SELECT * FROM USAGE_DAILY WHERE USAGE_DATE = (SELECT MAX(USAGE_DATE) FROM USAGE_DAILY)
""")
save(result, "billing", "billing_usage_append_daily", "sfx_billing.SPARK_USAGE_DAILY", mode="append")
spark.stop()
