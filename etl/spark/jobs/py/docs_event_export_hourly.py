import os

from pyspark.sql.functions import col, lit, pmod
from common.runtime import landing, session

spark = session("docs_event_export_hourly")
events = landing(spark, "DOCUMENT").withColumn("EXPORT_BUCKET", pmod(col("DOCUMENT_ID"), lit(10000)))
events.coalesce(1).write.mode("overwrite").option(
    "partitionOverwriteMode", "static"
).option("parquet.block.size", 1048576).option("parquet.page.size", 65536).option(
    "parquet.enable.dictionary", "false"
).partitionBy("EXPORT_BUCKET").parquet(
    f"{os.environ.get('LAKE_DIR', '/opt/lake')}/documents/docs_event_export_hourly"
)
spark.stop()
