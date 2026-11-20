from pyspark.sql.functions import col, lit, pmod

from common.runtime import landing, save, session


def run(spark):
    # Match Spark's inferred type for the former bucket directories.
    events = landing(spark, "DOCUMENT").withColumn(
        "EXPORT_BUCKET", pmod(col("DOCUMENT_ID"), lit(10000)).cast("int")
    )
    save(events, "documents", "docs_event_export_hourly")


if __name__ == "__main__":
    spark = session("docs_event_export_hourly")
    try:
        run(spark)
    finally:
        spark.stop()
