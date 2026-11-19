from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil

from pyspark.sql import Window
from pyspark.sql.functions import col, expr, lag, max as latest, min as earliest, sum as total, when

from common.runtime import landing, save_partition, session


def sessionize(events):
    order = Window.partitionBy("USER_ID", "DOCUMENT_ID").orderBy("EVENT_AT")
    marked = events.withColumn("PREVIOUS_AT", lag("EVENT_AT").over(order)).withColumn(
        "NEW_SESSION", when(col("PREVIOUS_AT").isNull() |
                            expr("EVENT_AT > PREVIOUS_AT + INTERVAL 1800 SECONDS"), 1).otherwise(0))
    numbered = marked.withColumn("SESSION_NUMBER", total("NEW_SESSION").over(
        order.rowsBetween(Window.unboundedPreceding, Window.currentRow)))
    return numbered.groupBy("USER_ID", "DOCUMENT_ID", "SESSION_NUMBER").agg(
        earliest("EVENT_AT").alias("START_AT"), latest("EVENT_AT").alias("END_AT"))


def main():
    run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date):
        raise ValueError("run_date must be YYYY-MM-DD")
    spark = session("collab_session_sessionize")
    frame = sessionize(landing(spark, "COLLAB_SESSION"))
    root = Path(os.environ.get("LAKE_DIR", "/opt/lake")) / "documents/collab_session_sessionize"
    if root.is_dir():
        for path in root.iterdir():
            if not path.name.startswith("run_date="):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    save_partition(frame, "documents", "collab_session_sessionize", run_date)
    spark.stop()


if __name__ == "__main__":
    main()
