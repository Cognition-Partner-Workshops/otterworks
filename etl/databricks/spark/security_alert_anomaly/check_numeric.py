# run_token=dbx-d1111 expires=2026-11-24
"""Diagnose exact local mismatch without changing canonical formatting or accepting tolerance."""
import json
from pathlib import Path
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.appName("security_alert_numeric_diagnostic").getOrCreate()
before = spark.read.parquet("/opt/lake/audit/security_alert_anomaly").alias("b")
after = spark.read.parquet("/opt/lake/audit/migrated_fixture_security_alert_anomaly").alias("a")
joined = before.join(after, ["ALERT_ID", "USER_ID"])
different = joined.filter(F.col("b.Z_SCORE") != F.col("a.Z_SCORE"))
summary = joined.agg(F.count("*").alias("paired_rows"),
                     F.max(F.abs(F.col("b.Z_SCORE") - F.col("a.Z_SCORE"))).alias("max_abs_delta")).first().asDict()
summary["different_rows"] = different.count()
summary["paired_samples"] = [r.asDict() for r in different.select(
    "ALERT_ID", F.col("b.Z_SCORE").alias("before_z_score"),
    F.col("a.Z_SCORE").alias("after_z_score")).orderBy("ALERT_ID").limit(20).collect()]
summary["verdict"] = "FAIL: exact comparison; no tolerance applied and no correction claimed"
Path(__file__).with_name("numeric-evidence.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary), flush=True)
spark.stop()
