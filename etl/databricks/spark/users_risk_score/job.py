# run_token=dbx-d1111 expires=2026-11-24
import math
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DoubleType


def score(logins, actions):
    if logins is None or actions is None:
        return None
    try:
        return 1.0 / (1.0 + math.exp(-(-2.1 + logins * 0.0004 - actions * 0.0001)))
    except OverflowError:
        return 0.0


def transform(frame):
    return frame.withColumn("RISK_SCORE", F.udf(score, DoubleType())("LOGIN_COUNT", "ACTION_COUNT"))


def main():
    spark = SparkSession.builder.appName("users_risk_score").getOrCreate()
    try:
        adaptive = spark.conf.get("spark.sql.adaptive.enabled")
    except Exception as error:
        if "CONFIG_NOT_AVAILABLE" not in str(error):
            raise
        adaptive = "UNAVAILABLE: serverless does not expose this configuration"
    print("spark.sql.adaptive.enabled=" + adaptive)
    query = Path("/Workspace/Shared/dbx-d1111-spark/users_risk_score/inputs.sql").read_text().strip().removesuffix(";")
    frame = spark.sql(query)
    result = transform(frame)
    (result.writeTo("cpw.dbx_d1111_after.users__spark_users_risk_score")
     .using("delta")
     .tableProperty("comment", "run_token=dbx-d1111 expires=2026-11-24")
     .tableProperty("run_token", "dbx-d1111")
     .tableProperty("expires", "2026-11-24")
     .tableProperty("act", "spark")
     .createOrReplace())


if __name__ == "__main__":
    main()
