import math
import os
from datetime import datetime, timezone
from pyspark.sql.functions import col, udf
from pyspark.sql.types import DoubleType
from common.runtime import landing, save_partition, session


@udf(DoubleType())
def score(status, customer_id):
    linear = -1.8 + 0.04 * (customer_id % 50) + (1.2 if status == "closed" else 0.0)
    return 1.0 / (1.0 + math.exp(-linear))


spark = session("billing_churn_score")
result = landing(spark, "SUBSCRIPTION").withColumn("CHURN_SCORE", score(col("STATUS"), col("CUSTOMER_ID")))
run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
save_partition(result, "billing", "billing_churn_score", run_date)
spark.stop()
