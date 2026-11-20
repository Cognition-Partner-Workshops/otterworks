import difflib
from datetime import datetime, timezone
import os
from pyspark.sql.functions import col, lag, udf
from pyspark.sql.types import DoubleType
from pyspark.sql.window import Window
from common.runtime import landing, save_partition, session


@udf(DoubleType())
def similarity(before, after):
    return difflib.SequenceMatcher(None, before or "", after or "").ratio()


def transform(versions):
    previous = lag("BODY").over(Window.partitionBy("DOCUMENT_ID").orderBy("VERSION_NUMBER"))
    return versions.withColumn("PREVIOUS_BODY", previous).withColumn(
        "SIMILARITY", similarity(col("PREVIOUS_BODY"), col("BODY")))


def main():
    spark = session("doc_version_diff_stats")
    try:
        run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
        save_partition(transform(landing(spark, "DOC_VERSION")),
                       "documents", "doc_version_diff_stats", run_date)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
