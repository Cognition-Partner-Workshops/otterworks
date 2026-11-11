# run_token=dbx-d1111 expires=2026-11-24
import math
from pyspark.sql import functions as F

def transform(frame):
    if "SCORE" not in frame.columns:
        raise ValueError("Missing required SCORE; SEVERITY_CD is not an anomaly score")
    records = frame.select(F.col("SECURITY_ALERT_ID").cast("long").alias("ALERT_ID"),
                           F.col("USER_ID").cast("long").alias("USER_ID"),
                           F.col("SCORE").cast("double").alias("SCORE"))
    if records.filter(F.col("SCORE").isNull()).limit(1).count():
        raise ValueError("Original float(SCORE) does not accept null")
    stats = records.agg(F.count("*").alias("n"), F.sum("SCORE").alias("total"),
                       F.sum(F.col("SCORE") * F.col("SCORE")).alias("squares")).first()
    n = max(stats.n, 1)
    mean = (stats.total or 0.0) / n
    stddev = math.sqrt(max((stats.squares or 0.0) / n - mean ** 2, 0.0)) or 1.0
    return records.withColumn("Z_SCORE", (F.col("SCORE") - F.lit(mean)) / F.lit(stddev))

def main():
    from pathlib import Path
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    print("spark.sql.adaptive.enabled=" + spark.conf.get("spark.sql.adaptive.enabled"))
    statement = Path(__file__).with_name("inputs.sql").read_text().split(";")[0]
    frame = transform(spark.sql(statement))
    (frame.writeTo("cpw.dbx_d1111_after.audit__spark_security_alert_anomaly").using("delta")
     .tableProperty("comment", "run_token=dbx-d1111 expires=2026-11-24")
     .tableProperty("run_token", "dbx-d1111").tableProperty("expires", "2026-11-24")
     .tableProperty("act", "spark").createOrReplace())

if __name__ == "__main__":
    main()
