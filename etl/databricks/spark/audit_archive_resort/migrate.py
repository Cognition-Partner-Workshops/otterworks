# run_token=dbx-d1111 expires=2026-11-24
def transform(frame):
    return frame.orderBy("EVENT_TYPE", "EVENT_AT", "AUDIT_EVENT_ARCHIVE_ID")

def main():
    from pathlib import Path
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    from pyspark.errors import AnalysisException
    try:
        aqe = spark.conf.get("spark.sql.adaptive.enabled")
    except AnalysisException as error:
        if not error.getErrorClass().startswith("CONFIG_NOT_AVAILABLE"):
            raise
        aqe = "UNAVAILABLE (serverless-managed; CONFIG_NOT_AVAILABLE)"
    print("spark.sql.adaptive.enabled=" + aqe)
    statement = Path("/Workspace/Shared/dbx-d1111-spark/audit_archive_resort/inputs.sql").read_text().split(";")[0]
    frame = transform(spark.sql(statement))
    (frame.writeTo("cpw.dbx_d1111_after.audit__spark_audit_archive_resort").using("delta")
     .tableProperty("comment", "run_token=dbx-d1111 expires=2026-11-24")
     .tableProperty("run_token", "dbx-d1111").tableProperty("expires", "2026-11-24")
     .tableProperty("act", "spark").createOrReplace())

if __name__ == "__main__":
    main()
