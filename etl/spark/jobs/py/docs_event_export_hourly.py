from pyspark.sql.functions import col, pmod
from common.runtime import landing, session

spark = session("docs_event_export_hourly")
events = landing(spark, "DOCUMENT").withColumn("EXPORT_BUCKET", pmod(col("DOCUMENT_ID"), col("DOCUMENT_ID") * 0 + 10000))
events.repartition(8, "EXPORT_BUCKET").write.mode("overwrite").partitionBy("EXPORT_BUCKET").parquet(
    "/opt/lake/documents/docs_event_export_hourly"
)
spark.stop()
