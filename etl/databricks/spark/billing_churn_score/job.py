# run_token=dbx-d1111 expires=2026-11-24
import math
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DoubleType


def score(status, customer_id):
    linear = -1.8 + 0.04 * (customer_id % 50) + (1.2 if status == "closed" else 0.0)
    return 1.0 / (1.0 + math.exp(-linear))


def transform(frame):
    return frame.withColumn("CHURN_SCORE", F.udf(score, DoubleType())("STATUS", "CUSTOMER_ID"))


def main():
    spark = SparkSession.builder.appName("billing_churn_score").getOrCreate()
    try:
        adaptive = spark.conf.get("spark.sql.adaptive.enabled")
    except Exception as error:
        if "CONFIG_NOT_AVAILABLE" not in str(error):
            raise
        adaptive = "UNAVAILABLE: serverless does not expose this configuration"
    print("spark.sql.adaptive.enabled=" + adaptive)
    query = Path("/Workspace/Shared/dbx-d1111-spark/billing_churn_score/inputs.sql").read_text().strip().removesuffix(";")
    frame = spark.sql(query)
    result = transform(frame)
    (result.writeTo("cpw.dbx_d1111_after.billing__spark_billing_churn_score")
     .using("delta")
     .tableProperty("comment", "run_token=dbx-d1111 expires=2026-11-24")
     .tableProperty("run_token", "dbx-d1111")
     .tableProperty("expires", "2026-11-24")
     .tableProperty("act", "spark")
     .createOrReplace())


if __name__ == "__main__":
    main()
