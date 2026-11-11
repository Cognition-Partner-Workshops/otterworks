# run_token=dbx-d1111 expires=2026-11-24
import difflib
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DoubleType
from pyspark.sql.window import Window


def similarity(before, after):
    return difflib.SequenceMatcher(None, before or "", after or "").ratio()


def transform(frame):
    previous = F.lag("BODY").over(Window.partitionBy("DOCUMENT_ID").orderBy("VERSION_NUMBER"))
    return frame.withColumn("PREVIOUS_BODY", previous).withColumn(
        "SIMILARITY", F.udf(similarity, DoubleType())("PREVIOUS_BODY", "BODY")
    )


def main():
    spark = SparkSession.builder.appName("doc_version_diff_stats").getOrCreate()
    try:
        adaptive = spark.conf.get("spark.sql.adaptive.enabled")
    except Exception as error:
        if "CONFIG_NOT_AVAILABLE" not in str(error):
            raise
        adaptive = "UNAVAILABLE: serverless does not expose this configuration"
    print("spark.sql.adaptive.enabled=" + adaptive)
    query = Path("/Workspace/Shared/dbx-d1111-spark/doc_version_diff_stats/inputs.sql").read_text().strip().removesuffix(";")
    frame = spark.sql(query)
    result = transform(frame)
    (result.writeTo("cpw.dbx_d1111_after.documents__spark_doc_version_diff_stats")
     .using("delta")
     .tableProperty("comment", "run_token=dbx-d1111 expires=2026-11-24")
     .tableProperty("run_token", "dbx-d1111")
     .tableProperty("expires", "2026-11-24")
     .tableProperty("act", "spark")
     .createOrReplace())


if __name__ == "__main__":
    main()
