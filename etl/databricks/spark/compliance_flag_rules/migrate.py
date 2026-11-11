# run_token=dbx-d1111 expires=2026-11-24
from pyspark.sql import functions as F

def transform(frame):
    if "SEVERITY" not in frame.columns:
        raise ValueError("Missing required SEVERITY; FLAG_TYPE is not a severity score")
    severity = F.coalesce(F.col("SEVERITY").cast("int"), F.lit(0))
    return frame.select(
        F.coalesce(F.col("COMPLIANCE_FLAG_ID").cast("long"), F.lit(0)).alias("FLAG_ID"),
        F.coalesce(F.col("DOCUMENT_ID").cast("long"), F.lit(0)).alias("DOCUMENT_ID"),
        severity.alias("SEVERITY"),
        F.when(F.col("STATUS") == "closed", "resolved")
         .when(severity >= 7000, "review").otherwise("monitor").alias("DISPOSITION"))

def main():
    from pathlib import Path
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    print("spark.sql.adaptive.enabled=" + spark.conf.get("spark.sql.adaptive.enabled"))
    statement = Path(__file__).with_name("inputs.sql").read_text().split(";")[0]
    frame = transform(spark.sql(statement))
    (frame.writeTo("cpw.dbx_d1111_after.audit__spark_compliance_flag_rules").using("delta")
     .tableProperty("comment", "run_token=dbx-d1111 expires=2026-11-24")
     .tableProperty("run_token", "dbx-d1111").tableProperty("expires", "2026-11-24")
     .tableProperty("act", "spark").createOrReplace())

if __name__ == "__main__":
    main()
